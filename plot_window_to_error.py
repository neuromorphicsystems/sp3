import argparse
import astropy.time
import astropy.units
import matplotlib.colors
import matplotlib.patheffects
import matplotlib.pyplot
import numpy
import pathlib
import sp3

dirname = pathlib.Path(__file__).resolve().parent
matplotlib.pyplot.rc("font", size=14, family="Times New Roman")

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
args = parser.parse_args()

decimation_level = 2
degrees = tuple(range(1, 17))
windows = tuple(range(1, 9))

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
        print(name)
        records = satellite.records
        errors = numpy.zeros((len(degrees), len(windows)))
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
        for degree_index, degree in enumerate(degrees):
            for window_index, window in enumerate(windows):
                if window * 2 + 1 > degree:
                    print(f"{name=}, {degree=}, {window=}")
                    decimated_piecewise_polynomial = (
                        sp3.narrowed_records_to_piecewise_polynomial(
                            records=records[::decimation_level],
                            window=window,
                            degree=degree,
                        )
                    )
                    error_sample = sample[
                        numpy.logical_and(
                            sample[:, 3]
                            >= (
                                decimated_piecewise_polynomial.minimum_time
                                - decimated_piecewise_polynomial.reference_time
                            ).total_seconds(),
                            sample[:, 3]
                            < (
                                decimated_piecewise_polynomial.maximum_time
                                - decimated_piecewise_polynomial.reference_time
                            ).total_seconds(),
                        ),
                    ]
                    error_interpolated = decimated_piecewise_polynomial(
                        obstime=astropy.time.Time(
                            decimated_piecewise_polynomial.reference_time
                        )
                        + error_sample[:, 3] * astropy.units.Unit("s")
                    )
                    errors[len(degrees) - 1 - degree_index, window_index] = numpy.max(
                        numpy.abs(
                            [
                                error_sample[:, 0] - error_interpolated.x.to("m").value,
                                error_sample[:, 1] - error_interpolated.y.to("m").value,
                                error_sample[:, 2] - error_interpolated.z.to("m").value,
                            ]  # type: ignore
                        )
                    )
                else:
                    errors[len(degrees) - 1 - degree_index, window_index] = numpy.nan

        figure = matplotlib.pyplot.figure(figsize=(16, 9), dpi=80)
        figure.suptitle(f"{name} maximum error (decimated fit)")
        subplot = figure.add_subplot(1, 1, 1)
        subplot.xaxis.tick_top()
        subplot.xaxis.set_label_position("top")
        subplot.set_xlabel("window")
        subplot.set_ylabel("degree")
        colormap = subplot.pcolormesh(
            errors,
            norm=matplotlib.colors.LogNorm(
                vmin=numpy.nanmin(errors), vmax=numpy.nanmax(errors)
            ),
            cmap=matplotlib.pyplot.get_cmap("viridis"),
        )
        for degree_index, degree in enumerate(degrees):
            for window_index, window in enumerate(windows):
                text = subplot.text(
                    window_index + 0.5,
                    len(degrees) - 1 - degree_index + 0.5,
                    f"{errors[len(degrees) - 1 - degree_index, window_index]:.2e}"
                    if window * 2 + 1 > degree
                    else "",
                    horizontalalignment="center",
                    color="white",
                )
                text.set_path_effects(
                    [matplotlib.patheffects.withStroke(linewidth=1, foreground="black")]
                )
        figure.colorbar(colormap)
        subplot.set_xticks(numpy.arange(len(windows)) + 0.5, windows)
        subplot.set_yticks(numpy.arange(len(degrees)) + 0.5, reversed(degrees))
        figure.savefig(
            dirname / "renders" / f"{name}_window_to_error.png",
            dpi=160,
        )
        matplotlib.pyplot.close(figure)
