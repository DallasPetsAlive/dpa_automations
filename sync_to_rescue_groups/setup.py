from setuptools import setup

setup(
    name="sync_to_rescue_groups",
    version="1.0",
    description="sync new digs and shelterluv to rescuegroups.org",
    license="MIT",
    author="Katie Patterson",
    author_email="katie@dallaspetsalive.org",
    packages=["sync_to_rescue_groups"],
    install_requires=["requests"],
)
