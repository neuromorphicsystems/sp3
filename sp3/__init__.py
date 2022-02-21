from __future__ import annotations
import astropy.coordinates
import astropy.units
import astropy.time
import collections
import datetime
import dataclasses
import erfa
import functools
import itertools
import logging
import numpy
import pathlib
import requests
import scipy.optimize
import typing
from . import provider as provider
from . import satellite as satellite
from . import timesystem as timesystem
from .parse import (
    Version as Version,
    FileType as FileType,
    Record as Record,
    Satellite as Satellite,
    Product as Product,
)
from .provider import cddis as cddis


@dataclasses.dataclass(init=False)
class Id:
    value: bytes

    def __init__(self, _: typing.Union[str, bytes]):
        raise NotImplementedError()


@dataclasses.dataclass(init=False)
class Sp3Id(Id):
    def __init__(self, value: typing.Union[str, bytes]):
        self.value = value.encode() if isinstance(value, str) else value
        assert satellite.sp3_pattern.match(self.value) is not None


@dataclasses.dataclass(init=False)
class NoradId(Id):
    def __init__(self, value: typing.Union[str, bytes, int]):
        if isinstance(value, int):
            self.value = str(value).encode()
        elif isinstance(value, str):
            self.value = value.encode()
        else:
            self.value = value
        assert satellite.norad_pattern.match(self.value) is not None


total_seconds = numpy.vectorize(lambda delta: delta.total_seconds())


@dataclasses.dataclass
class PiecewisePolynomial:
    minimum_time: datetime.datetime
    maximum_time: datetime.datetime
    reference_time: datetime.datetime
    offset: numpy.ndarray
    begin: numpy.ndarray
    coefficients: numpy.ndarray
    velocity_coefficients: numpy.ndarray

    def __call__(self, obstime: astropy.time.Time) -> astropy.coordinates.ITRS:
        assert obstime.scale == "utc"
        first_obstime: datetime.datetime = obstime.min().to_datetime(timezone=datetime.timezone.utc)  # type: ignore
        if first_obstime < self.minimum_time:
            raise Exception(
                "the first obstime is too close to the first record to interpolate"
            )
        last_obstime: datetime.datetime = obstime.max().to_datetime(timezone=datetime.timezone.utc)  # type: ignore
        if last_obstime >= self.maximum_time:
            raise Exception(
                "the last obstime is too close to the last record to interpolate"
            )
        relative_obstime = total_seconds(
            obstime.to_datetime(timezone=datetime.timezone.utc) - self.reference_time
        )
        index = numpy.searchsorted(self.begin, relative_obstime, side="right") - 1
        relative_obstime -= self.offset[index]
        return astropy.coordinates.ITRS(
            x=(
                (
                    numpy.polynomial.polynomial.polyval(
                        relative_obstime,
                        self.coefficients[:, index, 0],
                        tensor=False,
                    )
                )
            )
            * astropy.units.Unit("m"),
            y=(
                (
                    numpy.polynomial.polynomial.polyval(
                        relative_obstime,
                        self.coefficients[:, index, 1],
                        tensor=False,
                    )
                )
            )
            * astropy.units.Unit("m"),
            z=(
                (
                    numpy.polynomial.polynomial.polyval(
                        relative_obstime,
                        self.coefficients[:, index, 2],
                        tensor=False,
                    )
                )
            )
            * astropy.units.Unit("m"),
            v_x=(
                (
                    numpy.polynomial.polynomial.polyval(
                        relative_obstime,
                        self.velocity_coefficients[:, index, 0],
                        tensor=False,
                    )
                )
            )
            * astropy.units.Unit("m/s"),
            v_y=(
                (
                    numpy.polynomial.polynomial.polyval(
                        relative_obstime,
                        self.velocity_coefficients[:, index, 1],
                        tensor=False,
                    )
                )
            )
            * astropy.units.Unit("m/s"),
            v_z=(
                (
                    numpy.polynomial.polynomial.polyval(
                        relative_obstime,
                        self.velocity_coefficients[:, index, 2],
                        tensor=False,
                    )
                )
            )
            * astropy.units.Unit("m/s"),
            obstime=obstime,
        )


def narrowed_records_to_piecewise_polynomial(
    records: typing.Sequence[Record],
    window: int,
    degree: int,
) -> PiecewisePolynomial:
    assert degree >= 0
    assert window * 2 + 1 > degree
    if len(records) < window * 2 + 1:
        raise Exception("insufficient number of records")
    record_position = numpy.array(tuple(record.position for record in records))
    relative_record_time = total_seconds(
        numpy.array(tuple(record.time - records[0].time for record in records))
    )
    relative_record_time_diff = numpy.diff(relative_record_time)
    offset = relative_record_time[window : len(records) - window]
    begin = (
        relative_record_time[window : len(records) - window]
        - relative_record_time_diff[window - 1 : len(records) - window - 1] / 2
    )
    coefficients = numpy.zeros(
        (len(records) - 2 * window, degree + 1, 3), dtype=numpy.double
    )
    mean = numpy.zeros((len(records) - 2 * window, 3))
    std = numpy.zeros((len(records) - 2 * window, 3))
    for index in range(0, len(coefficients)):
        mean[index] = numpy.mean(
            record_position[index : index + 2 * window + 1], axis=0
        )
        std[index] = numpy.std(record_position[index : index + 2 * window + 1], axis=0)
        coefficients[index] = numpy.polynomial.polynomial.polyfit(
            relative_record_time[index : index + 2 * window + 1] - offset[index],
            (record_position[index : index + 2 * window + 1] - mean[index])
            / std[index],
            deg=degree,
        )
    coefficients = coefficients.transpose((1, 0, 2)) * std
    coefficients[0] += mean
    if all(record.velocity is not None for record in records):
        record_velocity = numpy.array(tuple(record.velocity for record in records))
        velocity_coefficients = numpy.zeros(
            (len(records) - 2 * window, degree + 1, 3), dtype=numpy.double
        )
        velocity_mean = numpy.zeros((len(records) - 2 * window, 3))
        velocity_std = numpy.zeros((len(records) - 2 * window, 3))
        for index in range(0, len(velocity_coefficients)):
            velocity_mean[index] = numpy.mean(
                record_velocity[index : index + 2 * window + 1], axis=0
            )
            velocity_std[index] = numpy.std(
                record_velocity[index : index + 2 * window + 1], axis=0
            )
            velocity_coefficients[index] = numpy.polynomial.polynomial.polyfit(
                relative_record_time[index : index + 2 * window + 1] - offset[index],
                (record_velocity[index : index + 2 * window + 1] - velocity_mean[index])
                / velocity_std[index],
                deg=degree,
            )
        velocity_coefficients = (
            velocity_coefficients.transpose((1, 0, 2)) * velocity_std
        )
        velocity_coefficients[0] += velocity_mean
    else:
        velocity_coefficients = numpy.polynomial.polynomial.polyder(coefficients)
    return PiecewisePolynomial(
        minimum_time=records[window].time,
        maximum_time=records[-window].time,
        reference_time=records[0].time,
        offset=offset,
        begin=begin,
        coefficients=coefficients,
        velocity_coefficients=velocity_coefficients,
    )


def records_to_piecewise_polynomial(
    records: typing.Sequence[Record],
    begin: datetime.datetime,
    end: datetime.datetime,
    window: int,
    degree: int,
) -> PiecewisePolynomial:
    assert begin.tzinfo == datetime.timezone.utc
    assert end.tzinfo == datetime.timezone.utc
    assert begin < end
    if begin < records[window].time:
        raise Exception(
            f"begin ({begin}) is too close to the first record to interpolate"
        )
    if end >= records[-window].time:
        raise Exception(f"end ({end}) is too close to the last record to interpolate")
    begin_record_index = 0
    for index, record in enumerate(records):
        if begin < record.time:
            begin_record_index = index - 1
            break
    end_record_index = len(records)
    for index, record in enumerate(reversed(records)):
        if end >= record.time:
            end_record_index = len(records) - 1 - (index - 1)
            break
    return narrowed_records_to_piecewise_polynomial(
        records=list(
            itertools.islice(
                records, begin_record_index - window, end_record_index + window
            )
        ),
        window=window,
        degree=degree,
    )


def load(
    id: Id,
    begin: datetime.datetime,
    end: datetime.datetime,
    download_directory: typing.Union[str, bytes, pathlib.Path],
    window: int,
    force_download: bool = False,
) -> typing.Sequence[Record]:
    sp3_id: bytes
    if isinstance(id, Sp3Id):
        sp3_id = id.value
    elif isinstance(id, NoradId):
        sp3_id = satellite.norad_to_satellite[id.value].sp3
    else:
        raise Exception(f"unsupported id type {id.__class__}")
    assert begin.tzinfo == datetime.timezone.utc
    assert end.tzinfo == datetime.timezone.utc
    assert begin < end
    if isinstance(download_directory, bytes):
        download_directory = pathlib.Path(download_directory.decode())
    elif isinstance(download_directory, str):
        download_directory = pathlib.Path(download_directory)
    provider_found = False
    records: collections.deque[Record] = collections.deque()
    for candidate_provider in provider.find_providers_of(sp3_id):
        offset = 0.0
        begin_covered = False
        end_covered = False
        while True:
            try:
                product = Product.from_file(
                    candidate_provider.download(
                        time=candidate_provider.time_system.offset_seconds(
                            begin, offset
                        ),
                        download_directory=download_directory,
                        force=force_download,
                    )
                )
                candidate_satellite = product.satellite_with_id(sp3_id)
                if offset < 0.0:
                    for record in candidate_satellite.records[::-1]:
                        if len(records) == 0 or record.time < records[0].time:
                            records.appendleft(record)
                else:
                    for record in candidate_satellite.records:
                        if len(records) == 0 or record.time > records[-1].time:
                            records.append(record)
                if len(records) > window:
                    begin_covered = begin >= records[window].time
                    end_covered = end < records[-window].time
                    if begin_covered:
                        if end_covered:
                            provider_found = True
                            break
                        else:
                            offset = max(offset, 0.0) + candidate_provider.duration
                    else:
                        offset = min(offset, 0.0) - candidate_provider.duration
            except requests.exceptions.HTTPError as error:
                if error.response.status_code == 404:
                    logging.warning(f'"{error.request.url}" returned error 404')
                    break
                raise error
            except LookupError as error:
                if error.args[0] == sp3_id:
                    break
                raise error
        if provider_found:
            break
    if not provider_found:
        raise Exception(f'no suitable SP3 provider for "{sp3_id.decode()}"')
    return records


def obstime_to_begin_and_end(obstime: astropy.time.Time):
    assert obstime.scale == "utc"
    begin: datetime.datetime = obstime.min().to_datetime(timezone=datetime.timezone.utc)  # type: ignore
    end: datetime.datetime = obstime.max().to_datetime(timezone=datetime.timezone.utc)  # type: ignore
    while begin == end:
        end += datetime.timedelta(microseconds=1)
    return begin, end


def itrs(
    id: Id,
    obstime: astropy.time.Time,
    download_directory: typing.Union[str, bytes, pathlib.Path],
    window: int = 5,
    degree: int = 10,
) -> astropy.coordinates.ITRS:
    begin, end = obstime_to_begin_and_end(obstime)
    return records_to_piecewise_polynomial(
        records=load(
            id=id,
            begin=begin,
            end=end,
            window=window,
            download_directory=download_directory,
            force_download=False,
        ),
        begin=begin,
        end=end,
        window=window,
        degree=degree,
    )(obstime)


def altaz(
    id: Id,
    obstime: astropy.time.Time,
    location: astropy.coordinates.EarthLocation,
    pressure: astropy.units.Quantity,
    temperature: astropy.units.Quantity,
    relative_humidity: astropy.units.Quantity,
    obswl: astropy.units.Quantity,
    download_directory: typing.Union[str, bytes, pathlib.Path],
    window: int = 5,
    degree: int = 10,
) -> astropy.coordinates.AltAz:
    begin, end = obstime_to_begin_and_end(obstime)
    piecewise_polynomial = records_to_piecewise_polynomial(
        records=load(
            id=id,
            begin=begin - datetime.timedelta(seconds=2.0),
            end=end,
            window=window,
            download_directory=download_directory,
            force_download=False,
        ),
        begin=begin,
        end=end,
        window=window,
        degree=degree,
    )
    c = astropy.constants.c.to("m/s").value  # type: ignore
    location_itrs = location.get_itrs().cartesian.get_xyz()

    def light_time_correction_error(
        scalar_light_time_correction: float, scalar_obstime: astropy.time.Time
    ):
        return (
            numpy.linalg.norm(
                (
                    piecewise_polynomial(
                        scalar_obstime
                        - scalar_light_time_correction * astropy.units.Unit("s")
                    ).cartesian.get_xyz()
                    - location_itrs
                )
                .to("m")
                .value
            )
            - scalar_light_time_correction * c
        )

    light_time_correction = numpy.zeros(len(obstime))
    for index, scalar_obstime in enumerate(obstime):
        light_time_correction[index] = scipy.optimize.root_scalar(
            f=functools.partial(
                light_time_correction_error, scalar_obstime=scalar_obstime  # type: ignore
            ),
            method="brentq",
            bracket=[0.0, 2.0],
        ).root
    corrected_obstime = obstime - light_time_correction * astropy.units.Unit("s")
    itrs = piecewise_polynomial(corrected_obstime)
    itrs_vector = itrs.cartesian.get_xyz().transpose() - location_itrs
    cirs_non_topographic = astropy.coordinates.ITRS(
        x=itrs_vector[:, 0],
        y=itrs_vector[:, 1],
        z=itrs_vector[:, 2],
        v_x=itrs.v_x,
        v_y=itrs.v_y,
        v_z=itrs.v_z,
        obstime=obstime,
    ).transform_to(astropy.coordinates.CIRS(obstime=obstime))
    cirs = astropy.coordinates.CIRS(
        ra=cirs_non_topographic.ra,
        dec=cirs_non_topographic.dec,
        distance=cirs_non_topographic.distance,
        pm_ra_cosdec=cirs_non_topographic.pm_ra_cosdec,
        pm_dec=cirs_non_topographic.pm_dec,
        radial_velocity=cirs_non_topographic.radial_velocity,
        obstime=obstime,
        location=location,
    )
    altaz_vacuo = cirs.transform_to(
        astropy.coordinates.AltAz(obstime=obstime, location=location)
    )
    refraction_a, refraction_b = erfa.refco(
        phpa=pressure.to("hPa").value,
        tc=temperature.to("deg_C").value,
        rh=relative_humidity.value,
        wl=obswl.to("um").value,
    )
    distance_to_zenith = numpy.pi / 2 - altaz_vacuo.alt.to("rad").value
    tan_distance_to_zenith = numpy.tan(distance_to_zenith)
    alt_refraction_correction = (
        refraction_a * tan_distance_to_zenith
        + refraction_b * (tan_distance_to_zenith**3)
    ) * astropy.units.Unit("rad")
    # derivative of a tan(π / 2 - alt) + b tan(π / 2 - alt)³
    pm_alt_refraction_correction = (
        -altaz_vacuo.pm_alt
        * (numpy.cos(distance_to_zenith) ** -2)
        * (refraction_a + 3 * refraction_b * tan_distance_to_zenith**2)
    )
    return astropy.coordinates.AltAz(
        alt=altaz_vacuo.alt + alt_refraction_correction,
        az=altaz_vacuo.az,
        pm_az_cosalt=altaz_vacuo.pm_az_cosalt,
        pm_alt=altaz_vacuo.pm_alt + pm_alt_refraction_correction,
        obstime=obstime,
        location=location,
        pressure=pressure,
        temperature=temperature,
        relative_humidity=relative_humidity,
        obswl=0.8 * astropy.units.Unit("um"),
    )


def altaz_standard_atmosphere(
    id: Id,
    obstime: astropy.time.Time,
    location: astropy.coordinates.EarthLocation,
    download_directory: typing.Union[str, bytes, pathlib.Path],
    temperature: astropy.units.Quantity = 20.0 * astropy.units.Unit("deg_C"),  # type: ignore
    relative_humidity: astropy.units.Quantity = 0.0 * astropy.units.dimensionless_unscaled,  # type: ignore
    obswl: astropy.units.Quantity = 0.8 * astropy.units.Unit("um"),  # type: ignore
    window: int = 5,
    degree: int = 10,
):
    # https://en.wikipedia.org/wiki/Barometric_formula
    p0 = 101325 * astropy.units.Unit("Pa")
    l0 = -0.0065 * astropy.units.Unit("K/m")
    t0 = 288.15 * astropy.units.Unit("K")
    g0 = 9.80665 * astropy.units.Unit("m/s2")
    m = 0.0289644 * astropy.units.Unit("kg")
    rstar = 8.3144598 * astropy.units.Unit("J/K")
    pressure = p0 * ((1.0 + (l0 * location.height / t0)) ** ((-g0 * m) / (rstar * l0)))  # type: ignore
    return altaz(
        id=id,
        obstime=obstime,
        location=location,
        pressure=pressure,
        temperature=temperature,
        relative_humidity=relative_humidity,
        obswl=obswl,
        download_directory=download_directory,
        window=window,
        degree=degree,
    )
