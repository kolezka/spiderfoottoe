from spiderfoot.tasks.maintenance import database_vacuum


def test_vacuum_without_dsn_reports_configuration_error(monkeypatch):
    monkeypatch.delenv("SF_POSTGRES_DSN", raising=False)

    assert database_vacuum.run() == {
        "status": "error",
        "message": "SF_POSTGRES_DSN not configured",
    }
