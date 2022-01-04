from __future__ import annotations
import astropy.time
import dataclasses
import datetime
import enum
import gzip
import json
import logging
import math
import pathlib
import pkgutil
import requests
import typing
from . import timesystem
from . import satellite
from . import unix


class Compression(enum.Enum):
    NONE = "none"
    GZIP = "gzip"
    UNIX = "unix"


@dataclasses.dataclass
class Provider:
    name_template: str
    url_template: str
    compression: Compression
    time_system: timesystem.TimeSystem
    duration: float
    sp3_ids: set[bytes]

    def time_to_parameters(self, time: datetime.datetime):
        gps_seconds = astropy.time.Time(time).gps
        time = self.time_system.time_from_utc(time)
        return {
            "year": time.year,
            "day_of_year": time.timetuple().tm_yday,
            "gps_week": math.floor(gps_seconds / (60 * 60 * 24 * 7)),
        }

    def download(
        self,
        time: datetime.datetime,
        download_directory: pathlib.Path,
        force: bool,
    ):
        parameters = self.time_to_parameters(time)
        download_directory.mkdir(parents=True, exist_ok=True)
        name = self.name_template.format(**parameters)
        if not force and (download_directory / name).is_file():
            return download_directory / name
        url = self.url_template.format(**parameters)
        logging.info(f'download "{url}" to "{download_directory / name}"')
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(download_directory / f"{name}.download", "wb") as output:
            if self.compression is Compression.NONE:
                for chunk in response.iter_content(chunk_size=4096):
                    output.write(chunk)
            elif self.compression == Compression.GZIP:
                with gzip.open(response.raw) as decompressed_response:
                    while True:
                        chunk = decompressed_response.read(4096)
                        if len(chunk) == 0:
                            break
                        output.write(chunk)
            elif self.compression == Compression.UNIX:
                unix.uncompress(response.raw, output)
            else:
                raise Exception(f"unsupported compression type {self.compression}")
        (download_directory / f"{name}.download").rename(download_directory / name)
        return download_directory / name


providers: list[Provider] = []
raw_data = pkgutil.get_data("sp3", "providers.json")
assert raw_data is not None
for json_provider in json.loads(raw_data.decode()):
    assert isinstance(json_provider["name_template"], str)
    assert isinstance(json_provider["url_template"], str)
    assert isinstance(json_provider["compression"], str)
    assert isinstance(json_provider["time_system"], str)
    assert isinstance(json_provider["duration"], float)
    assert json_provider["duration"] > 0.0
    assert isinstance(json_provider["sp3_ids"], list)
    for sp3_id in json_provider["sp3_ids"]:
        assert isinstance(sp3_id, str)
        assert satellite.sp3_pattern.match(sp3_id.encode()) is not None
    sp3_ids: set[bytes] = set(sp3_id.encode() for sp3_id in json_provider["sp3_ids"])
    assert len(sp3_ids) == len(json_provider["sp3_ids"])
    providers.append(
        Provider(
            name_template=json_provider["name_template"],
            url_template=json_provider["url_template"],
            compression=Compression(json_provider["compression"]),
            time_system=timesystem.TimeSystem(json_provider["time_system"].encode()),
            duration=json_provider["duration"],
            sp3_ids=sp3_ids,
        )
    )


def find_providers_of(sp3_id: bytes) -> typing.Iterable[Provider]:
    for provider in providers:
        if sp3_id in provider.sp3_ids:
            yield provider


"""
download(
    name="ESA0MGNFIN_20212900000_01D_05M_ORB.sp3",
    url="http://navigation-office.esa.int/products/gnss-products/2180/ESA0MGNFIN_20212900000_01D_05M_ORB.SP3.gz",
    cache=dirname / "download",
    compression=Compression.GZIP,
    force=True,
)

download(
    name="esa21800.sp3",
    url="http://navigation-office.esa.int/products/gnss-products/2180/esa21800.sp3.Z",
    cache=dirname / "download",
    compression=Compression.UNIX,
    force=True,
)
"""
