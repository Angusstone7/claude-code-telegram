"""
Input validation utilities для безопасности.

Предоставляет валидацию для всех пользовательских вводов.
"""

import re
import logging
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, field_validator, Field

logger = logging.getLogger(__name__)


# === Common Validators ===

class ValidatedCommand(BaseModel):
    """Валидированная команда от пользователя"""
    command: str = Field(..., min_length=1, max_length=1000)

    @field_validator('command')
    @classmethod
    def validate_command(cls, v: str) -> str:
        """Валидация команды на опасные символы"""
        # Длина
        if len(v) > 1000:
            raise ValueError('Command too long (max 1000 characters)')

        # Опасные символы (basic check)
        dangerous_patterns = ['&&', '||', ';', '`', '$(', '<(', '>', '|']
        for pattern in dangerous_patterns:
            if pattern in v:
                raise ValueError(f'Dangerous character sequence detected: {pattern}')

        # Path traversal
        if '../' in v or '..\\' in v:
            raise ValueError('Path traversal detected')

        # Null bytes
        if '\x00' in v:
            raise ValueError('Null bytes detected')

        return v.strip()


class ValidatedPath(BaseModel):
    """Валидированный путь"""
    path: str = Field(..., min_length=1, max_length=500)

    @field_validator('path')
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Валидация пути"""
        # Длина
        if len(v) > 500:
            raise ValueError('Path too long (max 500 characters)')

        # Path traversal
        if '../' in v or '..\\' in v:
            raise ValueError('Path traversal detected')

        # Null bytes
        if '\x00' in v:
            raise ValueError('Null bytes detected')

        # Проверка на валидные символы
        # Windows:不允许 <>:"|?*
        # Unix: только null и /
        invalid_windows = ['<', '>', ':', '"', '|', '?', '*']
        if any(char in v for char in invalid_windows):
            raise ValueError(f'Invalid character in path (Windows forbidden)')

        return v.strip()


class ValidatedProxyUrl(BaseModel):
    """Валидированный proxy URL"""
    url: str = Field(..., min_length=1, max_length=200)

    @field_validator('url')
    @classmethod
    def validate_proxy_url(cls, v: str) -> str:
        """Валидация proxy URL"""
        from urllib.parse import urlparse

        try:
            result = urlparse(v)

            # Scheme проверка
            if result.scheme not in ['http', 'https', 'socks5', 'socks5h']:
                raise ValueError(
                    "Invalid proxy scheme. Must be http, https, socks5, or socks5h"
                )

            # Hostname проверка
            if not result.hostname:
                raise ValueError("Missing hostname in proxy URL")

            # Port проверка (если указан)
            if result.port is not None and not (1 <= result.port <= 65535):
                raise ValueError(f"Invalid port: {result.port}")

            # Длина
            if len(v) > 200:
                raise ValueError('Proxy URL too long (max 200 characters)')

            return v.strip()

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f'Invalid proxy URL: {e}')


class ValidatedProjectName(BaseModel):
    """Валидированное название проекта"""
    name: str = Field(..., min_length=1, max_length=100)

    @field_validator('name')
    @classmethod
    def validate_project_name(cls, v: str) -> str:
        """Валидация названия проекта"""
        # Длина
        if len(v) > 100:
            raise ValueError('Project name too long (max 100 characters)')

        # Опасные символы
        if any(char in v for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']):
            raise ValueError('Invalid character in project name')

        # Path traversal
        if '../' in v or '..\\' in v:
            raise ValueError('Path traversal detected')

        # Null bytes
        if '\x00' in v:
            raise ValueError('Null bytes detected')

        return v.strip()


class ValidatedGitHubUrl(BaseModel):
    """Валидированный GitHub URL"""
    url: str = Field(..., min_length=1, max_length=200)

    @field_validator('url')
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        """Валидация GitHub URL"""
        from urllib.parse import urlparse

        try:
            result = urlparse(v)

            # Scheme проверка
            if result.scheme not in ['http', 'https']:
                raise ValueError("Invalid URL scheme. Must be http or https")

            # Domain проверка
            if 'github.com' not in result.netloc.lower():
                raise ValueError("URL must be from github.com")

            # Path проверка
            if not result.path or result.path == '/':
                raise ValueError("Invalid GitHub repository path")

            # Длина
            if len(v) > 200:
                raise ValueError('GitHub URL too long (max 200 characters)')

            return v.strip()

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f'Invalid GitHub URL: {e}')


class ValidatedText(BaseModel):
    """Валидированный текст (общий случай)"""
    text: str = Field(..., min_length=1, max_length=5000)

    @field_validator('text')
    @classmethod
    def validate_text(cls, v: str) -> str:
        """Базовая валидация текста"""
        # Длина
        if len(v) > 5000:
            raise ValueError('Text too long (max 5000 characters)')

        # Null bytes
        if '\x00' in v:
            raise ValueError('Null bytes detected')

        # Control characters (кроме newline, tab, carriage return)
        control_chars = set(range(0, 32)) - {9, 10, 13}  # \t, \n, \r
        if any(ord(c) in control_chars for c in v):
            raise ValueError('Control characters detected')

        return v


class ValidatedApiKey(BaseModel):
    """Валидированный API key"""
    key: str = Field(..., min_length=1, max_length=200)

    @field_validator('key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Валидация API key"""
        # Длина
        if len(v) > 200:
            raise ValueError('API key too long (max 200 characters)')

        # Проверка на whitespace
        if any(c.isspace() for c in v):
            raise ValueError('API key cannot contain whitespace')

        # Null bytes
        if '\x00' in v:
            raise ValueError('Null bytes detected')

        return v.strip()


# === Validator Functions ===

def validate_user_input(input_type: str, value: str) -> tuple[bool, str, any]:
    """
    Валидация пользовательского ввода.

    Args:
        input_type: Тип ввода (command, path, proxy_url, project_name, github_url, text, api_key)
        value: Значение для валидации

    Returns:
        (success, error_message, validated_value)
    """
    validators = {
'command': ValidatedCommand,
        'path': ValidatedPath,
        'proxy_url': ValidatedProxyUrl,
        'project_name': ValidatedProjectName,
        'github_url': ValidatedGitHubUrl,
        'text': ValidatedText,
        'api_key': ValidatedApiKey,
    }

    validator_class = validators.get(input_type)
    if not validator_class:
        return False, f"Unknown input type: {input_type}", None

    try:
        validated = validator_class(**{input_type if input_type != 'proxy_url' else 'url': value})
        return True, "", validated.__getattribute__(
            'command' if input_type == 'command' else
            'path' if input_type == 'path' else
            'url' if input_type == 'proxy_url' else
            'name' if input_type == 'project_name' else
            'url' if input_type == 'github_url' else
            'text' if input_type == 'text' else
            'key'
        )
    except Exception as e:
        return False, str(e), None


# === Middleware Integration ===

async def validate_and_sanitize(user_input: str, input_type: str = 'text') -> tuple[bool, str, str]:
    """
    Валидация и санитизация пользовательского ввода.

    Args:
        user_input: Пользовательский ввод
        input_type: Тип ввода

    Returns:
        (success, error_message, sanitized_value)
    """
    success, error, value = validate_user_input(input_type, user_input)

    if not success:
        logger.warning(f"Input validation failed: {error}")
        return False, error, ""

    return True, "", value
