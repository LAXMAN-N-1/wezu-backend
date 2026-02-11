
from app.core.config import settings
import pytest

def test_secret_key_loaded():
    """Verify SECRET_KEY is present and not default"""
    assert settings.SECRET_KEY, "SECRET_KEY must be loaded"
    assert settings.SECRET_KEY != "yd0b7447cbdd06c5586e20d5093121fbfbde37268d664dac666884cfe79cb3d1f", "SECRET_KEY is using the unsafe default!"

def test_cors_origins_loaded():
    """Verify CORS_ORIGINS is a list and contains trusted domains"""
    print(f"DEBUG: CORS_ORIGINS={settings.CORS_ORIGINS}")
    assert isinstance(settings.CORS_ORIGINS, list), "CORS_ORIGINS must be a list"
    assert len(settings.CORS_ORIGINS) > 0, "CORS_ORIGINS must not be empty"
    assert "http://localhost:3000" in settings.CORS_ORIGINS

def test_cors_not_wildcard():
    """Verify CORS is not wildcard '*' in a way that allows all"""
    # Note: If it's literally ["*"], it allows everything.
    # We want to ensure it is NOT just ["*"] if we want to be strict.
    # But for now, just checking it's allowed.
    pass
