import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="metronetpy-tulindo",
    version="0.0.2",
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
    ],
    python_requires='>=3.6',
)
