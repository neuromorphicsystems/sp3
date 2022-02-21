# SP3

Download and interpolate precise ephemeris in SP3 (-c or -d) format.

- [SP3](#sp3)
  - [Get started](#get-started)
  - [Providers](#providers)
  - [Satellites](#satellites)
  - [Interpolation](#interpolation)
  - [API](#api)
    - [High-level](#high-level)
    - [Low-level](#low-level)
      - [Parser](#parser)
      - [Interpolation](#interpolation-1)
  - [Tests and figures](#tests-and-figures)
  - [Contribute](#contribute)
    - [Format](#format)
    - [Publish](#publish)

## Get started

```sh
# this command also installs the dependencies astropy, numpy, requests, and scipy
python3 -m pip install sp3
```

```py
import astropy.coordinates
import astropy.time
import sp3

sp3_altaz = sp3.altaz_standard_atmosphere(
    id=sp3.NoradId("24876"),
    obstime=astropy.time.Time(
        [
            "2022-01-01T17:00:00Z",
            "2022-01-01T18:00:00Z",
            "2022-01-01T19:00:00Z",
            "2022-01-01T20:00:00Z",
        ],
    ),
    location=astropy.coordinates.EarthLocation.from_geodetic(
        lon=151.2153,
        lat=-33.8568,
        height=4,
    ),
    download_directory="sp3_cache",
)
```

`sp3_altaz` is an astropy.coordinates.AltAz object (https://docs.astropy.org/en/stable/api/astropy.coordinates.AltAz.html) with one point per obstime. It accounts for refraction and aberration effects.

The function `altaz_standard_atmosphere` downloads as many SP3 files as required to cover the entire obstime range. `download_directory` (created if it does not exist) stores downloaded files for future usage.

`id` can be a NORAD id (`sp3.NoradId("40294")`) or a SP3 id / PRN code (`sp3.Sp3Id("G13")`).

Obstimes must be in UTC. The GPS / TAI clocks used by some SP3 files do not have leap seconds (https://en.wikipedia.org/wiki/Leap_second), unlike UTC. This difference can cause interpolation issues under rare conditions (satellite observation over a leap second).

## Providers

This package downloads SP3 files from the following providers:

-   ESA's Navigation Support Office (http://navigation-office.esa.int/GNSS_based_products.html)
-   NASA's Crustal Dynamics Data Information System (CDDIS) (https://cddis.nasa.gov/Data_and_Derived_Products/index.html)

Both provide _rapid_ products available about one day after the time of observation and _final_ products published weekly (see https://cddis.nasa.gov/Data_and_Derived_Products/GNSS/orbit_products.html for details).

This package tries to find _final_ products for the given satellite and obstime, and fallbacks to _rapid_ products if _final_ products do not cover the entire obstime range. _Ultra-rapid_ products, which include predicted positions, are left out on purpose.

Preference is given to ESA's products since they do not require a login and password. To use CDDIS products, create an account at http://urs.earthdata.nasa.gov and specify your credentials before calling SP3 functions:

```py
import sp3

sp3.cddis.username = "earthdata login username"
sp3.cddis.password = "earthdata login password"

# call sp3 methods here
```

The following satellites require a CDDIS account: L12 (CryoSat-2), L39 (Jason-3), L40 (Sentinel-6A / Jason CS), L46 (SARAL), L47 (Swarm-A), L48 (Swarm-B), L49 (Swarm-C), L50 (Ajisai), L55 (Starlette), L56 (Stella), L59 (Larets), L60 (LARES), L69 (HY-2C), L74 (Sentinel-3A), L78 (HY-2D), and L98 (Sentinel-3B).

Providers are listed in preference order in _sp3/providers.json_.

## Satellites

The file _sp3/satellite.json_ lists satellites with an active SP3 provider and maps NORAD ids to SP3 ids. The SP3 id is identical to the Pseudorandom Noise code (PRN) for GNSS satellites (BeiDou, GPS, Galileo, and GLONASS). We used the following sources as reference for PRNs and names:

-   http://www.csno-tarc.cn/en/system/constellation
-   https://www.pulsesat.com/satellites (GPS Operational)
-   https://celestrak.com/NORAD/elements/table.php?GROUP=gps-ops&FORMAT=tle
-   https://en.wikipedia.org/wiki/List_of_Galileo_satellites
-   https://celestrak.com/NORAD/elements/table.php?GROUP=galileo&FORMAT=tle
-   http://www.csno-tarc.cn/en/glonass/constellation
-   https://celestrak.com/NORAD/elements/table.php?GROUP=glo-ops&FORMAT=tle

The PRN code identifies a satellite's role in a constellation whereas the NORAD id corresponds to a specific object. Hence, the NORAD to PRN mapping changes whenever old GNSS satellites are replaced by new ones. Since this library provides a static mapping (last updated 2022-01-01), applications concerned with long-term stability should use SP3 ids rather than NORAD ids.

## Interpolation

This library calculates a satellite's position at arbitrary times by interpolating the SP3 records with piecewise polynomials. The number of samples and the polynomial degree default to 11 and 10, respectively.

The polynomial `Pₖ` is used to interpolate the position for obstimes in the range `[(tₖ₋₁ + tₖ) / 2, (tₖ + tₖ₊₁) / 2[`, where `tₖ₋₁, tₖ, and tₖ₊₁` are the timestamps of the SP3 samples `k - 1`, `k` and `k + 1`. We estimate `Pₖ` with a least-square fit on the sample range `[k - w, k + w]` (`2w + 1` samples in total), where `w` denotes the _window_ parameter.

Each spatial coordinate (`x`, `y` and `z` in ITRS) uses a different piecewise polynomial. Three more polynomials are used for velocities if the SP3 file provides them. Otherwise, we use the spatial polynomials' derivatives.

The figure below shows a plot of the resulting curves for satellite G13 (GPS-BIIR-2, NORAD 24876) with default parameters (`window = 5`, `degree = 10`). Similar plots for other satellites can be found in _renders_.

![renders/ESA0MGNFIN_20213460000_01D_05M_ORB_G13_velocity_window5_degree10.png](https://raw.githubusercontent.com/neuromorphicsystems/sp3/main/renders/ESA0MGNFIN_20213460000_01D_05M_ORB_G13_velocity_window5_degree10.png)

We estimate the method's error by using odd samples for fitting and even samples to evaluate errors.

![renders/ESA0MGNFIN_20213460000_01D_05M_ORB_G13_interpolation_window5_degree10.png](https://raw.githubusercontent.com/neuromorphicsystems/sp3/main/renders/ESA0MGNFIN_20213460000_01D_05M_ORB_G13_interpolation_window5_degree10.png)

The table below shows the maximum error for different pairs `(window, degree)`. Pairs where `window * 2 + 1 ≤ degree` are not evaluated since they yield ill-defined fitting problems.

![renders/ESA0MGNFIN_20213460000_01D_05M_ORB_G13_window_to_error.png](https://raw.githubusercontent.com/neuromorphicsystems/sp3/main/renders/ESA0MGNFIN_20213460000_01D_05M_ORB_G13_window_to_error.png)

## API

### High-level

The high-level API contains functions that download and interpolate SP3 data in a single call.

```py
"""
Download enough SP3 files to cover the obstime range
and return interpolated ITRS positions.

See https://docs.astropy.org/en/stable/api/astropy.coordinates.ITRS.html for details on ITRS.
"""
def itrs(
    id: Id,
    obstime: astropy.time.Time,
    download_directory: typing.Union[str, bytes, pathlib.Path],
    window: int = 5,
    degree: int = 10,
) -> astropy.coordinates.ITRS: ...
```

```py
"""
Download enough SP3 files to cover the obstime range
and return interpolated AltAz positions.

See https://docs.astropy.org/en/stable/api/astropy.coordinates.AltAz.html for details on AltAz.
"""
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
) -> astropy.coordinates.AltAz: ...
```

```py
"""
Download enough SP3 files to cover the obstime range
and return interpolated AltAz positions.

This function calls sp3.ataz with pressure calculated using the Barometric formula ( https://en.wikipedia.org/wiki/Barometric_formula).

See https://docs.astropy.org/en/stable/api/astropy.coordinates.AltAz.html for details on AltAz.
"""
def altaz_standard_atmosphere(
    id: sp3.Id,
    obstime: astropy.time.Time,
    location: astropy.coordinates.EarthLocation,
    download_directory: typing.Union[str, bytes, pathlib.Path],
    temperature: astropy.units.Quantity = 20.0 * astropy.units.Unit("deg_C"),
    relative_humidity: astropy.units.Quantity = 0.0 * astropy.units.dimensionless_unscaled,
    obswl: astropy.units.Quantity = 0.8 * astropy.units.Unit("um"),
    window: int = 5,
    degree: int = 10,
) -> astropy.coordinates.AltAz: ...
```

### Low-level

#### Parser

The parser is compatible with the following formats:

-   SP3-c: https://files.igs.org/pub/data/format/sp3c.txt
-   SP3-d: https://gssc.esa.int/wp-content/uploads/2018/07/sp3d.pdf

The following example illustrates low-level parsing usage:

```py
import sp3

product = sp3.Product.from_file("test_products/ESA0MGNFIN_20213460000_01D_05M_ORB.SP3")

# satellite from SP3 id
satellite = product.satellite_with_id(b"G13")

# satellite from NORAD id
satellite = product.satellite_with_id(sp3.satellite.norad_to_satellite[b"24876"].sp3)
```

Distances are in metres, velocities are in metres per second, clocks are in second, and timestamps are in UTC.

```py
@dataclasses.dataclass
class Product:
    version: sp3.Version
    file_type: sp3.FileType
    time_system: sp3.timesystem.TimeSystem
    data_used: bytes
    coordinate_system: bytes
    orbit_type: bytes
    agency: bytes
    comments: list[bytes]
    satellites: list[sp3.Satellite]

    @classmethod
    def from_bytes(cls, data: bytes) -> sp3.Product: ...

    @classmethod
    def from_file(cls, path: typing.Union[str, bytes, os.PathLike]) -> sp3.Product: ...

    def satellite_with_id(self, sp3_id: bytes) -> sp3.Satellite: ...
```

```py
@dataclasses.dataclass
class Satellite:
    id: bytes
    accuracy: typing.Optional[float]  # m
    records: list[sp3.Record]
```

```py
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
```

#### Interpolation

```py
"""
Estimate piecewise polynomials (positions and velocities) for the given records.
"""
def narrowed_records_to_piecewise_polynomial(
    records: typing.Sequence[Record],
    window: int,
    degree: int,
) -> PiecewisePolynomial
```

```py
"""
Estimate piecewise polynomials (positions and velocities) for the given records.

This function calls sp3.narrowed_records_to_piecewise_polynomial after trimming the records to the smallest set that covers [begin, end[.
This results in a significant speed-up if the range of interest is much smaller than the range covered by the original records.
"""
def records_to_piecewise_polynomial(
    records: typing.Sequence[Record],
    begin: datetime.datetime,
    end: datetime.datetime,
    window: int,
    degree: int,
) -> PiecewisePolynomial
```

```py
@dataclasses.dataclass
class PiecewisePolynomial:
    minimum_time: datetime.datetime
    maximum_time: datetime.datetime
    reference_time: datetime.datetime
    offset: numpy.ndarray
    begin: numpy.ndarray
    coefficients: numpy.ndarray
    velocity_coefficients: numpy.ndarray

def __call__(self, obstime: astropy.time.Time) -> astropy.coordinates.ITRS: ...
```

## Tests and figures

-   `python3 -m sp3 coverage` displays supported satellites and the number of providers per satellite.
-   `python3 test.py` runs parsing tests.
-   `python3 plot_interpolation.py` generates decimated polynomial interpolations graphs with errors (position only).
-   `python3 plot_velocities.py` generates position and velocity graphs. Velocity is interpolated when velocity samples are available and is calculated from the position otherwise.
-   `python3 plot_window_to_error` calculates the error on decimated samples for different polynomial window / polynomial degree combinations.

The output of plot scripts is saved in _renders_.

## Contribute

### Format

Run `black .` to format the source code (see https://github.com/psf/black).

Run `pyright .` to check types (see https://github.com/microsoft/pyright).

Run `python3 test.py` to run unit tests.

### Publish

```
rm -rf sp3.egg-info; rm -rf dist; python3 setup.py sdist
python3 -m twine upload dist/*
```
