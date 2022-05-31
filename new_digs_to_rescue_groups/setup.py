from setuptools import setup

setup(
    name="new_digs_to_rescue_groups",
    version="1.0",
    description="sync new digs to rescuegroups.org",
    license="MIT",
    author="Katie Patterson",
    author_email="katie@dallaspetsalive.org",
    packages=["new_digs_to_rescue_groups"],
    install_requires=["requests"],
)
