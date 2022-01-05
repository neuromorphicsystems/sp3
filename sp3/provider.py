from __future__ import annotations
import astropy.time
import dataclasses
import datetime
import enum
import gzip
import html.parser
import json
import logging
import math
import pathlib
import pkgutil
import re
import requests
import typing
from . import timesystem
from . import satellite
from . import unix


sp3_group_pattern = re.compile(rb"^[A-Z]\*{2}$")


@dataclasses.dataclass
class Cddis:
    username: typing.Optional[str]
    password: typing.Optional[str]
    session: requests.Session


cddis = Cddis(username=None, password=None, session=requests.Session())


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
    sp3_patterns: list[re.Pattern]

    def time_to_parameters(self, time: datetime.datetime):
        gps_seconds = astropy.time.Time(time).gps
        time = self.time_system.time_from_utc(time)
        plus_8_days = time + datetime.timedelta(days=8)
        plus_10_days = time + datetime.timedelta(days=10)
        next_saturday = time + datetime.timedelta(days=(12 - time.weekday()) % 7)
        gps_week = math.floor(gps_seconds / (60 * 60 * 24 * 7))
        return {
            "year": time.year,
            "next_saturay_year_2_digits": f"{next_saturday.year % 100:02d}",
            "next_saturay_month_2_digits": f"{next_saturday.month:02d}",
            "next_saturay_day_2_digits": f"{next_saturday.day:02d}",
            "year_2_digits": f"{time.year % 100:02d}",
            "month_2_digits": f"{time.month:02d}",
            "day_2_digits": f"{time.day:02d}",
            "day_of_year": f"{time.timetuple().tm_yday:03d}",
            "plus_8_days_year_2_digits": f"{plus_8_days.day:02d}",
            "plus_8_days_day_of_year": f"{plus_8_days.timetuple().tm_yday:03d}",
            "plus_10_days_year_2_digits": f"{plus_10_days.day:02d}",
            "plus_10_days_day_of_year": f"{plus_10_days.timetuple().tm_yday:03d}",
            "gps_week": gps_week,
            "gps_day": math.floor(gps_seconds / (60 * 60 * 24) - gps_week * 7),
        }

    def get_response(self, url: str):
        return requests.get(url, stream=True)

    def download_to(self, output: typing.IO[bytes], parameters: dict[str, typing.Any]):
        url = self.url_template.format(**parameters)
        logging.info(f'download "{url}"')
        response = self.get_response(url)
        response.raise_for_status()
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
        with open(download_directory / f"{name}.download", "wb") as output:
            self.download_to(output, parameters)
        (download_directory / f"{name}.download").rename(download_directory / name)
        return download_directory / name


@dataclasses.dataclass
class CddisProvider(Provider):
    class UrsEarthdataOauth(html.parser.HTMLParser):
        def __init__(self):
            super().__init__()
            self.authenticity_token: typing.Optional[str] = None
            self.client_id: typing.Optional[str] = None
            self.state: typing.Optional[str] = None

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, typing.Optional[str]]]
        ):
            if tag == "input":
                name_attr: typing.Optional[str] = None
                value_attr: typing.Optional[str] = None
                for name, value in attrs:
                    if name == "name":
                        name_attr = value
                    elif name == "value":
                        value_attr = value
                if name_attr is not None and value_attr is not None:
                    if name_attr == "authenticity_token":
                        self.authenticity_token = value_attr
                    elif name_attr == "client_id":
                        self.client_id = value_attr
                    elif name_attr == "state":
                        self.state = value_attr

    class UrsEarthdataOauthRedirect(html.parser.HTMLParser):
        def __init__(self):
            super().__init__()
            self.redirect_url: typing.Optional[str] = None

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, typing.Optional[str]]]
        ):
            if tag == "a":
                id_attr: typing.Optional[str] = None
                href_attr: typing.Optional[str] = None
                for name, value in attrs:
                    if name == "id":
                        id_attr = value
                    elif name == "href":
                        href_attr = value
                if id_attr is not None and href_attr is not None:
                    if id_attr == "redir_link":
                        self.redirect_url = href_attr

    def get_response(self, url: str):
        response = cddis.session.get(url, stream=True)
        response.raise_for_status()
        if response.url.startswith("https://urs.earthdata.nasa.gov/oauth"):
            logging.info(
                f'login to https://urs.earthdata.nasa.gov with username "{cddis.username}"'
            )
            if cddis.username is None or cddis.password is None:
                raise Exception(
                    "sp3.cddis.username and sp3.cddis.password must be set before downloading CDDIS data"
                )
            parser = CddisProvider.UrsEarthdataOauth()
            parser.feed(response.text)
            assert parser.authenticity_token is not None
            assert parser.client_id is not None
            assert parser.state is not None
            response = cddis.session.post(
                "https://urs.earthdata.nasa.gov/login",
                data={
                    "utf8": "✓",
                    "authenticity_token": parser.authenticity_token,
                    "username": cddis.username,
                    "password": cddis.password,
                    "client_id": parser.client_id,
                    "redirect_uri": "https://cddis.nasa.gov/proxyauth",
                    "response_type": "code",
                    "state": parser.state,
                    "stay_in": "1",
                    "commit": "Log in",
                },
            )
            response.raise_for_status()
            parser = CddisProvider.UrsEarthdataOauthRedirect()
            parser.feed(response.text)
            assert parser.redirect_url is not None
            response = cddis.session.get(parser.redirect_url, stream=True)
        return response


@dataclasses.dataclass
class CddisSearchProvider(CddisProvider):
    begin_end_delta: int

    def download(
        self,
        time: datetime.datetime,
        download_directory: pathlib.Path,
        force: bool,
    ):
        download_directory.mkdir(parents=True, exist_ok=True)
        http_error: typing.Optional[requests.exceptions.HTTPError] = None
        for offset in range(0, self.begin_end_delta):
            try:
                parameters = self.time_to_parameters(
                    time - datetime.timedelta(days=offset)
                )
                name = self.name_template.format(**parameters)
                if not force and (download_directory / name).is_file():
                    return download_directory / name
                with open(download_directory / f"{name}.download", "wb") as output:
                    self.download_to(output, parameters)
                (download_directory / f"{name}.download").rename(
                    download_directory / name
                )
                return download_directory / name
            except requests.exceptions.HTTPError as error:
                if error.errno == 404:
                    logging.info(f'"{error.request.url}" returned error 404')
                    http_error = error
                    continue
                raise error
        assert http_error is not None
        raise http_error


providers: list[Provider] = []
raw_data = pkgutil.get_data("sp3", "providers.json")
assert raw_data is not None
for json_provider in json.loads(raw_data.decode()):
    assert isinstance(json_provider["type"], str)
    assert isinstance(json_provider["name_template"], str)
    assert isinstance(json_provider["url_template"], str)
    assert isinstance(json_provider["compression"], str)
    assert isinstance(json_provider["time_system"], str)
    assert isinstance(json_provider["duration"], float)
    assert json_provider["duration"] > 0.0
    assert isinstance(json_provider["sp3_ids"], list)
    for sp3_id in json_provider["sp3_ids"]:
        assert isinstance(sp3_id, str)
        assert (
            satellite.sp3_pattern.match(sp3_id.encode()) is not None
            or sp3_group_pattern.match(sp3_id.encode()) is not None
        )
    sp3_ids: set[bytes] = set(sp3_id.encode() for sp3_id in json_provider["sp3_ids"])
    assert len(sp3_ids) == len(json_provider["sp3_ids"])
    sp3_patterns = [
        re.compile(
            (
                f"^{sp3_id[0]}\\d\\d$"
                if sp3_group_pattern.match(sp3_id.encode()) is not None
                else f"^{sp3_id}$"
            ).encode()
        )
        for sp3_id in json_provider["sp3_ids"]
    ]
    if json_provider["type"] == "default":
        provider = Provider(
            name_template=json_provider["name_template"],
            url_template=json_provider["url_template"],
            compression=Compression(json_provider["compression"]),
            time_system=timesystem.TimeSystem(json_provider["time_system"].encode()),
            duration=json_provider["duration"],
            sp3_patterns=sp3_patterns,
        )
    elif json_provider["type"] == "cddis":
        provider = CddisProvider(
            name_template=json_provider["name_template"],
            url_template=json_provider["url_template"],
            compression=Compression(json_provider["compression"]),
            time_system=timesystem.TimeSystem(json_provider["time_system"].encode()),
            duration=json_provider["duration"],
            sp3_patterns=sp3_patterns,
        )
    elif json_provider["type"] == "cddis_search":
        assert isinstance(json_provider["begin_end_delta"], int)
        provider = CddisSearchProvider(
            name_template=json_provider["name_template"],
            url_template=json_provider["url_template"],
            compression=Compression(json_provider["compression"]),
            time_system=timesystem.TimeSystem(json_provider["time_system"].encode()),
            duration=json_provider["duration"],
            sp3_patterns=sp3_patterns,
            begin_end_delta=json_provider["begin_end_delta"],
        )
    else:
        raise Exception('unsupported provider type "{}"'.format(json_provider["type"]))
    providers.append(provider)


def find_providers_of(sp3_id: bytes) -> typing.Iterable[Provider]:
    for provider in providers:
        if any(
            sp3_pattern.match(sp3_id) is not None
            for sp3_pattern in provider.sp3_patterns
        ):
            yield provider
