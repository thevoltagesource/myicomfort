import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="myicomfort",
    version="0.1.6",
    author="Jacob Southard",
    author_email="jacob@thevoltagesource.com",
    description="API Wrapper for myicomfort.com",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/thevoltagesource/myicomfort",
    packages=['myicomfort'],
    install_requires=[
        'logging',
        'requests'
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)