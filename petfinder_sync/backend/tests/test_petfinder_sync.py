from backend import petfinder_sync


def test_handler():
    assert petfinder_sync.handler(None, None) is None
