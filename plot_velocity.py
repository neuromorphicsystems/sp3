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
        satellite = product.satellites[0]
        records = satellite.records
        piecewise_polynomial = sp3.narrowed_records_to_piecewise_polynomial(
            records=records, window=args.window, degree=args.degree
        )
        figure = matplotlib.pyplot.figure(figsize=(14, 12), dpi=80)
        figure.suptitle(f"{name} position and velocity (full fit)")
        subplots = []
        velocity_subplots = []
        for index, ylabel in enumerate(("X", "Y", "Z")):
            subplot = figure.add_subplot(
                6, 1, 2 * index + 1, sharex=None if len(subplots) == 0 else subplots[0]
            )
            subplot.tick_params("x", labelbottom=False)
            subplot.set_ylabel(f"{ylabel} (m)")
            subplots.append(subplot)
            velocity_subplot = figure.add_subplot(
                6, 1, 2 * index + 2, sharex=subplots[0]
            )
            if index == 2:
                velocity_subplot.set_xlabel("Time (s)")
            else:
                velocity_subplot.tick_params("x", labelbottom=False)
            velocity_subplot.set_ylabel(f"{ylabel} velocity (m/s )")
            velocity_subplots.append(velocity_subplot)
        supersamples_count = len(piecewise_polynomial.offset) * 20
        superobstime = numpy.linspace(
            (
                piecewise_polynomial.minimum_time - piecewise_polynomial.reference_time
            ).total_seconds(),
            (
                piecewise_polynomial.maximum_time - piecewise_polynomial.reference_time
            ).total_seconds()
            - (
                piecewise_polynomial.maximum_time - piecewise_polynomial.minimum_time
            ).total_seconds()
            / supersamples_count,
            supersamples_count,
        )
        itrs = piecewise_polynomial(
            obstime=astropy.time.Time(piecewise_polynomial.reference_time)
            + superobstime * astropy.units.Unit("s")
        )
        relative_time = [
            (record.time - piecewise_polynomial.reference_time).total_seconds()
            for record in records
        ]
        for index, quantity in enumerate((itrs.x, itrs.y, itrs.z)):
            subplots[index].plot(
                superobstime,
                quantity.to("m").value,
                "-",
                label="piecewise polynomial",
                linewidth=1.0,
                color="tab:blue",
            )
            subplots[index].plot(
                relative_time,
                [record.position[index] for record in records],
                "+",
                label="fit samples",
                markersize=4,
                color="tab:orange",
            )
        has_velocities = all(record.velocity is not None for record in records)
        for index, quantity in enumerate((itrs.v_x, itrs.v_y, itrs.v_z)):
            velocity_subplots[index].plot(
                superobstime,
                quantity.to("m/s").value,
                "-",
                label="velocity piecewise polynomial"
                if has_velocities
                else "derivated piecewise polynomial",
                linewidth=1.0,
                color="tab:green",
            )
        if all(record.velocity is not None for record in records):
            for index in range(0, len(velocity_subplots)):
                velocity_subplots[index].plot(
                    relative_time,
                    [record.velocity[index] for record in records],  # type: ignore
                    "+",
                    label="velocity fit samples",
                    markersize=4,
                    color="tab:purple",
                )
        handles, labels = subplots[0].get_legend_handles_labels()
        velocity_handles, velocity_labels = velocity_subplots[
            0
        ].get_legend_handles_labels()
        figure.legend(
            handles=handles + velocity_handles, labels=labels + velocity_labels
        )
        figure.savefig(
            dirname
            / "renders"
            / f"{name}_velocity_window{args.window}_degree{args.degree}.png",
            dpi=160,
        )
        matplotlib.pyplot.close(figure)
