from setuptools import setup, find_packages

setup(
    name="rose-bag",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "textual>=0.40.0",
        "rosbags>=0.9.16",
        "rich>=13.0.0",
        "typer>=0.9.0",
        "pydantic>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "rose=roseApp.rose:cli",
        ],
    },
    package_data={
        "roseApp": ["style.tcss", "config.json"],
    },
) 