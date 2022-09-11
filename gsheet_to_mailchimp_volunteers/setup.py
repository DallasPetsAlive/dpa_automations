from setuptools import setup

setup(
    name="gsheet_to_mailchimp_volunteers",
    version="1.0",
    description="sync volunteers from gsheet to mailchimp",
    license="MIT",
    author="Katie Patterson",
    author_email="katie@dallaspetsalive.org",
    packages=["gsheet_to_mailchimp_volunteers"],
    install_requires=[
        "google-api-python-client",
        "google-auth-httplib2",
        "google-auth-oauthlib",
        "requests",
    ],
)
