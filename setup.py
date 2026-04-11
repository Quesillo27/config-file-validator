from setuptools import setup, find_packages

setup(
    name="config-file-validator",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.1",
        "rich>=13.0",
        "PyYAML>=6.0",
        "jsonschema>=4.0",
        "python-dotenv>=1.0",
    ],
    entry_points={
        "console_scripts": [
            "cfv=src.cli:main",
        ],
    },
)
