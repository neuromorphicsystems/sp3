from __future__ import annotations
import dataclasses
import json
import pkgutil
import re

sp3_pattern = re.compile(rb"^[A-Z]\d{2}$")

ilrs_pattern = re.compile(rb"^\d{6,7}$")

norad_pattern = re.compile(rb"^\d+$")


@dataclasses.dataclass
class SatelliteAlias:
    group: str
    name: str
    sp3: bytes


@dataclasses.dataclass
class Satellite:
    group: str
    name: str
    sp3: bytes
    ilrs: bytes
    norad: bytes
    aliases: list[SatelliteAlias]


raw_data = pkgutil.get_data("sp3", "satellites.json")
assert raw_data is not None
sp3_to_satellite: dict[bytes, Satellite] = {}
ilrs_to_satellite: dict[bytes, Satellite] = {}
norad_to_satellite: dict[bytes, Satellite] = {}
for json_satellite in json.loads(raw_data.decode()):
    assert isinstance(json_satellite["group"], str)
    assert isinstance(json_satellite["name"], str)
    assert isinstance(json_satellite["sp3"], str)
    assert isinstance(json_satellite["ilrs"], str)
    assert isinstance(json_satellite["norad"], str)
    assert sp3_pattern.match(json_satellite["sp3"].encode()) is not None
    assert ilrs_pattern.match(json_satellite["ilrs"].encode()) is not None
    assert norad_pattern.match(json_satellite["norad"].encode()) is not None
    if "aliases" in json_satellite:
        assert isinstance(json_satellite["aliases"], list)
        for json_alias in json_satellite["aliases"]:
            assert isinstance(json_alias["group"], str)
            assert isinstance(json_alias["name"], str)
            assert isinstance(json_alias["sp3"], str)
            assert sp3_pattern.match(json_satellite["sp3"].encode()) is not None
    satellite = Satellite(
        group=json_satellite["group"],
        name=json_satellite["name"],
        sp3=json_satellite["sp3"].encode(),
        ilrs=json_satellite["ilrs"].encode(),
        norad=json_satellite["norad"].encode(),
        aliases=[
            SatelliteAlias(
                group=json_alias["group"],
                name=json_alias["name"],
                sp3=json_alias["sp3"].encode(),
            )
            for json_alias in json_satellite["aliases"]
        ]
        if "aliases" in json_satellite
        else [],
    )
    if satellite.sp3 in sp3_to_satellite:
        raise Exception(f"non-unique SP3 id {satellite.sp3}")
    sp3_to_satellite[satellite.sp3] = satellite
    for alias in satellite.aliases:
        if alias.sp3 in sp3_to_satellite:
            raise Exception(f"non-unique SP3 id {alias.sp3}")
        alias_satellite = Satellite(
            group=alias.group,
            name=alias.name,
            sp3=alias.sp3,
            ilrs=satellite.ilrs,
            norad=satellite.norad,
            aliases=[
                *(
                    other_alias
                    for other_alias in satellite.aliases
                    if other_alias.sp3 != alias.sp3
                ),
                SatelliteAlias(
                    group=satellite.group, name=satellite.name, sp3=satellite.sp3
                ),
            ],
        )
        sp3_to_satellite[alias.sp3] = satellite
    if satellite.ilrs in ilrs_to_satellite:
        raise Exception(f"non-unique ILRS id {satellite.ilrs}")
    ilrs_to_satellite[satellite.ilrs] = satellite
    if satellite.norad in norad_to_satellite:
        raise Exception(f"non-unique NORAD id {satellite.norad}")
    norad_to_satellite[satellite.norad] = satellite
