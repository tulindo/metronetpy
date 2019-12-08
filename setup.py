import setuptools

with open("README.md", "r") as fh:
    LONG_DESCRIPTION = fh.read()

VERSION = {}
with open("metronetpy/__version__.py") as fh:
    exec(fh.read(), VERSION)

setuptools.setup(
    name="metronetpy",
    version=VERSION["__version__"],
    author="Paolo Tuninetto",
    author_email="paolo.tuninetto@gmail.com",
    description="Python Package for programmatically controlling Security and "
    + "Intrusion systems made by IESS",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    url="https://github.com/tulindo/metronetpy",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
    ],
    python_requires=">=3.7",
    install_requires=["requests", "yaml", "sslkeylog"],
    scripts=["metronet"],
)
