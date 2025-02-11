from setuptools import setup, find_packages
import os

# Read the contents of README.md
with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="rose-bag",
    version="0.1.1",
    author="Lingfeng_ai",
    author_email="hanxiaomax@qq.com",  # Please update with your email
    description="A modern TUI tool for ROS bag file analysis and visualization",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hanxiaomax/rose",  # Please update with your repository URL
    packages=find_packages(),
    include_package_data=True,
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
        "roseApp": [
            "style.tcss",
            "config.json",
            "themes/*.py",
            "whitelists/*",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Visualization",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    keywords="ros, bag, tui, visualization, robotics",
) 