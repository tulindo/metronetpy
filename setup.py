import os
import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

version = {}
with open("metronetpy/__version__.py") as fh:
    exec(fh.read(), version)

setuptools.setup(
    name="metronetpy",
    version=version["__version__"],
    author="Paolo Tuninetto",
    author_email="paolo.tuninetto@gmail.com",
    description="Python Package for programmatically controlling Security and Intrusion systems made by IESS",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tulindo/metronetpy",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
    ],
    python_requires=">=3.7",
    install_requires=["hyper","sslkeylog"],
    scripts=["metronet"],
)
