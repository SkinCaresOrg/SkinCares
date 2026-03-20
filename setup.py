from setuptools import setup, find_packages
from pathlib import Path

# version
here = Path(__file__).absolute().parent
version_data = {}
with open(here.joinpath("skincarelib", "__init__.py"), "r") as f:
    exec(f.read(), version_data)
version = version_data.get("__version__", "0.0")

install_requires = [
    "numpy>=1.21,<2",
    "pandas>=2,<3",
    "scikit-learn>=1.2,<2",
    "scipy>=1.8,<2",
    "joblib>=1.2,<2",
    "vowpalwabbit>=9.0,<10",
]

extras_require = {
    "dev": [
        "pytest>=7.0,<9",
        "ruff>=0.6,<1",
        "pre-commit>=3.7,<5",
        "ipykernel>=6,<7",
        "jupyter>=1,<2",
    ],
    "vw": [
        "vowpalwabbit>=9.0,<10",
    ],
    "scraping": [
        "requests>=2.31,<3",
        "beautifulsoup4>=4.12,<5",
        "urllib3>=2,<3",
    ],
}

setup(
    name="skincarelib",
    version=version,
    install_requires=install_requires,
    extras_require=extras_require,
    package_dir={"skincarelib": "skincarelib"},
    python_requires=">=3.9",
    packages=find_packages(where=".", exclude=["docs", "examples", "tests"]),
)
