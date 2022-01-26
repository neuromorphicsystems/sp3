import argparse
import astropy.time
import astropy.units
import matplotlib.pyplot
import numpy
import pathlib
import sp3

dirname = pathlib.Path(__file__).resolve().parent
matplotlib.pyplot.rc("font", size=14, family="Times New Roman")

decimation_level = 2

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument(
    "--product",
    default=None,
    help=f"path to the SP3 product file (defaults to all files in {dirname / 'test_products'})",
)
parser.add_argument(
    "--satellite",
    default=None,
    help="satellite SP3 id (defualts to the first satellite in the file)",
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
args = parser.parse_args()

if args.product is None:
    products_paths = (dirname / "test_products").iterdir()
else:
    products_paths = (pathlib.Path(args.product),)
    assert products_paths[0].suffix in {".sp3", ".SP3"}

for product_path in products_paths:
    if product_path.is_file() and product_path.suffix in {".sp3", ".SP3"}:
        product = sp3.Product.from_file(product_path)
        if args.satellite is None:
            satellite = product.satellites[0]
        else:
            satellite = product.satellite_with_id(args.satellite.encode())
        name = f"{product_path.with_suffix('').name}_{satellite.id.decode()}"
        records = satellite.records
        sample = numpy.array(
            tuple(
                (
                    record.position[0],
                    record.position[1],
                    record.position[2],
                    (record.time - records[0].time).total_seconds(),
                )
                for record in records
            )
        )
        decimation_mask = numpy.zeros(len(records), dtype="?")
        decimation_mask[::decimation_level] = True
        decimated_sample = sample[decimation_mask]
        decimated_rest_sample = sample[numpy.logical_not(decimation_mask)]
        decimated_piecewise_polynomial = sp3.narrowed_records_to_piecewise_polynomial(
            records=records[::decimation_level], window=args.window, degree=args.degree
        )
        figure = matplotlib.pyplot.figure(figsize=(14, 12), dpi=80)
        figure.suptitle(f"{name} position and error (decimated fit)")
        subplots = []
        error_subplots = []
        for index, ylabel in enumerate(("X", "Y", "Z")):
            subplot = figure.add_subplot(
                6, 1, 2 * index + 1, sharex=None if len(subplots) == 0 else subplots[0]
            )
            subplot.tick_params("x", labelbottom=False)
            subplot.set_ylabel(f"{ylabel} (m)")
            subplots.append(subplot)
            error_subplot = figure.add_subplot(6, 1, 2 * index + 2, sharex=subplots[0])
            if index == 2:
                error_subplot.set_xlabel("Time (s)")
            else:
                error_subplot.tick_params("x", labelbottom=False)
            error_subplot.set_ylabel(f"{ylabel} error (m)")
            error_subplots.append(error_subplot)
        supersamples_count = len(decimated_piecewise_polynomial.offset) * 20
        superobstime = numpy.linspace(
            (
                decimated_piecewise_polynomial.minimum_time
                - decimated_piecewise_polynomial.reference_time
            ).total_seconds(),
            (
                decimated_piecewise_polynomial.maximum_time
                - decimated_piecewise_polynomial.reference_time
            ).total_seconds()
            - (
                decimated_piecewise_polynomial.maximum_time
                - decimated_piecewise_polynomial.minimum_time
            ).total_seconds()
            / supersamples_count,
            supersamples_count,
        )
        itrs = decimated_piecewise_polynomial(
            obstime=astropy.time.Time(decimated_piecewise_polynomial.reference_time)
            + superobstime * astropy.units.Unit("s")
        )
        for index, quantity in enumerate((itrs.x, itrs.y, itrs.z)):
            subplots[index].plot(
                superobstime,
                quantity.to("m").value,
                "-",
                label=f"piecewise polynomial",
                linewidth=1.0,
            )
        error_sample = numpy.array(
            tuple(
                (
                    record.position[0],
                    record.position[1],
                    record.position[2],
                    (
                        record.time - decimated_piecewise_polynomial.reference_time
                    ).total_seconds(),
                )
                for record in records
                if record.time >= decimated_piecewise_polynomial.minimum_time
                and record.time < decimated_piecewise_polynomial.maximum_time
            )
        )
        error_interpolated = decimated_piecewise_polynomial(
            obstime=astropy.time.Time(decimated_piecewise_polynomial.reference_time)
            + error_sample[:, 3] * astropy.units.Unit("s")
        )
        for index, subplot in enumerate(subplots):
            subplot.plot(
                decimated_sample[:, 3],
                decimated_sample[:, index],
                "+",
                label="fit samples",
                markersize=4,
                color="tab:orange",
            )
            subplot.plot(
                decimated_rest_sample[:, 3],
                decimated_rest_sample[:, index],
                "+",
                label="test samples",
                markersize=4,
                color="tab:purple",
            )
        for index, (subplot, quantity) in enumerate(
            zip(
                error_subplots,
                (error_interpolated.x, error_interpolated.y, error_interpolated.z),
            )
        ):
            error = error_sample[:, index] - quantity.to("m").value
            subplot.plot(
                error_sample[:, 3],
                error,
                "-",
                label=f"error (fit and test)",
                color="tab:red",
                linewidth=1.0,
            )
        handles, labels = subplots[0].get_legend_handles_labels()
        error_handles, error_labels = error_subplots[0].get_legend_handles_labels()
        figure.legend(handles=handles + error_handles, labels=labels + error_labels)
        figure.savefig(
            dirname
            / "renders"
            / f"{name}_interpolation_window{args.window}_degree{args.degree}.png",
            dpi=160,
        )
        matplotlib.pyplot.close(figure)
