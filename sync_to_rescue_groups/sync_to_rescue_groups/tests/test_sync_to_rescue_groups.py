"""Test Airtable to RescueGroups.org sync."""
import configparser
import csv

import pytest

from sync_to_rescue_groups.sync_to_rescue_groups import (
    CSV_HEADERS,
    create_csv_file,
    get_airtable_pets,
    upload_to_rescue_groups,
)

config = configparser.ConfigParser()
config.read("config.ini")

animals = [
    {
        "id": "1",
        "fields": {
            "Status": "Adopted",
        },
    },
    {
        "id": "2",
        "fields": {
            "Status": "Published - ",
            "Pet Species": "Alien",
        },
    },
    {
        "id": "3",
        "fields": {
            "Status": "Published - Available for Adoption",
            "Pet Species": "Dog",
            "Pet Name": "Fido",
            "Sex": "Male",
            "Pet Age": "Young",
            "Pet Size": "Large",
            "Coat Length": "Short",
            "Mixed Breed": "Unknown",
            "Breed - Dog": "Beagle",
            "Color - Dog": "Tan",
            "Okay with Dogs": "Yes",
            "Okay with Cats": "No",
            "Okay with Kids": "Unknown",
            "Housetrained": "Yes",
            "Altered": "Unknown",
            "Up-to-date on Shots etc": "No",
            "Public Description": "test dog notes\n\r",
            "Pictures": [
                {
                    "id": "attlWavzYDzYGGBwb",
                    "width": 171,
                    "height": 180,
                    "url": "https://dog.jpg",
                },
            ],
        },
    },
    {
        "id": "4",
        "fields": {
            "Status": "x Published - Available",
            "Pet Species": "Cat",
            "Pet Name": "Freya",
            "Sex": "Female",
            "Pet Age": "Adult",
            "Special Needs": "Yes",
            "Pet Size": "Small",
            "Coat Length": "Long",
            "Mixed Breed": "No",
            "Breed - Cat": "Calico",
            "Color - Cat": "White",
            "Okay with Dogs": "Unknown",
            "Okay with Cats": "Yes",
            "Okay with Kids": "No",
            "Declawed": "Yes",
            "Housetrained": "No",
            "Altered": "No",
            "Up-to-date on Shots etc": "Unknown",
            "Pictures": [
                {
                    "url": "https://cat1.jpg",
                },
                {
                    "url": "https://cat2.jpg",
                },
                {
                    "url": "https://cat3.jpg",
                },
                {
                    "url": "https://cat4.jpg",
                },
            ],
        },
    },
]


def test_get_pets(requests_mock):
    """Test getting pets from Airtable (mocked)."""
    records = {
        "records": [{"a thing": "a pet"}],
    }
    print(config.sections())
    url = "https://api.airtable.com/v0/" + config["airtable"]["BASE"] + "/Pets"
    requests_mock.get(url, json=records, status_code=200)

    pets = get_airtable_pets()
    assert len(pets) == 1
    assert pets[0]["a thing"] == "a pet"


def test_get_pets_error(requests_mock):
    """Test getting pets from Airtable with a mocked error."""
    records = {
        "records": [{"a thing": "a pet"}],
    }
    url = "https://api.airtable.com/v0/" + config["airtable"]["BASE"] + "/Pets"
    requests_mock.get(url, json=records, status_code=400)

    with pytest.raises(Exception):
        get_airtable_pets()


def test_get_pets_bad_data(requests_mock):
    """Test getting pets from Airtable with mocked bad data."""
    records = {
        "this is wrong": "nope",
    }
    url = "https://api.airtable.com/v0/" + config["airtable"]["BASE"] + "/Pets"
    requests_mock.get(url, json=records, status_code=200)

    with pytest.raises(KeyError):
        get_airtable_pets()


def test_csv_file():
    """Test creating a csv file with animals."""
    filename = create_csv_file(animals)
    assert filename == "newdigs.csv"

    with open(config["local"]["FILEPATH"] + filename, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = reader.__next__()

        assert header == CSV_HEADERS

        for row in reader:
            assert row[0] in ("3", "4")

            if row[0] == "3":
                assert row == [
                    "3",
                    "Available",
                    "",
                    "",
                    "Fido",
                    "Dog",
                    "Beagle",
                    "",
                    "Yes",
                    "Male",
                    "Yes",
                    "No",
                    "",
                    "",
                    "Yes",
                    "Young",
                    "",
                    "",
                    "Large",
                    "No",
                    "Tan",
                    "",
                    "Short",
                    "Yes",
                    "test dog notes<br /><br />",
                    "No",
                    "",
                    "",
                    "https://dog.jpg",
                    "",
                    "",
                    "",
                    "",
                ]

            else:
                assert row == [
                    "4",
                    "Available",
                    "",
                    "",
                    "Freya",
                    "Cat",
                    "Calico",
                    "",
                    "No",
                    "Female",
                    "",
                    "Yes",
                    "No",
                    "Yes",
                    "No",
                    "Adult",
                    "Yes",
                    "No",
                    "Small",
                    "",
                    "White",
                    "",
                    "Long",
                    "Yes",
                    "",
                    "No",
                    "",
                    "",
                    "https://cat1.jpg",
                    "https://cat2.jpg",
                    "https://cat3.jpg",
                    "https://cat4.jpg",
                    "",
                ]


def test_csv_file_empty():
    """Test creating a csv file when we have no pets."""
    empty_animals = [
        {
            "id": "1",
            "fields": {
                "Status": "Adopted",
            },
        },
        {
            "id": "2",
            "fields": {
                "Status": "Accepted, Published",
            },
        },
        {
            "id": "3",
            "fields": {
                "Status": "Accepted",
            },
        },
    ]
    filename = create_csv_file(empty_animals)
    assert filename == "newdigs.csv"

    with open(config["local"]["FILEPATH"] + filename, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = reader.__next__()

        assert header == CSV_HEADERS

        row_count = 0

        for row in reader:
            assert row_count == 0
            row_count += 1

            assert row[0] == "1"

            assert row == [
                "1",
                "Deleted",
                "",
                "",
                "Temporary Deleted Dog",
                "Dog",
                "Beagle",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "Tan",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ]

        assert row_count == 1


def test_ftp_upload(mocker):
    """Mock testing of FTP upload to rescuegroups."""
    ftp_constructor_mock = mocker.patch("ftplib.FTP")
    ftp_mock = ftp_constructor_mock.return_value

    upload_to_rescue_groups("newdigs.csv")

    ftp_constructor_mock.assert_called_with(
        "ftp.rescuegroups.org",
        config["rescuegroups"]["FTP_USERNAME"],
        config["rescuegroups"]["FTP_PASSWORD"],
    )
    assert ftp_mock.__enter__().storbinary.called
