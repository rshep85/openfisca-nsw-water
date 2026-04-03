from setuptools import setup, find_packages

setup(
    name="openfisca-nsw-water",
    version="0.1.0",
    description="OpenFisca package encoding NSW water management rules",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="NSW Water Team",
    license="AGPL-3.0",
    url="https://github.com/your-org/openfisca-nsw-water",
    packages=find_packages(),
    install_requires=[
        "openfisca-nsw-base >= 0.4.0",
        "openfisca-core >= 35.0.0, < 36.0.0",
    ],
    extras_require={
        "dev": [
            "flake8 >= 6.0",
            "bump2version >= 1.0",
            "build >= 1.0",
            "twine >= 4.0",
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Programming Language :: Python :: 3.7",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    python_requires=">=3.7",
    entry_points={
        "openfisca.country_package": [
            "openfisca_nsw_water = openfisca_nsw_water",
        ],
    },
)
