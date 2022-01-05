import setuptools
import sys

with open("README.md") as file:
    long_description = file.read()

setuptools.setup(
    name="sp3",
    version="0.0.2",
    url="https://github.com/neuromorphicsystems/sp3",
    author="Alexandre Marcireau",
    author_email="alexandre.marcireau@gmail.com",
    description="Download and interpolate precise satellite ephemeris (SP3)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=[
        "astropy >= 4.0",
        "numpy >= 1.20",
        "requests >= 2.0",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    packages=["sp3"],
    package_data={"": ["*.json"]},
)
