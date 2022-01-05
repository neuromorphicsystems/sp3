from __future__ import annotations
import dataclasses
import json
import pkgutil
import re

sp3_pattern = re.compile(rb"^[A-Z]\d{2}$")

norad_pattern = re.compile(rb"^\d+$")


@dataclasses.dataclass
class Satellite:
    name: str
    sp3: bytes
    norad: bytes


raw_data = pkgutil.get_data("sp3", "satellites.json")
assert raw_data is not None
sp3_to_satellite: dict[bytes, Satellite] = {}
norad_to_satellite: dict[bytes, Satellite] = {}
for json_satellite in json.loads(raw_data.decode()):
    assert isinstance(json_satellite["name"], str)
    assert isinstance(json_satellite["sp3"], str)
    assert isinstance(json_satellite["norad"], str)
    assert sp3_pattern.match(json_satellite["sp3"].encode()) is not None
    assert norad_pattern.match(json_satellite["norad"].encode()) is not None
    satellite = Satellite(
        name=json_satellite["name"],
        sp3=json_satellite["sp3"].encode(),
        norad=json_satellite["norad"].encode(),
    )
    if satellite.sp3 in sp3_to_satellite:
        raise Exception(f"non-unique SP3 id {satellite.sp3}")
    sp3_to_satellite[satellite.sp3] = satellite
    if satellite.norad in norad_to_satellite:
        raise Exception(f"non-unique NORAD id {satellite.norad}")
    norad_to_satellite[satellite.norad] = satellite
