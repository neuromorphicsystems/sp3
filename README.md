# sp3

Download and interpolate precise ephemeris (SP3).

## CDDIS registration

http://urs.earthdata.nasa.gov

## Caveats

-   Norad / PRN correlation may change over time (especially for GNSS satellites).
-   All user-facing functions use UTC timestamps for compatibility with TLE data. Unlike UTC, the GPS / TAI clocks used by some SP3 files do not have leap seconds (https://en.wikipedia.org/wiki/Leap_second). This difference can cause interpolation issues under the rare condition of satellite observation over a leap second.
-   SP3 files from GNSS providers (BeiDou, Galileo, GPS, IRNSS, and GLONASS) sometimes contain data for only parts of a constellation. This library's interpolation function will automatically try different providers until it finds the expected satellite.
-   Ultra-rapid products (esu, igu, igv...), which include predicted positions, are not listed in the providers.

## Format documentation

SP3-c https://files.igs.org/pub/data/format/sp3c.txt
SP3-d https://gssc.esa.int/wp-content/uploads/2018/07/sp3d.pdf

## Sources for satellites names, SP3 ids (PRN), and NORAD ids

BeiDou:

-   http://www.csno-tarc.cn/en/system/constellation

Galileo:

-   https://en.wikipedia.org/wiki/List_of_Galileo_satellites
-   http://www.celestrak.com/Norad/elements/table.php?tleFile=galileo&title=Galileo%20Satellites

GPS:

-   https://celestrak.com/NORAD/elements/table.php?tleFile=gps-ops&title=GPS%20Operational%20Satellites
-   https://www.pulsesat.com/satellites

IRNSS:

-   https://en.wikipedia.org/wiki/Indian_Regional_Navigation_Satellite_System

GLONASS:

-   http://www.csno-tarc.cn/en/glonass/constellation
-   https://celestrak.com/NORAD/elements/table.php?tleFile=glo-ops&title=GLONASS%20Operational%20Satellites

## Contribute

Run `black .` to format the source code (see https://github.com/psf/black).
Run `pyright .` to check types (see https://github.com/microsoft/pyright).
Run `python3 test.py` to run unit tests.

## Publish

```
rm -rf dist
python3 setup.py sdist
python3 -m twine upload dist/*
```
