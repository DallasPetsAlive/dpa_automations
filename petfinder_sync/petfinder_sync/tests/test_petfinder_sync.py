from typing import Any, Dict

import pytest
import requests

from petfinder_sync import petfinder_sync


def test_get_shelterluv_pets(requests_mock: Any) -> None:
    json_response: Dict[str, Any] = {
        "success": 1,
        "animals": [
            {
                "ID": "1",
                "Name": "Fido",
            }
        ],
        "total_count": 1,
        "has_more": False,
    }

    requests_mock.get(
        "https://www.shelterluv.com/api/v1/animals?status_type=publishable",
        json=json_response,
    )

    animals = petfinder_sync.get_shelterluv_pets("")

    assert animals.__len__() == 1
    assert animals["1"] == {"ID": "1", "Name": "Fido"}


def test_get_shelterluv_pets_length_mismatch(requests_mock: Any) -> None:
    json_response: Dict[str, Any] = {
        "success": 1,
        "animals": [
            {
                "ID": "1",
                "Name": "Fido",
            }
        ],
        "total_count": 0,
        "has_more": False,
    }

    requests_mock.get(
        "https://www.shelterluv.com/api/v1/animals?status_type=publishable",
        json=json_response,
    )

    with pytest.raises(requests.RequestException):
        petfinder_sync.get_shelterluv_pets("")


def test_get_airtable_pets(requests_mock: Any) -> None:
    json_response: Dict[str, Any] = {
        "records": [
            {
                "id": "2",
                "fields": {
                    "Name": "Daisy",
                    "Status": "Published - Available",
                },
            },
        ],
    }

    requests_mock.get(
        "https://api.airtable.com/v0/6543/Pets",
        json=json_response,
    )

    animals = petfinder_sync.get_airtable_pets(
        {
            "BASE": "6543",
            "AIRTABLE_API_KEY": "",
        }
    )

    assert animals.__len__() == 1
    assert animals["2"] == {
        "Name": "Daisy",
        "Status": "Published - Available",
    }


@pytest.mark.parametrize(
    "type, color, first_color, second_color",
    [
        ("Dog", "Grey", "Gray / Blue / Silver", ""),
        ("Dog", "Sable\\/None", "Sable", ""),
        ("Dog", "Black\\/Cream", "Black", "White / Cream"),
        ("Cat", "Blue\\/White", "Gray / Blue / Silver", "White"),
        ("Dog", "Gook\\/Blah", "", ""),
        ("Person", "Black", "", ""),
    ],
)
def test_get_color_from_shelterluv(
    type: str, color: str, first_color: str, second_color: str
) -> None:
    color_one, color_two = petfinder_sync.get_colors_from_shelterluv(color, type)
    assert color_one == first_color
    assert color_two == second_color


def test_get_photos_from_shelterluv() -> None:
    fields = {
        "CoverPhoto": "coverphoto",
        "Photos": [
            "onephoto",
            "coverphoto",
            "twophoto",
        ],
    }
    photos = petfinder_sync.get_photos_from_shelterluv(fields)
    assert len(photos) >= 6

    assert photos[0] == "coverphoto"
    assert photos[1] == "onephoto"
    assert photos[2] == "twophoto"
    assert photos[3] == ""
    assert photos[4] == ""
    assert photos[5] == ""


def test_get_special_needs_from_shelterluv():
    fields = {
        "Attributes": [
            {
                "Internal-ID": "67626",
            },
            {
                "Internal-ID": "7320",
            },
        ],
    }

    needs, needs_notes = petfinder_sync.get_special_needs_from_shelterluv(fields)

    assert needs == "1"
    assert needs_notes == "Diabetic, FIV+"


def test_get_special_needs_from_shelterluv_none():
    fields = {
        "Attributes": [
            {
                "Internal-ID": "1",
            }
        ],
    }

    needs, needs_notes = petfinder_sync.get_special_needs_from_shelterluv(fields)

    assert needs == ""
    assert needs_notes == ""


@pytest.mark.parametrize(
    "id, expected",
    [("1", ""), ("7319", "1")],
)
def test_get_declawed_from_shelterluv(id, expected):
    fields = {
        "Attributes": [
            {
                "Internal-ID": id,
            }
        ],
    }

    assert petfinder_sync.get_declawed_from_shelterluv(fields) == expected


@pytest.mark.parametrize(
    "id, expected",
    [("1", ""), ("14839", "1")],
)
def test_get_housebroken_from_shelterluv(id, expected):
    fields = {
        "Attributes": [
            {
                "Internal-ID": id,
            }
        ],
    }

    assert petfinder_sync.get_housebroken_from_shelterluv(fields) == expected


@pytest.mark.parametrize(
    "id, expected",
    [("1", ""), ("14842", "0"), ("14837", "1")],
)
def test_get_no_dogs_from_shelterluv(id, expected):
    fields = {
        "Attributes": [
            {
                "Internal-ID": id,
            }
        ],
    }

    assert petfinder_sync.get_no_dogs_from_shelterluv(fields) == expected


@pytest.mark.parametrize(
    "id, expected",
    [("1", ""), ("14820", "0"), ("17159", "1")],
)
def test_get_no_cats_from_shelterluv(id, expected):
    fields = {
        "Attributes": [
            {
                "Internal-ID": id,
            }
        ],
    }

    assert petfinder_sync.get_no_cats_from_shelterluv(fields) == expected


@pytest.mark.parametrize(
    "id, expected",
    [("1", ""), ("14840", "0"), ("53437", "1")],
)
def test_get_no_kids_from_shelterluv(id, expected):
    fields = {
        "Attributes": [
            {
                "Internal-ID": id,
            }
        ],
    }

    assert petfinder_sync.get_no_kids_from_shelterluv(fields) == expected


@pytest.mark.parametrize(
    "months, expected",
    [(1, "Baby"), (9, "Young"), (20, "Adult"), (130, "Senior")],
)
def test_get_age_from_shelterluv(months, expected):
    assert petfinder_sync.get_age_from_shelterluv(months) == expected


@pytest.mark.parametrize(
    "size, expected",
    [
        ("Small (1-20)", "S"),
        ("Medium some", "M"),
        ("Large 1234", "L"),
        ("Extra-Large yes", "XL"),
        ("", "M"),
    ],
)
def test_get_size_from_shelterluv(size, expected):
    assert petfinder_sync.get_size_from_shelterluv(size) == expected


@pytest.mark.parametrize(
    "type, expected",
    [
        ("Dog", "Dog"),
        ("Small mammal", "Small & Furry"),
        ("Large mammal", "Barnyard"),
        ("Exotic/Other", "Scales, Fins & Other"),
    ],
)
def test_get_type_from_shelterluv(type, expected):
    assert petfinder_sync.get_type_from_shelterluv(type) == expected


@pytest.mark.parametrize(
    "breed, type, expected",
    [
        ("Chihuahua, Long Coat", "Dog", ("Chihuahua", "")),
        ("Chihuahua\\/Devil", "Dog", ("Chihuahua", "Mix")),
        ("Terrier, Rat\\/Collie, Bearded", "Dog", ("Rat Terrier", "Bearded Collie")),
        ("Monkey", "Dog", ("Mixed Breed", "Mix")),
        ("Domestic Longhair", "Cat", ("Domestic Long Hair", "")),
        ("Siamese\\/Panther", "Cat", ("Siamese", "Mix")),
        ("Pixie-Bob\\/Sphynx", "Cat", ("Pixiebob", "Sphynx / Hairless Cat")),
        ("Tiger", "Cat", ("Domestic Short Hair", "Mix")),
    ],
)
def test_get_breed_from_shelterluv(breed, type, expected):
    assert petfinder_sync.get_breed_from_shelterluv(breed, type) == expected


def test_shelterluv_to_petfinder_conversion():
    shelterluv_pets = {
        "1234": {
            "Name": "Nacho",
            "Type": "Dog",
            "Sex": "Male",
            "Breed": "Chihuahua\\/Pug",
            "Size": "Small",
            "Age": 40,
            "Description": "This is\na description",
            "Altered": "Yes",
            "Attributes": [
                {
                    "Internal-ID": "67626",
                },
            ],
            "CoverPhoto": "bigphoto",
            "Photos": [
                "anotherphoto",
                "bigphoto",
            ],
            "LastIntakeUnixTime": "1644295379",
            "DOBUnixTime": "1579063379",
            "AdoptionFeeGroup": {
                "Price": "100",
            },
            "Color": "Brown\\/None",
        },
        "567": {
            "Name": "Minnie",
            "Type": "Cat",
            "Sex": "Female",
            "Breed": "Domestic Shorthair",
            "Size": "Large",
            "Age": 2,
            "Description": "This is\na description\nas well",
            "Altered": "",
            "Attributes": [],
            "CoverPhoto": "",
            "Photos": [],
            "LastIntakeUnixTime": "1654576979",
            "DOBUnixTime": "1651898579",
            "AdoptionFeeGroup": {
                "Price": "200",
            },
            "Color": "Seal\\/None",
        },
    }

    result_pets = petfinder_sync.shelterluv_to_csv(shelterluv_pets)

    assert len(result_pets) == 2

    assert result_pets[0] == {
        "ID": "DPA-A-1234",
        "Internal": "",
        "AnimalName": "Nacho",
        "PrimaryBreed": "Chihuahua",
        "SecondaryBreed": "Pug",
        "Sex": "M",
        "Size": "S",
        "Age": "Adult",
        "Desc": "This is&#10;a description",
        "Type": "Dog",
        "Status": "A",
        "Shots": "1",
        "Altered": "1",
        "NoDogs": "",
        "NoCats": "",
        "NoKids": "",
        "Housetrained": "",
        "Declawed": "",
        "specialNeeds": "1",
        "Mix": "",
        "photo1": "bigphoto",
        "photo2": "anotherphoto",
        "photo3": "",
        "photo4": "",
        "photo5": "",
        "photo6": "",
        "arrival_date": "2022-02-07",
        "birth_date": "2020-01-14",
        "primaryColor": "Brown / Chocolate",
        "secondaryColor": "",
        "tertiaryColor": "",
        "coat_length": "",
        "adoption_fee": 100,
        "display_adoption_fee": "1",
        "adoption_fee_waived": "0",
        "special_needs_notes": "Diabetic",
        "no_other": "",
        "no_other_note": "",
        "tags": "",
    }
    assert result_pets[1] == {
        "ID": "DPA-A-567",
        "Internal": "",
        "AnimalName": "Minnie",
        "PrimaryBreed": "Domestic Short Hair",
        "SecondaryBreed": "",
        "Sex": "F",
        "Size": "L",
        "Age": "Baby",
        "Desc": "This is&#10;a description&#10;as well",
        "Type": "Cat",
        "Status": "A",
        "Shots": "1",
        "Altered": "",
        "NoDogs": "",
        "NoCats": "",
        "NoKids": "",
        "Housetrained": "",
        "Declawed": "",
        "specialNeeds": "",
        "Mix": "",
        "photo1": "",
        "photo2": "",
        "photo3": "",
        "photo4": "",
        "photo5": "",
        "photo6": "",
        "arrival_date": "2022-06-06",
        "birth_date": "2022-05-06",
        "primaryColor": "Seal Point",
        "secondaryColor": "",
        "tertiaryColor": "",
        "coat_length": "",
        "adoption_fee": 200,
        "display_adoption_fee": "1",
        "adoption_fee_waived": "0",
        "special_needs_notes": "",
        "no_other": "",
        "no_other_note": "",
        "tags": "",
    }
