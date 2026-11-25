"""Boolean options survive both in-memory and DB-string config round trips."""
import pytest

from spiderfoot.sflib.config import configSerialize, configUnserialize


@pytest.mark.parametrize("db_strings", [False, True], ids=["memory", "db-strings"])
@pytest.mark.parametrize("enabled", [False, True])
def test_boolean_round_trip(enabled, db_strings):
    def config(value):
        return {"flag": value, "__modules__": {"example": {"opts": {"flag": value}}}}

    expected = config(enabled)
    stored = configSerialize(expected)
    if db_strings:
        stored = {key: str(value) for key, value in stored.items()}

    restored = configUnserialize(stored, config(not enabled))
    assert restored["flag"] is enabled
    assert restored["__modules__"]["example"]["opts"]["flag"] is enabled
