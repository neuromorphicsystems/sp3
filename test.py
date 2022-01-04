import pathlib
import sp3
import unittest

dirname = pathlib.Path(__file__).resolve().parent


class TestSp3(unittest.TestCase):
    def assertRelativeAlmostEqual(
        self, first: float, second: float, maximum_relative_error: float = 1e-9
    ):
        if first == 0.0 and second == 0.0:
            return
        self.assertLess(
            abs((first - second) / (first if second == 0.0 else second)),
            maximum_relative_error,
        )

    def assertVectorEqual(
        self, first: tuple[float, float, float], second: tuple[float, float, float]
    ):
        for index in range(0, 3):
            self.assertRelativeAlmostEqual(first[index], second[index])

    def test_emr21000(self):
        # https://cddis.nasa.gov/archive/gnss/products/2100/emr21000.sp3.Z
        product = sp3.Product.from_file(dirname / "test_products" / "emr21000.sp3")
        self.assertEqual(product.version, sp3.Version.C)
        self.assertEqual(product.file_type, sp3.FileType.GPS)
        self.assertEqual(product.time_system, sp3.timesystem.TimeSystem.GPS)
        self.assertEqual(product.data_used, b"U")
        self.assertEqual(product.coordinate_system, b"IGS14")
        self.assertEqual(product.orbit_type, b"FIT")
        self.assertEqual(product.agency, b"EMR")
        self.assertListEqual(
            product.comments,
            [
                b"CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
                b"CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
                b"CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
                b"PCV:IGS14_1935 OL/AL:FES2004  NONE     YN ORB:CoN CLK:CoN",
            ],
        )
        self.assertEqual(len(product.satellites), 32)
        for satellite in product.satellites:
            self.assertEqual(len(satellite.records), 96)
        self.assertEqual(product.satellites[0].id, b"G01")
        self.assertEqual(
            product.satellites[0].records[0].time.isoformat(),
            "2020-04-04T23:59:42+00:00",
        )
        self.assertVectorEqual(
            product.satellites[0].records[0].position,
            (21163886.281, 13420060.103, 9081657.071),
        )
        self.assertRelativeAlmostEqual(
            product.satellites[0].records[0].clock, -0.000348529159  # type: ignore
        )
        self.assertEqual(
            product.satellites[0].records[-1].time.isoformat(),
            "2020-04-05T23:44:42+00:00",
        )
        self.assertVectorEqual(
            product.satellites[0].records[-1].position,
            (20683557.342, 12721489.456, 10936561.064),
        )
        self.assertRelativeAlmostEqual(
            product.satellites[0].records[-1].clock, -0.000349505066  # type: ignore
        )
        self.assertEqual(product.satellites[-1].id, b"G32")
        self.assertEqual(
            product.satellites[-1].records[0].time.isoformat(),
            "2020-04-04T23:59:42+00:00",
        )
        self.assertVectorEqual(
            product.satellites[-1].records[0].position,
            (-14732619.696, 15325155.155, 15908182.296),
        )
        self.assertRelativeAlmostEqual(
            product.satellites[-1].records[0].clock, 0.000252210148  # type: ignore
        )
        self.assertEqual(
            product.satellites[-1].records[-1].time.isoformat(),
            "2020-04-05T23:44:42+00:00",
        )
        self.assertVectorEqual(
            product.satellites[-1].records[-1].position,
            (-13358975.068, 15143246.089, 17254577.670),
        )
        self.assertRelativeAlmostEqual(
            product.satellites[-1].records[-1].clock, 0.000252946982  # type: ignore
        )

    def test_nsgf_orb_ajisai_211220_v00(self):
        # https://cddis.nasa.gov/archive/slr/products/orbits/ajisai/211220/nsgf.orb.ajisai.211220.v00.sp3.gz
        product = sp3.Product.from_file(
            dirname / "test_products" / "nsgf.orb.ajisai.211220.v00.sp3"
        )
        self.assertEqual(product.version, sp3.Version.C)
        self.assertEqual(product.file_type, sp3.FileType.LEO)
        self.assertEqual(product.time_system, sp3.timesystem.TimeSystem.UTC)
        self.assertEqual(product.data_used, b"SLR")
        self.assertEqual(product.coordinate_system, b"ECF")
        self.assertEqual(product.orbit_type, b"FIT")
        self.assertEqual(product.agency, b"NSGF")
        self.assertListEqual(
            product.comments,
            [
                b"Earth-centered-fixed orbital predictions from SGF ILRS AC",
                b"The underlying ECF frame is that of IERS/ITRF",
                b"Note: Solution based on 4-day long arc",
            ],
        )
        self.assertEqual(len(product.satellites), 1)
        for satellite in product.satellites:
            self.assertEqual(len(satellite.records), 1478)
        self.assertEqual(product.satellites[0].id, b"L50")
        self.assertEqual(
            product.satellites[0].records[0].time.isoformat(),
            "2021-12-16T00:00:00+00:00",
        )
        self.assertVectorEqual(
            product.satellites[0].records[0].position,
            (-4586301.149, 2383308.229, 5926669.233),
        )
        self.assertVectorEqual(
            product.satellites[0].records[0].velocity,  # type: ignore
            (-2050.9432000, -6356.8161000, 976.0648100),
        )
        self.assertIsNone(product.satellites[0].records[0].clock)
        self.assertEqual(
            product.satellites[0].records[-1].time.isoformat(),
            "2021-12-20T02:28:00+00:00",
        )
        self.assertVectorEqual(
            product.satellites[0].records[-1].position,
            (-4568661.503, 3087193.619, 5610808.976),
        )
        self.assertVectorEqual(
            product.satellites[0].records[-1].velocity,  # type: ignore
            (-5109.7022000, -3939.3079000, -1982.5136000),
        )
        self.assertIsNone(product.satellites[0].records[-1].clock)

    def test_igr21882(self):
        # https://cddis.nasa.gov/archive/gnss/products/2188/igr21882.sp3.Z
        product = sp3.Product.from_file(dirname / "test_products" / "igr21882.sp3")
        self.assertEqual(product.version, sp3.Version.C)
        self.assertEqual(product.file_type, sp3.FileType.GPS)
        self.assertEqual(product.time_system, sp3.timesystem.TimeSystem.GPS)
        self.assertEqual(product.data_used, b"ORBIT")
        self.assertEqual(product.coordinate_system, b"IGb14")
        self.assertEqual(product.orbit_type, b"HLM")
        self.assertEqual(product.agency, b"IGS")
        self.assertListEqual(
            product.comments,
            [
                b"RAPID ORBIT COMBINATION FROM WEIGHTED AVERAGE OF:",
                b"cod emr esa gfz jpl ngs sio usn whu",
                b"REFERENCED TO IGS TIME (IGST) AND TO WEIGHTED MEAN POLE:",
                b"PCV:IGS14_2186 OL/AL:FES2004  NONE     Y  ORB:CMB CLK:CMB",
            ],
        )
        self.assertEqual(len(product.satellites), 32)
        for satellite in product.satellites:
            self.assertEqual(len(satellite.records), 96)
        self.assertEqual(product.satellites[0].id, b"G01")
        self.assertEqual(
            product.satellites[0].records[0].time.isoformat(),
            "2021-12-13T23:59:42+00:00",
        )
        self.assertVectorEqual(
            product.satellites[0].records[0].position,
            (12439850.240, -21691270.701, -8699268.697),
        )
        self.assertRelativeAlmostEqual(
            product.satellites[0].records[0].clock, 0.000484801109  # type: ignore
        )
        self.assertEqual(
            product.satellites[0].records[-1].time.isoformat(),
            "2021-12-14T23:44:42+00:00",
        )
        self.assertVectorEqual(
            product.satellites[0].records[-1].position,
            (11796938.686, -21224988.119, -10617300.036),
        )
        self.assertRelativeAlmostEqual(
            product.satellites[0].records[-1].clock, 0.000483931034  # type: ignore
        )
        self.assertEqual(product.satellites[-1].id, b"G32")
        self.assertEqual(
            product.satellites[-1].records[0].time.isoformat(),
            "2021-12-13T23:59:42+00:00",
        )
        self.assertVectorEqual(
            product.satellites[-1].records[0].position,
            (15677566.080, 16199844.556, -14073948.839),
        )
        self.assertRelativeAlmostEqual(
            product.satellites[-1].records[0].clock, -0.000034780613  # type: ignore
        )
        self.assertEqual(
            product.satellites[-1].records[-1].time.isoformat(),
            "2021-12-14T23:44:42+00:00",
        )
        self.assertVectorEqual(
            product.satellites[-1].records[-1].position,
            (15454109.950, 14960247.378, -15586329.017),
        )
        self.assertRelativeAlmostEqual(
            product.satellites[-1].records[-1].clock, -0.000035242731  # type: ignore
        )

    def test_esa0mgnfin_20213460000_01d_05m_orb(self):
        # http://navigation-office.esa.int/products/gnss-products/2188/ESA0MGNFIN_20213460000_01D_05M_ORB.SP3.gz
        product = sp3.Product.from_file(
            dirname / "test_products" / "ESA0MGNFIN_20213460000_01D_05M_ORB.SP3"
        )
        self.assertEqual(product.version, sp3.Version.D)
        self.assertEqual(product.file_type, sp3.FileType.MIXED)
        self.assertEqual(product.time_system, sp3.timesystem.TimeSystem.GPS)
        self.assertEqual(product.data_used, b"ORBIT")
        self.assertEqual(product.coordinate_system, b"ITRF")
        self.assertEqual(product.orbit_type, b"BHN")
        self.assertEqual(product.agency, b"ESOC")
        self.assertListEqual(
            product.comments,
            [
                b"CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
                b"CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
                b"CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
                b"PCV:IGS        OL/AL:EOT11A   NONE     YN ORB:CoN CLK:CoN",
            ],
        )
        self.assertEqual(len(product.satellites), 116)
        for satellite in product.satellites:
            self.assertEqual(len(satellite.records), 289)
        self.assertEqual(product.satellites[0].id, b"G13")
        self.assertEqual(
            product.satellites[0].records[0].time.isoformat(),
            "2021-12-11T23:59:42+00:00",
        )
        self.assertVectorEqual(
            product.satellites[0].records[0].position,
            (-13462439.424, 8521400.998, 21070022.207),
        )
        self.assertRelativeAlmostEqual(
            product.satellites[0].records[0].clock, 0.000228071998  # type: ignore
        )
        self.assertEqual(
            product.satellites[0].records[-1].time.isoformat(),
            "2021-12-12T23:59:42+00:00",
        )
        self.assertVectorEqual(
            product.satellites[0].records[-1].position,
            (-13576824.587, 7863384.875, 21253921.516),
        )
        self.assertRelativeAlmostEqual(
            product.satellites[0].records[-1].clock, 0.000228574284  # type: ignore
        )
        self.assertEqual(product.satellites[-1].id, b"J04")
        self.assertEqual(
            product.satellites[-1].records[0].time.isoformat(),
            "2021-12-11T23:59:42+00:00",
        )
        self.assertVectorEqual(
            product.satellites[-1].records[0].position,
            (-25955007.071, 27861480.331, 24376352.859),
        )
        self.assertRelativeAlmostEqual(
            product.satellites[-1].records[0].clock, 0.000109181452  # type: ignore
        )
        self.assertEqual(
            product.satellites[-1].records[-1].time.isoformat(),
            "2021-12-12T23:59:42+00:00",
        )
        self.assertVectorEqual(
            product.satellites[-1].records[-1].position,
            (-26000797.533, 27896444.575, 24260130.997),
        )
        self.assertRelativeAlmostEqual(
            product.satellites[-1].records[-1].clock, 0.000110384373  # type: ignore
        )


if __name__ == "__main__":
    unittest.main()
