def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    from app.config import Settings
    s = Settings()
    assert s.SECRET_KEY == "test-secret"
    assert s.ACCESS_TOKEN_TTL_MIN == 15          # default
    assert s.APP_TIMEZONE == "Asia/Kolkata"      # default
