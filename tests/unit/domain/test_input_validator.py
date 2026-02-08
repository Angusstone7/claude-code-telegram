"""
Tests for input validators.
"""

import pytest
from pydantic import ValidationError
from domain.validators.input_validator import (
    ValidatedCommand,
    ValidatedPath,
    ValidatedProxyUrl,
    ValidatedProjectName,
    ValidatedGitHubUrl,
    ValidatedText,
    ValidatedApiKey,
    validate_user_input,
)


class TestValidatedCommand:
    """Тесты валидации команд"""

    def test_valid_command(self):
        """Валидная команда"""
        cmd = ValidatedCommand(command="ls -la")
        assert cmd.command == "ls -la"

    def test_command_too_long(self):
        """Слишком длинная команда"""
        with pytest.raises((ValueError, ValidationError)):
            ValidatedCommand(command="a" * 1001)

    def test_command_with_dangerous_chars(self):
        """Опасные символы"""
        with pytest.raises(ValueError, match="Dangerous character"):
            ValidatedCommand(command="ls && rm -rf")

        with pytest.raises(ValueError, match="Dangerous character"):
            ValidatedCommand(command="cat | grep test")

    def test_command_with_path_traversal(self):
        """Path traversal"""
        with pytest.raises(ValueError, match="Path traversal"):
            ValidatedCommand(command="cat ../../../etc/passwd")

    def test_command_strip_whitespace(self):
        """Удаление пробелов"""
        cmd = ValidatedCommand(command="  ls -la  ")
        assert cmd.command == "ls -la"


class TestValidatedPath:
    """Тесты валидации путей"""

    def test_valid_path(self):
        """Валидный путь"""
        path = ValidatedPath(path="/root/projects")
        assert path.path == "/root/projects"

    def test_path_too_long(self):
        """Слишком длинный путь"""
        with pytest.raises((ValueError, ValidationError)):
            ValidatedPath(path="a" * 501)

    def test_path_with_path_traversal(self):
        """Path traversal"""
        with pytest.raises(ValueError, match="Path traversal"):
            ValidatedPath(path="/root/../etc/passwd")

    def test_path_with_null_bytes(self):
        """Null bytes"""
        with pytest.raises(ValueError, match="Null bytes"):
            ValidatedPath(path="/root\x00/projects")

    def test_path_with_windows_forbidden(self):
        """Запрещенные символы Windows"""
        with pytest.raises(ValueError, match="Invalid character"):
            ValidatedPath(path="C:\\Projects\\Test<.txt")


class TestValidatedProxyUrl:
    """Тесты валидации proxy URLs"""

    def test_valid_http_proxy(self):
        """Валидный HTTP proxy"""
        proxy = ValidatedProxyUrl(url="http://proxy.example.com:8080")
        assert proxy.url == "http://proxy.example.com:8080"

    def test_valid_socks5_proxy(self):
        """Валидный SOCKS5 proxy"""
        proxy = ValidatedProxyUrl(url="socks5://proxy.example.com:1080")
        assert proxy.url == "socks5://proxy.example.com:1080"

    def test_proxy_with_auth(self):
        """Proxy с аутентификацией"""
        proxy = ValidatedProxyUrl(url="http://user:pass@proxy.example.com:8080")
        assert proxy.url == "http://user:pass@proxy.example.com:8080"

    def test_proxy_invalid_scheme(self):
        """Неверная схема"""
        with pytest.raises(ValueError, match="Invalid proxy scheme"):
            ValidatedProxyUrl(url="ftp://proxy.example.com")

    def test_proxy_missing_hostname(self):
        """Отсутствует hostname"""
        with pytest.raises(ValueError, match="Missing hostname"):
            ValidatedProxyUrl(url="http://")

    def test_proxy_invalid_port(self):
        """Неверный порт"""
        with pytest.raises((ValueError, ValidationError)):
            ValidatedProxyUrl(url="http://proxy.example.com:99999")


class TestValidatedProjectName:
    """Тесты валидации названий проектов"""

    def test_valid_project_name(self):
        """Валидное название"""
        name = ValidatedProjectName(name="My Project")
        assert name.name == "My Project"

    def test_project_name_too_long(self):
        """Слишком длинное название"""
        with pytest.raises((ValueError, ValidationError)):
            ValidatedProjectName(name="a" * 101)

    def test_project_name_with_invalid_chars(self):
        """Недопустимые символы"""
        with pytest.raises(ValueError, match="Invalid character"):
            ValidatedProjectName(name="Project/Name")

        with pytest.raises(ValueError, match="Invalid character"):
            ValidatedProjectName(name="Project:Name")

    def test_project_name_with_path_traversal(self):
        """Path traversal"""
        with pytest.raises((ValueError, ValidationError)):
            ValidatedProjectName(name="../etc")


class TestValidatedGitHubUrl:
    """Тесты валидации GitHub URLs"""

    def test_valid_github_url(self):
        """Валидный GitHub URL"""
        url = ValidatedGitHubUrl(url="https://github.com/user/repo")
        assert url.url == "https://github.com/user/repo"

    def test_github_url_with_git(self):
        """GitHub URL с .git"""
        url = ValidatedGitHubUrl(url="https://github.com/user/repo.git")
        assert url.url == "https://github.com/user/repo.git"

    def test_github_url_invalid_scheme(self):
        """Неверная схема"""
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            ValidatedGitHubUrl(url="ftp://github.com/user/repo")

    def test_github_url_wrong_domain(self):
        """Неверный домен"""
        with pytest.raises(ValueError, match="must be from github.com"):
            ValidatedGitHubUrl(url="https://gitlab.com/user/repo")

    def test_github_url_missing_path(self):
        """Отсутствует путь"""
        with pytest.raises(ValueError, match="Invalid GitHub repository path"):
            ValidatedGitHubUrl(url="https://github.com/")


class TestValidatedText:
    """Тесты валидации текста"""

    def test_valid_text(self):
        """Валидный текст"""
        text = ValidatedText(text="Hello, World!")
        assert text.text == "Hello, World!"

    def test_text_too_long(self):
        """Слишком длинный текст"""
        with pytest.raises((ValueError, ValidationError)):
            ValidatedText(text="a" * 5001)

    def test_text_with_null_bytes(self):
        """Null bytes"""
        with pytest.raises(ValueError, match="Null bytes"):
            ValidatedText(text="Hello\x00World")

    def test_text_with_control_chars(self):
        """Control characters"""
        with pytest.raises(ValueError, match="Control characters"):
            ValidatedText(text="Hello\x01World")

    def test_text_with_newline_allowed(self):
        """Newline разрешен"""
        text = ValidatedText(text="Line 1\nLine 2")
        assert "\n" in text.text


class TestValidatedApiKey:
    """Тесты валидации API keys"""

    def test_valid_api_key(self):
        """Валидный API key"""
        key = ValidatedApiKey(key="sk-1234567890abcdef")
        assert key.key == "sk-1234567890abcdef"

    def test_api_key_too_long(self):
        """Слишком длинный ключ"""
        with pytest.raises((ValueError, ValidationError)):
            ValidatedApiKey(key="a" * 201)

    def test_api_key_with_whitespace(self):
        """Whitespace в ключе"""
        with pytest.raises(ValueError, match="cannot contain whitespace"):
            ValidatedApiKey(key="sk-1234 5678")

    def test_api_key_strip(self):
        """API key с пробелами отклоняется (Pydantic v2 проверяет whitespace до strip)"""
        with pytest.raises((ValueError, ValidationError)):
            ValidatedApiKey(key="  sk-1234567890  ")


class TestValidateUserInput:
    """Тесты функции validate_user_input"""

    def test_valid_command(self):
        """Валидная команда"""
        success, error, value = validate_user_input('command', 'ls -la')
        assert success
        assert error == ""
        assert value == "ls -la"

    def test_invalid_command(self):
        """Невалидная команда"""
        success, error, value = validate_user_input('command', 'ls && rm -rf')
        assert not success
        assert "Dangerous character" in error
        assert value is None

    def test_unknown_type(self):
        """Неизвестный тип"""
        success, error, value = validate_user_input('unknown', 'test')
        assert not success
        assert "Unknown input type" in error
