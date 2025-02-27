import os
from setuptools import setup, find_packages

this_directory = os.path.abspath(os.path.dirname(__file__))
try:
    with open(os.path.join(this_directory, "README.md"), encoding="utf-8") as f:
        long_description = f.read()
except FileNotFoundError:
    long_description = ""

setup(
    name="simple-fast-grpc",
    version="0.0.1",
    description="Fast to Code gRPC in Python with FastAPI generator for testing your code. Fork of FastGRPC with dependency injection, middlewares and handling exception",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Leraner",
    author_email="legend.tony@yandex.ru",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.9",
    install_requires=[
        "APScheduler>=3.11.0",
        "protobuf>=5.29.3",
        "grpcio>=1.70.0",
        "grpcio-tools>=1.68.1",
        "pydantic>=2.10.5,<3.0.0",
        "logzero>=1.7.0,<2.0.0",
        "jinja2>=3.1.5,<4.0.0",
        "fastapi>=0.115.8",
        "uvicorn>=0.34.0",
        "typer>=0.15.1",
    ],
    extras_require={
        "dev": [
            "ruff==0.2.0",
            "mypy>=1.14.1,<2.0.0",
            "pytest>=8.3.4,<9.0.0",
            "pytest-asyncio>=0.23.8,<0.24.0",
            "pytest-mock>=3.14.0,<4.0.0",
            "ipython==8.0",
            "aiosqlite>=0.20.0,<0.21.0",
            "mkdocs>=1.6.1,<2.0.0",
            "mkdocs-material>=9.5.49,<10.0.0",
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
)
