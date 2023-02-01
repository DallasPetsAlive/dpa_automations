from setuptools import setup

test_deps = ["requests_mock"]
extras = {"test": test_deps}

setup(
    name="wordpress_pet_sync",
    version="1.0",
    description="sync pets from dynamodb to wordpress",
    license="MIT",
    author="Katie Patterson",
    author_email="katie@dallaspetsalive.org",
    packages=["wordpress_pet_sync"],
    install_requires=["cerealbox", "requests"],
    tests_requires=test_deps,
    extras_require=extras,
)
