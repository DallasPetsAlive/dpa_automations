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
