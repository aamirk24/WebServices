from app.config import get_settings


def test_settings_load():
    settings = get_settings()
    assert settings.database_url is not None
    assert settings.secret_key is not None
    assert settings.algorithm == "HS256"
    assert settings.access_token_expire_minutes == 30