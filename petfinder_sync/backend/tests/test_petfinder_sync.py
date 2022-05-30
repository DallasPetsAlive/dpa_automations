from backend import petfinder_sync


def test_handler() -> None:
    petfinder_sync.handler({}, None)
