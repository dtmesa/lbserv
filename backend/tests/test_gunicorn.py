import runpy
from pathlib import Path

from app.config import Settings

CONF = Path(__file__).resolve().parents[1] / "gunicorn.conf.py"
LISTEN_PER_WORKER = 1
MANAGED_PG_1GIB_BACKEND_CONNECTIONS = 22


def test_gunicorn_config_uses_uvicorn_workers(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PORT", "9999")
    monkeypatch.setenv("WEB_CONCURRENCY", "3")
    conf = runpy.run_path(str(CONF))
    assert conf["worker_class"] == "uvicorn_worker.UvicornWorker"
    assert conf["bind"] == "0.0.0.0:9999"
    assert conf["workers"] == 3
    assert conf["preload_app"] is False
    __import__("uvicorn_worker")


def test_default_connection_budget_fits_1gib_node_during_deploy(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
    workers = runpy.run_path(str(CONF))["workers"]
    settings = Settings()
    per_instance = workers * (LISTEN_PER_WORKER + settings.db_pool_size + settings.db_max_overflow)
    old_and_new_instances_plus_migrate_job = 2 * per_instance + 1
    assert old_and_new_instances_plus_migrate_job <= MANAGED_PG_1GIB_BACKEND_CONNECTIONS
