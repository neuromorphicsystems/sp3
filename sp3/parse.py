from __future__ import annotations
import dataclasses
import datetime
import enum
import math
import os
import re
import typing
from . import timesystem


id_to_patterns: dict[bytes, tuple[re.Pattern[bytes], ...]] = {
    b"0": (
        re.compile(
            rb"^#([cd])([PV])(\d{4}) ( \d|\d{2}) ( \d|\d{2}) ( \d|\d{2}) ( \d|\d{2}) ((?: \d|\d{2})\.\d{8}) ([ \d]{7}) (.{5}) (.{5}) (.{3}) (.{4})(?:$|\s+$)"
        ),
    ),
    b"1": (
        re.compile(
            rb"^## ([ \d]{4}) ([ \.\d]{6}\.\d{8}) ([ \d]{5}\.\d{8}) ([ \d]{5}) ([ \d]{1}\.\d{13})(?:$|\s+$)"
        ),
    ),
    b"+0": (re.compile(rb"^\+  ([ \d]{3})   ((?:\w\d{2})*).*(?:$|\s+$)"),),
    b"+": (re.compile(rb"^\+        ((?:\w\d{2})*).*(?:$|\s+$)"),),
    b"++": (
        re.compile(rb"^\+\+       ((?:[ \d]{3})*)(?:$|\s+$)"),
        re.compile(rb"^\+\+$"),
    ),
    b"c0": (
        re.compile(
            rb"^%c ([\w ]{2}) cc ([\w ]{3}) ccc cccc cccc cccc.cccc ccccc ccccc ccccc ccccc(?:$|\s+$)"
        ),
    ),
    b"c1": (
        re.compile(
            rb"^%c cc cc ccc ccc cccc cccc cccc.cccc ccccc ccccc ccccc ccccc(?:$|\s+$)"
        ),
    ),
    b"f0": (
        re.compile(
            rb"^%f ([ \d]{2}\.\d{7}) ([ \d]{2}\.\d{9})  0\.00000000000  0\.000000000000000(?:$|\s+$)"
        ),
    ),
    b"f1": (
        re.compile(
            rb"^%f  0\.0000000  0\.000000000  0\.00000000000  0\.000000000000000(?:$|\s+$)"
        ),
    ),
    b"i": (
        re.compile(
            rb"^%i    0    0    0    0      0      0      0      0         0(?:$|\s+$)"
        ),
    ),
    b"/": (re.compile(rb"^/\*($| .*)(?:$|\s+$)"),),
    b"*": (
        re.compile(
            rb"^\*  (\d{4}) ( \d|\d{2}) ( \d|\d{2}) ( \d|\d{2}) ( \d|\d{2}) ((?: \d|\d{2})\.\d{8})(?:$|\s+$)"
        ),
    ),
    b"p": (
        re.compile(
            rb"^P(\w\d{2})([ \d-]{7}\.\d{6})([ \d-]{7}\.\d{6})([ \d-]{7}\.\d{6})(?:([ \d-]{7}\.\d{6}| {14})(?: ([ \d]{2}) ([ \d]{2}) ([ \d]{2}) ([ \d]{3}) ([ \w])([ \w])|)|)(?:$|\s+$)"
        ),
    ),
    b"ep": (
        re.compile(
            rb"^EP  ([ \d]{4}) ([ \d]{4}) ([ \d]{4}) ([ \d]{7}) ([ \d]{8}) ([ \d]{8}) ([ \d]{8}) ([ \d]{8}) ([ \d]{8}) ([ \d]{8})(?:$|\s+$)$"
        ),
    ),
    b"v": (
        re.compile(
            rb"^V(\w\d{2})([ \d-]{7}\.\d{6})([ \d-]{7}\.\d{6})([ \d-]{7}\.\d{6})"
        ),
        re.compile(
            rb"^V(\w\d{2})([ \d-]{7}\.\d{6})([ \d-]{7}\.\d{6})([ \d-]{7}\.\d{6})([ \d-]{7}\.\d{6})(?:$|\s+$)"
        ),
        re.compile(
            rb"^V(\w\d{2})([ \d-]{7}\.\d{6})([ \d-]{7}\.\d{6})([ \d-]{7}\.\d{6}) {14} ([ \d]{2}) ([ \d]{2}) ([ \d]{2}) ([ \d]{3})(?:$|\s+$)"
        ),
        re.compile(
            rb"^V(\w\d{2})([ \d-]{7}\.\d{6})([ \d-]{7}\.\d{6})([ \d-]{7}\.\d{6})([ \d-]{7}\.\d{6}) ([ \d]{2}) ([ \d]{2}) ([ \d]{2}) ([ \d]{3})(?:$|\s+$)"
        ),
    ),
    b"ev": (
        re.compile(
            rb"^EV  ([ \d]{4}) ([ \d]{4}) ([ \d]{4}) ([ \d]{7}) ([ \d]{8}) ([ \d]{8}) ([ \d]{8}) ([ \d]{8}) ([ \d]{8}) ([ \d]{8})(?:$|\s+$)$"
        ),
    ),
    b"eof": (re.compile(rb"^EOF\s*$"),),
}


class Version(enum.Enum):
    C = b"c"
    D = b"d"


class FileType(enum.Enum):
    GPS = b"G"
    MIXED = b"M"
    GLONASS = b"R"
    LEO = b"L"
    SBAS = b"S"
    IRNSS = b"I"
    GALILEO = b"E"
    BEIDOU = b"B"
    QZSS = b"J"


@dataclasses.dataclass
class Record:
    time: datetime.datetime
    position: tuple[float, float, float]  # m
    position_std: typing.Optional[tuple[float, float, float]]  # m
    velocity: typing.Optional[tuple[float, float, float]]  # m/s
    velocity_std: typing.Optional[tuple[float, float, float]]  # m/s
    clock: typing.Optional[float]  # s
    clock_std: typing.Optional[float]  # s
    clock_rate: typing.Optional[float]  # s/s
    clock_rate_std: typing.Optional[float]  # s/s
    clock_event: bool
    clock_predicted: bool
    xy_correlation: typing.Optional[float]
    xz_correlation: typing.Optional[float]
    xc_correlation: typing.Optional[float]
    yz_correlation: typing.Optional[float]
    yc_correlation: typing.Optional[float]
    zc_correlation: typing.Optional[float]
    xy_velocity_correlation: typing.Optional[float]
    xz_velocity_correlation: typing.Optional[float]
    xc_velocity_correlation: typing.Optional[float]
    yz_velocity_correlation: typing.Optional[float]
    yc_velocity_correlation: typing.Optional[float]
    zc_velocity_correlation: typing.Optional[float]


@dataclasses.dataclass
class Satellite:
    id: bytes
    accuracy: typing.Optional[float]  # m
    records: list[Record]


@dataclasses.dataclass
class Product:
    version: Version
    file_type: FileType
    time_system: timesystem.TimeSystem
    data_used: bytes
    coordinate_system: bytes
    orbit_type: bytes
    agency: bytes
    comments: list[bytes]
    satellites: list[Satellite]

    @classmethod
    def from_bytes(cls, data: bytes):
        state = 0
        product: typing.Optional[Product] = None
        start: typing.Any = None
        satellites_count = 0
        satellite_index = 0
        header_complete = False
        position_base = 2.0
        clock_base = 2.0
        includes_velocities = False
        epochs = 0
        epoch_interval = datetime.timedelta()
        epoch_index = 0
        epoch: typing.Optional[datetime.datetime] = None
        for index, line in enumerate(data.split(b"\n")):
            id: typing.Optional[bytes] = None
            if index == 0:
                id = b"0"
            elif index == 1:
                id = b"1"
            elif index == 2:
                id = b"+0"
                state = 1
            else:
                if state == 1:
                    if line.startswith(b"+ "):
                        id = b"+"
                    else:
                        state = 2
                        id = b"++"
                elif state == 2:
                    if line.startswith(b"++"):
                        id = b"++"
                    else:
                        state = 3
                        id = b"c0"
                elif state == 3:
                    state = 4
                    id = b"c1"
                elif state == 4:
                    state = 5
                    id = b"f0"
                elif state == 5:
                    state = 6
                    id = b"f1"
                elif state == 6 or state == 7:
                    state += 1
                    id = b"i"
                elif state == 8:
                    if line.startswith(b"/* "):
                        id = b"/"
                    else:
                        state = 9
                        assert product is not None
                        assert len(product.satellites) == satellites_count
                        assert satellite_index == satellites_count
                        header_complete = True
                        id = b"*"
                elif state == 9:
                    state = 10
                    id = b"p"
                elif state == 10:
                    if line.startswith(b"P"):
                        id = b"p"
                    elif line.startswith(b"EP"):
                        state = 11
                        id = b"ep"
                    elif line.startswith(b"V"):
                        state = 12
                        id = b"v"
                    elif line.startswith(b"* "):
                        state = 9
                        id = b"*"
                    else:
                        state = 14
                        id = b"eof"
                elif state == 11:
                    if line.startswith(b"P"):
                        id = b"p"
                    elif line.startswith(b"V"):
                        state = 12
                        id = b"v"
                    elif line.startswith(b"* "):
                        state = 9
                        id = b"*"
                    else:
                        state = 14
                        id = b"eof"
                elif state == 12:
                    if line.startswith(b"P"):
                        id = b"p"
                    elif line.startswith(b"EV"):
                        state = 13
                        id = b"ev"
                    elif line.startswith(b"* "):
                        state = 9
                        id = b"*"
                    else:
                        state = 14
                        id = b"eof"
                elif state == 13:
                    if line.startswith(b"P"):
                        id = b"p"
                    elif line.startswith(b"* "):
                        state = 9
                        id = b"*"
                    else:
                        state = 14
                        id = b"eof"
                elif state == 14:
                    if len(line.strip()) > 0:
                        raise Exception(
                            f'found characters line {index + 1} ("{line.decode()}") after EOF'
                        )
                    continue
                else:
                    raise Exception(f"unknown state {state}")
            assert id is not None
            match: typing.Optional[re.Match[bytes]] = None
            for pattern in id_to_patterns[id]:
                match = pattern.match(line)
                if match is not None:
                    break
            if match is None:
                raise Exception(
                    f'SP3 line {index + 1} ("{line}") did not match the pattern "{id}"'
                )
            if id == b"0":
                product = Product(
                    version=Version(match[1]),
                    file_type=None,  # type: ignore
                    time_system=None,  # type: ignore
                    data_used=match[10].strip(),
                    coordinate_system=match[11].strip(),
                    orbit_type=match[12].strip(),
                    agency=match[13].strip(),
                    comments=[],
                    satellites=[],
                )
                includes_velocities = match[2] == b"V"
                epochs = int(match[9])
                start = datetime.datetime(
                    year=int(match[3]),
                    month=int(match[4]),
                    day=int(match[5]),
                    hour=int(match[6]),
                    minute=int(match[7]),
                    second=math.floor(float(match[8])),
                    microsecond=round(
                        (float(match[8]) - math.floor(float(match[8]))) * 1e6
                    ),
                    tzinfo=datetime.timezone.utc,
                )
            elif id == b"1":
                assert product is not None
                assert start == datetime.datetime(
                    year=1980,
                    month=1,
                    day=6,
                    tzinfo=datetime.timezone.utc,
                ) + datetime.timedelta(
                    seconds=int(match[1]) * 7 * 24 * 60 * 60 + float(match[2])
                )
                assert start == datetime.datetime(
                    year=1980,
                    month=1,
                    day=6,
                    tzinfo=datetime.timezone.utc,
                ) + datetime.timedelta(days=int(match[4]) - 44244 + float(match[5]))
                epoch_interval = datetime.timedelta(seconds=float(match[3]))
            elif id == b"+0" or id == b"+":
                if id == b"+0":
                    satellites_count = int(match[1])
                assert product is not None
                packed_ids = match[1 if id == b"+" else 2]
                for slice_start in range(0, len(packed_ids), 3):
                    product.satellites.append(
                        Satellite(
                            id=packed_ids[slice_start : slice_start + 3],
                            accuracy=None,
                            records=[],
                        )
                    )
            elif id == b"++":
                assert product is not None
                if len(match.groups()) < 1:
                    # L69 data (and perhaps others) sometimes has no data (empty line) after '++'
                    pass
                else:
                    for slice_start in range(0, len(match[1]), 3):
                        stripped_slice = match[1][slice_start : slice_start + 3].strip()
                        if len(stripped_slice) > 0:
                            exponent = int(stripped_slice)
                            if satellite_index < len(product.satellites):
                                product.satellites[satellite_index].accuracy = (
                                    None
                                    if exponent == 0
                                    else ((2.0**exponent) / 1000.0)
                                )
                                satellite_index += 1
                            elif exponent > 0:
                                raise Exception(
                                    "there are more accuracy fields than satellites"
                                )
            elif id == b"c0":
                assert product is not None
                product.file_type = FileType(match[1].strip())
                product.time_system = timesystem.TimeSystem(match[2])
            elif id == b"f0":
                position_base = float(match[1])
                clock_base = float(match[2])
            elif id == b"/":
                assert product is not None
                comment = match[1].strip()
                if len(comment) > 0:
                    product.comments.append(comment)
            elif id == b"*":
                assert product is not None
                if epoch_index > 0:
                    assert satellite_index + 1 == len(product.satellites)
                epoch_datetime = datetime.datetime(
                    year=int(match[1]),
                    month=int(match[2]),
                    day=int(match[3]),
                    hour=int(match[4]),
                    minute=int(match[5]),
                    second=math.floor(float(match[6])),
                    microsecond=round(
                        (float(match[6]) - math.floor(float(match[6]))) * 1e6
                    ),
                    tzinfo=datetime.timezone.utc,
                )
                assert epoch_datetime == start + epoch_index * epoch_interval
                epoch = product.time_system.time_to_utc(epoch_datetime)
                epoch_index += 1
                satellite_index = -1
            elif id == b"p":
                satellite_index += 1
                assert product is not None
                assert satellite_index < len(product.satellites)
                assert epoch is not None
                assert match[1] == product.satellites[satellite_index].id
                product.satellites[satellite_index].records.append(
                    Record(
                        time=epoch,
                        position=(
                            float(match[2]) * 1e3,
                            float(match[3]) * 1e3,
                            float(match[4]) * 1e3,
                        ),
                        position_std=None
                        if match[6] is None
                        or len(match[6].strip()) == 0
                        or match[7] is None
                        or len(match[7].strip()) == 0
                        or match[8] is None
                        or len(match[8].strip()) == 0
                        else (
                            (position_base ** float(match[6])) * 1e-3,
                            (position_base ** float(match[7])) * 1e-3,
                            (position_base ** float(match[8])) * 1e-3,
                        ),
                        velocity=None,
                        velocity_std=None,
                        clock=None
                        if match[5] is None or len(match[5].strip()) == 0
                        else float(match[5]) * 1e-6,
                        clock_std=None
                        if match[9] is None or len(match[9].strip()) == 0
                        else (clock_base ** float(match[9])) * 1e-12,
                        clock_rate=None,
                        clock_rate_std=None,
                        clock_event=match[10] == b"E",
                        clock_predicted=match[11] == b"P",
                        xy_correlation=None,
                        xz_correlation=None,
                        xc_correlation=None,
                        yz_correlation=None,
                        yc_correlation=None,
                        zc_correlation=None,
                        xy_velocity_correlation=None,
                        xz_velocity_correlation=None,
                        xc_velocity_correlation=None,
                        yz_velocity_correlation=None,
                        yc_velocity_correlation=None,
                        zc_velocity_correlation=None,
                    )
                )
            elif id == b"ep":
                assert product is not None
                assert satellite_index < len(product.satellites)
                raise Exception("ep field not implemented")
            elif id == b"v":
                assert product is not None
                assert satellite_index < len(product.satellites)
                assert match[1] == product.satellites[satellite_index].id
                groups_count = len(match.groups())
                product.satellites[satellite_index].records[-1].velocity = (
                    float(match[2]) * 1e-1,
                    float(match[3]) * 1e-1,
                    float(match[4]) * 1e-1,
                )
                if groups_count == 5 or groups_count == 9:
                    product.satellites[satellite_index].records[-1].clock_rate = float(
                        match[5]
                    )
                if groups_count == 9:
                    if (
                        len(match[6].strip()) > 0
                        and len(match[7].strip()) > 0
                        and len(match[8].strip()) > 0
                    ):
                        product.satellites[satellite_index].records[-1].velocity_std = (
                            (position_base ** float(match[6])) * 1e-7,
                            (position_base ** float(match[7])) * 1e-7,
                            (position_base ** float(match[8])) * 1e-7,
                        )
                    if len(match[9].strip()) > 0:
                        product.satellites[satellite_index].records[
                            -1
                        ].clock_rate_std = (clock_base ** float(match[9])) * 1e-16
            elif id == b"ev":
                assert product is not None
                assert satellite_index < len(product.satellites)
                raise Exception("ep field not implemented")
        assert product is not None
        assert header_complete
        assert epoch_index == epochs
        if epoch_index > 0:
            assert satellite_index + 1 == len(product.satellites)
        if includes_velocities:
            for satellite in product.satellites:
                for record in satellite.records:
                    assert record.velocity is not None
        else:
            for satellite in product.satellites:
                for record in satellite.records:
                    assert record.velocity is None
        return product

    @classmethod
    def from_file(cls, path: typing.Union[str, bytes, os.PathLike]):
        with open(path, "rb") as file:
            return Product.from_bytes(file.read())

    def satellite_with_id(self, sp3_id: bytes):
        for satellite in self.satellites:
            if satellite.id == sp3_id:
                return satellite
        raise LookupError(sp3_id)
