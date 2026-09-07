from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="sgrna-analyzer",
    version="2.1.0",
    author="许逸伦",
    description="自动化sgRNA文库测序结果分析工具（Windows 原生版）",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "sgrna_analyzer": ["templates/*"],
    },
    install_requires=[
        "matplotlib>=3.7.0",
        "numpy>=1.24.0",
        "jinja2>=3.1.0",
        "openpyxl>=3.1.0",
    ],
    entry_points={
        "console_scripts": [
            "sgrna-analyze=sgrna_analyzer.cli:main",
        ],
    },
    python_requires=">=3.9",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
    ],
)
