from app.main import is_duplicate_update


def test_is_duplicate_update():
    assert is_duplicate_update(1) is False
    assert is_duplicate_update(1) is True
    assert is_duplicate_update(2) is False
    assert is_duplicate_update(None) is False





