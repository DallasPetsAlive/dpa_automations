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
