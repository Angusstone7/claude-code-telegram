"""Unit tests for TelegramApiConfig value object."""

import pytest

from domain.value_objects.telegram_api_config import TelegramApiConfig


class TestTelegramApiConfigFromUrl:
    """Tests for TelegramApiConfig.from_url() factory."""

    def test_valid_http_url(self):
        config = TelegramApiConfig.from_url("http://85.192.63.133:8089/telegram")
        assert config.enabled is True
        assert config.server_url == "http://85.192.63.133:8089/telegram"

    def test_valid_https_url(self):
        config = TelegramApiConfig.from_url("https://tg-proxy.example.com/bot-api")
        assert config.enabled is True
        assert "https://" in config.server_url

    def test_url_without_path(self):
        config = TelegramApiConfig.from_url("http://proxy.local:3000")
        assert config.enabled is True
        assert config.server_url == "http://proxy.local:3000"

    def test_strips_trailing_slash(self):
        config = TelegramApiConfig.from_url("http://example.com:8080/tg/")
        assert config.server_url == "http://example.com:8080/tg"

    def test_strips_whitespace(self):
        config = TelegramApiConfig.from_url("  http://example.com:8080  ")
        assert config.server_url == "http://example.com:8080"

    def test_invalid_scheme_ftp(self):
        with pytest.raises(ValueError, match="Unsupported scheme"):
            TelegramApiConfig.from_url("ftp://example.com/telegram")

    def test_invalid_scheme_socks(self):
        with pytest.raises(ValueError, match="Unsupported scheme"):
            TelegramApiConfig.from_url("socks5://example.com:1080")

    def test_missing_host(self):
        with pytest.raises(ValueError):
            TelegramApiConfig.from_url("not-a-url")

    def test_empty_string(self):
        with pytest.raises(ValueError, match="URL cannot be empty"):
            TelegramApiConfig.from_url("")

    def test_whitespace_only(self):
        with pytest.raises(ValueError, match="URL cannot be empty"):
            TelegramApiConfig.from_url("   ")


class TestTelegramApiConfigDisabled:
    """Tests for TelegramApiConfig.disabled() factory."""

    def test_disabled_is_not_enabled(self):
        config = TelegramApiConfig.disabled()
        assert config.enabled is False

    def test_disabled_has_no_url(self):
        config = TelegramApiConfig.disabled()
        assert config.server_url is None


class TestTelegramApiConfigDisplayUrl:
    """Tests for display_url property."""

    def test_display_url_with_port_and_path(self):
        config = TelegramApiConfig.from_url("http://85.192.63.133:8089/telegram")
        assert config.display_url == "85.192.63.133:8089/telegram"

    def test_display_url_without_port(self):
        config = TelegramApiConfig.from_url("https://tg-proxy.example.com/api")
        assert config.display_url == "tg-proxy.example.com/api"

    def test_display_url_disabled(self):
        config = TelegramApiConfig.disabled()
        assert config.display_url == "api.telegram.org"

    def test_display_url_no_path(self):
        config = TelegramApiConfig.from_url("http://localhost:3000")
        assert "localhost:3000" in config.display_url


class TestTelegramApiConfigImmutability:
    """Tests that TelegramApiConfig is frozen."""

    def test_cannot_modify_server_url(self):
        config = TelegramApiConfig.from_url("http://example.com:8080")
        with pytest.raises(AttributeError):
            config.server_url = "http://other.com"

    def test_cannot_modify_enabled(self):
        config = TelegramApiConfig.from_url("http://example.com:8080")
        with pytest.raises(AttributeError):
            config.enabled = False
