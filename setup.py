from setuptools import setup, find_packages

setup(
    name="cc_converter",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["python-docx", "requests"],
    entry_points={
        "console_scripts": [
            "cc-convert=cc_converter.cli:main",
        ],
    },
) 