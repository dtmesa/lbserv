from app.config import Settings


def test_digitalocean_url_is_normalized() -> None:
    s = Settings(database_url="postgresql://u:p@db.example:25060/defaultdb?sslmode=require")
    assert s.sqlalchemy_url == "postgresql+asyncpg://u:p@db.example:25060/defaultdb"
    assert s.asyncpg_dsn == "postgresql://u:p@db.example:25060/defaultdb"
    assert s.ssl == "require"


def test_local_url_without_ssl() -> None:
    s = Settings(database_url="postgres://u:p@localhost/db")
    assert s.sqlalchemy_url == "postgresql+asyncpg://u:p@localhost/db"
    assert s.ssl is False
