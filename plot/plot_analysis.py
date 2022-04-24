import argparse
import astropy.coordinates
import astropy.time
import astropy.units
import datetime
import itertools
import json
import logging
import matplotlib.pyplot
import numpy
import pathlib
import sp3

dirname = pathlib.Path(__file__).resolve().parent
matplotlib.pyplot.rc("font", size=14, family="Times New Roman")

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument(
    "satellite", help="satellite NORAD id (or SP3 id if the flag --sp3 is used)"
)
parser.add_argument(
    "begin",
    help="begin UTC date in ISO format (for exampe '2022-03-18T13:38:09.425666Z')",
)
parser.add_argument(
    "duration",
    type=float,
    help="duration in seconds",
)
parser.add_argument(
    "latitude",
    type=float,
    help="latitude in degrees",
)
parser.add_argument(
    "longitude",
    type=float,
    help="longitude in degrees",
)
parser.add_argument(
    "height",
    type=float,
    help="height in metres",
)
parser.add_argument(
    "--sp3",
    action="store_true",
    help="indicates that the satellite ID is an SP3 id (instead of NORAD)",
)
parser.add_argument(
    "--download-directory",
    default=dirname.parent / "downloads",
    help="SP3 files download directory",
)
parser.add_argument(
    "--sampling-rate",
    type=float,
    default=1.0,
    help="number of samples per second",
)
parser.add_argument(
    "--window",
    type=int,
    default=5,
    help="polynomial fit window",
)
parser.add_argument(
    "--degree",
    type=int,
    default=10,
    help="polynomial degree",
)
parser.add_argument(
    "--force",
    action="store_true",
    help="re-download files even if they are in already in download_directory",
)
parser.add_argument(
    "--cddis-username",
    default=None,
    help="CDDIS username",
)
parser.add_argument(
    "--cddis-password",
    default=None,
    help="CDDIS password",
)
parser.add_argument(
    "--logging-level",
    default="WARNING",
    choices=["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    help="logging level, use INFO or lower to show download progress",
)
parser.add_argument(
    "--output",
    default=dirname / "analysis",
    help="output directory path",
)
parser.add_argument(
    "--wcs-fields",
    help="path to wcs_fields.json, a JSON representation of the WCS fields returned by https://github.com/neuromorphicsystems/astrometry",
)
args = parser.parse_args()

logging.getLogger().setLevel(getattr(logging, args.logging_level))
if args.cddis_username is not None and args.cddis_password is not None:
    sp3.cddis.username = args.cddis_username
    sp3.cddis.password = args.cddis_password
begin = datetime.datetime.fromisoformat(args.begin.replace("Z", "+00:00"))
end = begin + datetime.timedelta(seconds=args.duration)
output = pathlib.Path(args.output).resolve()
output.mkdir(exist_ok=True)
name = f"{args.satellite}_{begin.isoformat().replace('+00:00', 'Z').replace(':', '-')}_{args.duration}_{args.sampling_rate}"

records = sp3.load(
    id=sp3.Sp3Id(args.satellite) if args.sp3 else sp3.NoradId(args.satellite),
    begin=begin,
    end=end,
    download_directory=args.download_directory,
    window=args.window,
    force_download=args.force,
)
narrowed_records = []
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
narrowed_records = list(
    itertools.islice(
        records, begin_record_index - args.window, end_record_index + args.window
    )
)

# SP3 records
figure = matplotlib.pyplot.figure(figsize=(16, 9), dpi=80)
figure.suptitle(f"{name} SP3 records")
subplots = []
for index, ylabel in enumerate(("X", "Y", "Z")):
    subplot = figure.add_subplot(
        3, 1, index + 1, sharex=None if len(subplots) == 0 else subplots[0]
    )
    subplot.set_ylabel(f"{ylabel} (m)")
    if index == 2:
        subplot.set_xlabel("Time (s)")
    else:
        subplot.tick_params("x", labelbottom=False)
    subplots.append(subplot)
for index, subplot in enumerate(subplots):
    subplot.plot(
        [(record.time - begin).total_seconds() for record in narrowed_records],
        [record.position[index] for record in narrowed_records],
        "+",
        label=["X", "Y", "Z"][index],
    )
figure.legend()
figure.savefig(output / f"{name}_sp3_records.png")
matplotlib.pyplot.close()

# Interpolated records
piecewise_polynomial = sp3.narrowed_records_to_piecewise_polynomial(
    records=narrowed_records, window=args.window, degree=args.degree
)
timestamps = numpy.array(
    [
        index / args.sampling_rate
        for index in range(0, int(numpy.ceil(args.duration * args.sampling_rate)))
    ]
)
itrs = piecewise_polynomial(
    obstime=astropy.time.Time(begin) + timestamps * astropy.units.Unit("s")
)
figure = matplotlib.pyplot.figure(figsize=(16, 9), dpi=80)
figure.suptitle(f"{name} interpolated records")
subplots = []
for index, ylabel in enumerate(("X", "Y", "Z")):
    subplot = figure.add_subplot(
        3, 1, index + 1, sharex=None if len(subplots) == 0 else subplots[0]
    )
    subplot.set_ylabel(f"{ylabel} (m)")
    if index == 2:
        subplot.set_xlabel("Time (s)")
    else:
        subplot.tick_params("x", labelbottom=False)
    subplots.append(subplot)
for index, quantity in enumerate((itrs.x, itrs.y, itrs.z)):
    subplots[index].plot(
        timestamps,
        quantity.to("m").value,
        "+",
        label=["X", "Y", "Z"][index],
    )
figure.legend()
figure.savefig(output / f"{name}_interpolated_records.png")
matplotlib.pyplot.close()

# Interpolated records diff
figure = matplotlib.pyplot.figure(figsize=(16, 9), dpi=80)
figure.suptitle(f"{name} interpolated records (diff)")
subplots = []
for index, ylabel in enumerate(("X", "Y", "Z")):
    subplot = figure.add_subplot(
        3, 1, index + 1, sharex=None if len(subplots) == 0 else subplots[0]
    )
    subplot.set_ylabel(f"{ylabel} (m)")
    if index == 2:
        subplot.set_xlabel("Time (s)")
    else:
        subplot.tick_params("x", labelbottom=False)
    subplots.append(subplot)
for index, quantity in enumerate((itrs.x, itrs.y, itrs.z)):
    subplots[index].plot(
        timestamps[:-1],
        numpy.diff(quantity.to("m").value),
        "+",
        label=["X", "Y", "Z"][index],
    )
figure.legend()
figure.savefig(output / f"{name}_interpolated_records_diff.png")
matplotlib.pyplot.close()

# AzAlt
altaz = sp3.altaz_standard_atmosphere(
    id=sp3.Sp3Id(args.satellite) if args.sp3 else sp3.NoradId(args.satellite),
    obstime=astropy.time.Time(begin) + timestamps * astropy.units.Unit("s"),
    location=astropy.coordinates.EarthLocation.from_geodetic(
        lat=args.latitude,
        lon=args.longitude,
        height=args.height,
    ),
    download_directory=args.download_directory,
    window=args.window,
    degree=args.degree,
)
figure = matplotlib.pyplot.figure(figsize=(16, 9), dpi=80)
figure.suptitle(f"{name} Az/Alt")
subplots = []
for index, ylabel in enumerate(("Az", "Alt")):
    subplot = figure.add_subplot(
        2, 1, index + 1, sharex=None if len(subplots) == 0 else subplots[0]
    )
    subplot.set_ylabel(f"{ylabel} (deg)")
    if index == 1:
        subplot.set_xlabel("Time (s)")
    else:
        subplot.tick_params("x", labelbottom=False)
    subplots.append(subplot)
for index, quantity in enumerate((altaz.az, altaz.alt)):
    subplots[index].plot(
        timestamps,
        quantity.to("deg").value,
        "+",
        label=["Az", "Alt"][index],
    )
figure.legend()
figure.savefig(output / f"{name}_interpolated_records_azalt.png")
matplotlib.pyplot.close()

# Az/Alt diff
figure = matplotlib.pyplot.figure(figsize=(16, 9), dpi=80)
figure.suptitle(f"{name} Az/Alt diff")
subplots = []
for index, ylabel in enumerate(("Az", "Alt")):
    subplot = figure.add_subplot(
        2, 1, index + 1, sharex=None if len(subplots) == 0 else subplots[0]
    )
    subplot.set_ylabel(f"{ylabel} (deg)")
    if index == 1:
        subplot.set_xlabel("Time (s)")
    else:
        subplot.tick_params("x", labelbottom=False)
    subplots.append(subplot)
for index, quantity in enumerate((altaz.az, altaz.alt)):
    subplots[index].plot(
        timestamps[:-1],
        numpy.diff(quantity.to("deg").value),
        "+",
        label=["Az", "Alt"][index],
    )
figure.legend()
figure.savefig(output / f"{name}_interpolated_records_azalt_diff.png")
matplotlib.pyplot.close()

# ICRS
icrs = altaz.transform_to(astropy.coordinates.ICRS())
figure = matplotlib.pyplot.figure(figsize=(16, 9), dpi=80)
figure.suptitle(f"{name} ICRS")
subplots = []
for index, ylabel in enumerate(("Ra", "Dec")):
    subplot = figure.add_subplot(
        2, 1, index + 1, sharex=None if len(subplots) == 0 else subplots[0]
    )
    subplot.set_ylabel(f"{ylabel} (deg)")
    if index == 1:
        subplot.set_xlabel("Time (s)")
    else:
        subplot.tick_params("x", labelbottom=False)
    subplots.append(subplot)
for index, quantity in enumerate((icrs.ra, icrs.dec)):
    subplots[index].plot(
        timestamps,
        quantity.to("deg").value,
        "+",
        label=["Ra", "Dec"][index],
    )
figure.legend()
figure.savefig(output / f"{name}_interpolated_records_icrs.png")
matplotlib.pyplot.close()

# ICRS diff
figure = matplotlib.pyplot.figure(figsize=(16, 9), dpi=80)
figure.suptitle(f"{name} ICRS diff")
subplots = []
for index, ylabel in enumerate(("Ra", "Dec")):
    subplot = figure.add_subplot(
        2, 1, index + 1, sharex=None if len(subplots) == 0 else subplots[0]
    )
    subplot.set_ylabel(f"{ylabel} (deg)")
    if index == 1:
        subplot.set_xlabel("Time (s)")
    else:
        subplot.tick_params("x", labelbottom=False)
    subplots.append(subplot)
for index, quantity in enumerate((icrs.ra, icrs.dec)):
    subplots[index].plot(
        timestamps[:-1],
        numpy.diff(quantity.to("deg").value),
        "+",
        label=["Ra", "Dec"][index],
    )
figure.legend()
figure.savefig(output / f"{name}_interpolated_records_icrs_diff.png")
matplotlib.pyplot.close()

if args.wcs_fields is not None:
    import astropy.wcs

    with open(args.wcs_fields) as wcs_fields_file:
        wcs = astropy.wcs.WCS(
            {key: tuple(value) for key, value in json.load(wcs_fields_file).items()}
        )

    # Pixels
    pixels = wcs.all_world2pix(
        numpy.array([icrs.ra.to("deg").value, icrs.dec.to("deg").value]).transpose(),
        0,
    )
    pixels_nocorrection = wcs.wcs_world2pix(
        numpy.array([icrs.ra.to("deg").value, icrs.dec.to("deg").value]).transpose(),
        0,
    )
    figure = matplotlib.pyplot.figure(figsize=(16, 9), dpi=80)
    figure.suptitle(f"{name} pixels")
    subplots = []
    for index, ylabel in enumerate(("x", "y")):
        subplot = figure.add_subplot(
            2, 1, index + 1, sharex=None if len(subplots) == 0 else subplots[0]
        )
        subplot.set_ylabel(f"{ylabel} (pixels)")
        if index == 1:
            subplot.set_xlabel("Time (s)")
        else:
            subplot.tick_params("x", labelbottom=False)
        subplots.append(subplot)
    for index, subplot in enumerate(subplots):
        subplot.plot(
            timestamps,
            [pixel[index] for pixel in pixels],
            "+",
            label=["x", "y"][index],
        )
        subplot.plot(
            timestamps,
            [pixel[index] for pixel in pixels_nocorrection],
            "+",
            label=["x no correction", "y no correction"][index],
        )
    figure.legend()
    figure.savefig(output / f"{name}_interpolated_records_pixels.png")
    matplotlib.pyplot.close()

    # Pixels correction
    figure = matplotlib.pyplot.figure(figsize=(16, 9), dpi=80)
    figure.suptitle(f"{name} pixels correction delta")
    subplots = []
    for index, ylabel in enumerate(("x", "y")):
        subplot = figure.add_subplot(
            2, 1, index + 1, sharex=None if len(subplots) == 0 else subplots[0]
        )
        subplot.set_ylabel(f"{ylabel} (pixels)")
        if index == 1:
            subplot.set_xlabel("Time (s)")
        else:
            subplot.tick_params("x", labelbottom=False)
        subplots.append(subplot)
    for index, subplot in enumerate(subplots):
        subplot.plot(
            timestamps,
            [
                pixel[index] - pixel_nocorrection[index]
                for pixel, pixel_nocorrection in zip(pixels, pixels_nocorrection)
            ],
            "+",
            label=["x", "y"][index],
        )
    figure.legend()
    figure.savefig(output / f"{name}_interpolated_records_pixels_correction_delta.png")
    matplotlib.pyplot.close()

    # Pixels diff
    figure = matplotlib.pyplot.figure(figsize=(16, 9), dpi=80)
    figure.suptitle(f"{name} pixels diff")
    subplots = []
    for index, ylabel in enumerate(("vx", "vy")):
        subplot = figure.add_subplot(
            2, 1, index + 1, sharex=None if len(subplots) == 0 else subplots[0]
        )
        subplot.set_ylabel(f"{ylabel} (pixels/s)")
        if index == 1:
            subplot.set_xlabel("Time (s)")
        else:
            subplot.tick_params("x", labelbottom=False)
        subplots.append(subplot)
    for index, subplot in enumerate(subplots):
        subplot.plot(
            timestamps[:-1],
            numpy.diff([pixel[index] for pixel in pixels]) * args.sampling_rate,  # type: ignore
            "+",
            label=["vx", "vy"][index],
        )
        subplot.plot(
            timestamps[:-1],
            numpy.diff([pixel[index] for pixel in pixels_nocorrection])  # type: ignore
            * args.sampling_rate,
            "+",
            label=["vx no correction", "vy no correction"][index],
        )
    figure.legend()
    figure.savefig(output / f"{name}_interpolated_records_pixels_diff.png")
    matplotlib.pyplot.close()

    # Pixels diff correction
    figure = matplotlib.pyplot.figure(figsize=(16, 9), dpi=80)
    figure.suptitle(f"{name} pixels diff correction delta")
    subplots = []
    for index, ylabel in enumerate(("vx", "vy")):
        subplot = figure.add_subplot(
            2, 1, index + 1, sharex=None if len(subplots) == 0 else subplots[0]
        )
        subplot.set_ylabel(f"{ylabel} (pixels/s)")
        if index == 1:
            subplot.set_xlabel("Time (s)")
        else:
            subplot.tick_params("x", labelbottom=False)
        subplots.append(subplot)
    for index, subplot in enumerate(subplots):
        subplot.plot(
            timestamps[:-1],
            numpy.subtract(
                numpy.diff([pixel[index] for pixel in pixels]),  # type: ignore
                numpy.diff([pixel[index] for pixel in pixels_nocorrection]),  # type: ignore
            )
            * args.sampling_rate,
            "+",
            label=["vx", "vy"][index],
        )
    figure.legend()
    figure.savefig(
        output / f"{name}_interpolated_records_pixels_diff_correction_delta.png"
    )
    matplotlib.pyplot.close()
