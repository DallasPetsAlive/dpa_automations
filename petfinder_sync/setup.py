from setuptools import setup

setup(
    name="petfinder_sync",
    version="1.0",
    description="sync pets from shelterluv/airtable to petfinder",
    license="MIT",
    author="Katie Patterson",
    author_email="katie@dallaspetsalive.org",
    packages=["petfinder_sync"],
    install_requires=["requests"],
)
