from __future__ import annotations
import astropy.coordinates
import astropy.units
import astropy.time
import collections
import datetime
import dataclasses
import logging
import numpy
import pathlib
import requests
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
    def __init__(self, value: typing.Union[str, bytes]):
        self.value = value.encode() if isinstance(value, str) else value
        assert satellite.norad_pattern.match(self.value) is not None


def interpolate_records(
    records: typing.Sequence[Record],
    begin: datetime.datetime,
    end: datetime.datetime,
    samples_count: int,
    window: int = 5,
    polynomial_degree: int = 10,
):
    assert begin < end
    if len(records) < window * 2 + 1:
        raise Exception("insufficient number of records")
    if begin < records[window].time:
        raise Exception("begin is too close to the first record to interpolate")
    if end >= records[-window].time:
        raise Exception("end is too close to the last record to interpolate")
    time_and_position = numpy.array(
        [
            [
                record.time.timestamp(),
                *record.position,
                *([] if record.velocity is None else record.velocity),
            ]
            for record in records
        ]
    )
    min = time_and_position.min(axis=0)
    max = time_and_position.max(axis=0)
    time_and_position = (time_and_position - min) / (max - min)
    polynomials: list[
        tuple[
            numpy.polynomial.Polynomial,
            numpy.polynomial.Polynomial,
            numpy.polynomial.Polynomial,
        ]
    ] = []
    for index in range(window, len(time_and_position) - window):
        points = time_and_position[index - window : index + window + 1]
        polynomials.append(
            (
                numpy.polynomial.Polynomial.fit(
                    points[:, 0],
                    points[:, 1],
                    deg=polynomial_degree,
                ),
                numpy.polynomial.Polynomial.fit(
                    points[:, 0],
                    points[:, 2],
                    deg=polynomial_degree,
                ),
                numpy.polynomial.Polynomial.fit(
                    points[:, 0],
                    points[:, 3],
                    deg=polynomial_degree,
                ),
            )
        )
    ts: list[datetime.datetime] = []
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    sample_interval = datetime.timedelta(
        seconds=(end - begin).total_seconds() / samples_count
    )
    polynomial_index = 0
    for index in range(0, samples_count):
        time = begin + index * sample_interval
        while polynomial_index < len(polynomials) - 1 and abs(
            (records[polynomial_index + window].time - time).total_seconds()
        ) > abs((records[polynomial_index + 1 + window].time - time).total_seconds()):
            polynomial_index += 1
        normalized_time = (time.timestamp() - min[0]) / (max[0] - min[0])
        ts.append(time)
        xs.append(
            polynomials[polynomial_index][0](normalized_time) * (max[1] - min[1])
            + min[1]
        )
        ys.append(
            polynomials[polynomial_index][1](normalized_time) * (max[2] - min[2])
            + min[2]
        )
        zs.append(
            polynomials[polynomial_index][2](normalized_time) * (max[3] - min[3])
            + min[3]
        )
    return astropy.coordinates.ITRS(
        x=numpy.array(xs) * astropy.units.m,
        y=numpy.array(ys) * astropy.units.m,
        z=numpy.array(zs) * astropy.units.m,
        obstime=astropy.time.Time(ts),
    )


def interpolate(
    id: Id,
    begin: datetime.datetime,
    end: datetime.datetime,
    samples_count: int,
    download_directory: typing.Union[str, bytes, pathlib.Path],
    window: int = 5,
    polynomial_degree: int = 10,
) -> astropy.coordinates.ITRS:
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
                        force=False,
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
                if error.errno == 404:
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
    return interpolate_records(
        records,
        begin,
        end,
        samples_count,
        window,
        polynomial_degree,
    )
