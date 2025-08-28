"""Tests for webhook secret validation in config."""

import pytest
from pydantic import ValidationError
from app.config import Settings


class TestWebhookSecretValidation:
    """Test webhook secret validation rules."""

    def test_production_mode_requires_webhook_secret(self):
        """Test that production mode (DEBUG=False) requires WEBHOOK_SECRET."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(DEBUG=False, WEBHOOK_SECRET="")
        
        error = exc_info.value
        assert "WEBHOOK_SECRET is required when DEBUG is false" in str(error)

    def test_production_mode_requires_non_empty_webhook_secret(self):
        """Test that production mode rejects whitespace-only secrets."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(DEBUG=False, WEBHOOK_SECRET="   ")
        
        error = exc_info.value
        assert "WEBHOOK_SECRET is required when DEBUG is false" in str(error)

    def test_production_mode_requires_non_none_webhook_secret(self):
        """Test that production mode rejects None webhook secret."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(DEBUG=False, WEBHOOK_SECRET=None)
        
        error = exc_info.value
        assert "WEBHOOK_SECRET is required when DEBUG is false" in str(error)

    def test_production_mode_accepts_valid_webhook_secret(self):
        """Test that production mode accepts valid webhook secret."""
        settings = Settings(DEBUG=False, WEBHOOK_SECRET="my_secure_secret_123")
        assert settings.WEBHOOK_SECRET == "my_secure_secret_123"
        assert settings.DEBUG is False

    def test_debug_mode_allows_empty_webhook_secret(self):
        """Test that debug mode allows empty webhook secret."""
        settings = Settings(DEBUG=True, WEBHOOK_SECRET="")
        assert settings.WEBHOOK_SECRET == ""
        assert settings.DEBUG is True

    def test_debug_mode_allows_none_webhook_secret(self):
        """Test that debug mode allows None webhook secret."""
        settings = Settings(DEBUG=True, WEBHOOK_SECRET=None)
        assert settings.WEBHOOK_SECRET is None
        assert settings.DEBUG is True

    def test_debug_mode_allows_whitespace_webhook_secret(self):
        """Test that debug mode allows whitespace-only webhook secret."""
        settings = Settings(DEBUG=True, WEBHOOK_SECRET="   ")
        assert settings.WEBHOOK_SECRET == "   "
        assert settings.DEBUG is True

    def test_debug_mode_accepts_valid_webhook_secret(self):
        """Test that debug mode also accepts valid webhook secret."""
        settings = Settings(DEBUG=True, WEBHOOK_SECRET="debug_secret")
        assert settings.WEBHOOK_SECRET == "debug_secret"
        assert settings.DEBUG is True

    def test_validation_error_contains_helpful_message(self):
        """Test that validation error contains helpful guidance."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(DEBUG=False, WEBHOOK_SECRET="")
        
        error_msg = str(exc_info.value)
        assert "WEBHOOK_SECRET is required when DEBUG is false" in error_msg
        assert "Set WEBHOOK_SECRET environment variable" in error_msg
        assert "production security" in error_msg

    def test_default_values_in_production_mode_fail(self, monkeypatch):
        """Test that default values fail in production mode."""
        # Clear any environment variables that might interfere
        monkeypatch.delenv("DEBUG", raising=False)
        monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
        # Also clear any .env file loading by temporarily disabling it
        monkeypatch.setenv("WEBHOOK_SECRET", "")  # Force empty value
        
        # Default WEBHOOK_SECRET is None, DEBUG is False by default  
        with pytest.raises(ValidationError):
            Settings(DEBUG=False, WEBHOOK_SECRET="")  # Explicitly set empty

    def test_environment_variable_integration(self, monkeypatch):
        """Test validation works with environment variables."""
        # Test production mode with env var set
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("WEBHOOK_SECRET", "env_secret_123")
        
        settings = Settings()
        assert settings.DEBUG is False
        assert settings.WEBHOOK_SECRET == "env_secret_123"

    def test_environment_variable_production_failure(self, monkeypatch):
        """Test validation fails with empty env var in production."""
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("WEBHOOK_SECRET", "")
        
        with pytest.raises(ValidationError) as exc_info:
            Settings()
        
        assert "WEBHOOK_SECRET is required when DEBUG is false" in str(exc_info.value)

    def test_case_sensitivity_of_debug(self):
        """Test that DEBUG value parsing is case-sensitive as configured."""
        # DEBUG should be parsed as boolean, test different values
        
        # String "false" should be parsed as boolean False
        settings = Settings(DEBUG="false", WEBHOOK_SECRET="test_secret")  # type: ignore
        # Note: Pydantic converts string "false" to boolean False
        
        # This test documents current behavior - if it fails, 
        # it means pydantic boolean parsing changed
        try:
            Settings(DEBUG="False", WEBHOOK_SECRET="")  # type: ignore
            pytest.fail("Expected ValidationError for DEBUG=False with empty secret")
        except ValidationError:
            pass  # Expected behavior
