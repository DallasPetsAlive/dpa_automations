from botocore.stub import Stubber
import json
import requests_mock

from wordpress_pet_sync import wordpress_pet_sync


def test_get_token():
    with Stubber(wordpress_pet_sync.secrets_client) as stub:
        expected_params = {
            "SecretId": "wordpress_credentials",
        }
        stub.add_response(
            "get_secret_value",
            {
                "SecretString": json.dumps(
                    {
                        "username": "abc",
                        "password": "def",
                    }
                )
            },
            expected_params,
        )

        with requests_mock.Mocker() as requests_mocker:
            requests_mocker.post(
                "https://dallaspetsalive.org/wp-json/api/v1/token",
                text=json.dumps({"jwt_token": "1234"}),
            )

            sync = wordpress_pet_sync.WordpressSync()
            sync.get_token()

            stub.assert_no_pending_responses()
            assert requests_mocker.call_count == 1

            assert sync.token == "1234"


def test_get_dynamodb_pets():
    with Stubber(wordpress_pet_sync.dynamodb_client) as stub:
        first_scan_response = {
            "Items": [
                {
                    "source": {"S": "shelterluv"},
                    "name": {"S": "Socks"},
                },
                {
                    "source": {"S": "airtable"},
                    "name": {"S": "Fido"},
                },
            ],
            "LastEvaluatedKey": {
                "source": {"S": "airtable"},
                "name": {"S": "Fido"},
            },
        }
        first_expected_params = {
            "TableName": "Pets",
            "IndexName": "SyncIndex",
        }
        stub.add_response("scan", first_scan_response, first_expected_params)

        second_scan_response = {
            "Items": [
                {
                    "source": {"S": "airtable"},
                    "name": {"S": "Petey"},
                },
                {
                    "source": {"S": "shelterluv"},
                    "name": {"S": "Joey"},
                },
            ],
        }
        second_expected_params = {
            "TableName": "Pets",
            "IndexName": "SyncIndex",
            "ExclusiveStartKey": {
                "source": {"S": "airtable"},
                "name": {"S": "Fido"},
            },
        }

        stub.add_response("scan", second_scan_response, second_expected_params)

        sync = wordpress_pet_sync.WordpressSync()
        sync.get_dynamodb_pets()

        stub.assert_no_pending_responses()
        assert sync.dynamodb_pets == [
            {"source": "shelterluv", "name": "Socks"},
            {"source": "airtable", "name": "Fido"},
            {"source": "airtable", "name": "Petey"},
            {"source": "shelterluv", "name": "Joey"},
        ]


def test_get_wordpress_pets():
    with requests_mock.Mocker() as requests_mocker:
        requests_mocker.get(
            "https://dallaspetsalive.org/wp-json/wp/v2/pet?offset=0",
            text=json.dumps([{"name": "Fido"}]),
        )
        requests_mocker.get(
            "https://dallaspetsalive.org/wp-json/wp/v2/pet?offset=1",
            text=json.dumps([]),
        )

        sync = wordpress_pet_sync.WordpressSync()
        sync.token = "token"
        sync.get_wordpress_pets()

        assert requests_mocker.call_count == 2

        assert sync.wordpress_pets == [{"name": "Fido"}]


def test_delete_pets():
    with requests_mock.Mocker() as requests_mocker:
        requests_mocker.delete(
            "https://dallaspetsalive.org/wp-json/wp/v2/pet/abc?force=true",
        )

        sync = wordpress_pet_sync.WordpressSync()
        sync.token = "token"
        sync.dynamodb_ids = ["Z", "Y", "X", "W"]
        sync.wordpress_ids = ["Z", "Y", "A", "X"]
        sync.wordpress_pets = [
            {
                "id": "1",
                "metadata": {
                    "id": "Z",
                },
            },
            {
                "id": "2",
                "metadata": {
                    "id": "Y",
                },
            },
            {
                "id": "abc",
                "metadata": {
                    "id": "A",
                },
            },
            {
                "id": "4",
                "metadata": {
                    "id": "X",
                },
            },
        ]
        sync.delete_pets()

        assert requests_mocker.call_count == 1


def test_thing():
    sync = wordpress_pet_sync.WordpressSync()
    sync.get_token()
    sync.get_dynamodb_pets()
    sync.get_wordpress_pets()
    # sync.delete_pets()
    sync.create_pets()

    assert 0
