"""Unit tests for infrastructure settings (_get_infra_config and infra update logic).

Tests cover:
- Reading default values when no env vars are set
- Reading SSH, GitLab, alert, debug, and log_level env vars
- Writing infra settings back to env vars (simulating PATCH /settings)
- InfraConfigUpdate schema validation (ports, alert ranges, log levels)
"""

import os

import pytest
from pydantic import ValidationError

from presentation.api.routes.settings import _get_infra_config
from presentation.api.schemas.settings import InfraConfigUpdate


# ---------------------------------------------------------------------------
# 1. _get_infra_config returns defaults when no env vars are set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_infra_config_defaults(monkeypatch):
    """All fields should return sensible defaults when env vars are absent."""
    env_keys = [
        "SSH_HOST", "SSH_PORT", "HOST_USER",
        "GITLAB_URL", "GITLAB_TOKEN",
        "ALERT_THRESHOLD_CPU", "ALERT_THRESHOLD_MEMORY", "ALERT_THRESHOLD_DISK",
        "DEBUG", "LOG_LEVEL",
    ]
    for key in env_keys:
        monkeypatch.delenv(key, raising=False)

    result = await _get_infra_config()

    assert result["ssh_host"] == "host.docker.internal"
    assert result["ssh_port"] == 22
    assert result["ssh_user"] == "root"
    assert result["gitlab_url"] == "https://gitlab.com"
    assert result["gitlab_token_set"] is False
    assert result["alert_cpu"] == 80.0
    assert result["alert_memory"] == 85.0
    assert result["alert_disk"] == 90.0
    assert result["debug"] is False
    assert result["log_level"] == "INFO"


# ---------------------------------------------------------------------------
# 2. _get_infra_config reads SSH env vars
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_infra_config_ssh_vars(monkeypatch):
    """SSH_HOST, SSH_PORT, HOST_USER should be reflected in the config."""
    monkeypatch.setenv("SSH_HOST", "10.0.0.5")
    monkeypatch.setenv("SSH_PORT", "2222")
    monkeypatch.setenv("HOST_USER", "deploy")

    result = await _get_infra_config()

    assert result["ssh_host"] == "10.0.0.5"
    assert result["ssh_port"] == 2222
    assert result["ssh_user"] == "deploy"


@pytest.mark.asyncio
async def test_get_infra_config_ssh_port_is_int(monkeypatch):
    """SSH port must be returned as int, not str."""
    monkeypatch.setenv("SSH_PORT", "8022")

    result = await _get_infra_config()

    assert isinstance(result["ssh_port"], int)
    assert result["ssh_port"] == 8022


# ---------------------------------------------------------------------------
# 3. _get_infra_config reads GitLab env vars (token_set is bool)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_infra_config_gitlab_vars(monkeypatch):
    """gitlab_url and gitlab_token_set should be read from env."""
    monkeypatch.setenv("GITLAB_URL", "https://git.example.com")
    monkeypatch.setenv("GITLAB_TOKEN", "glpat-secret-token")

    result = await _get_infra_config()

    assert result["gitlab_url"] == "https://git.example.com"
    assert result["gitlab_token_set"] is True


@pytest.mark.asyncio
async def test_get_infra_config_gitlab_token_not_leaked(monkeypatch):
    """The actual token value must NOT appear in the config dict."""
    monkeypatch.setenv("GITLAB_TOKEN", "glpat-super-secret")

    result = await _get_infra_config()

    assert result["gitlab_token_set"] is True
    # The raw token string must not be present anywhere in the dict values
    for value in result.values():
        assert value != "glpat-super-secret"


@pytest.mark.asyncio
async def test_get_infra_config_gitlab_token_unset(monkeypatch):
    """gitlab_token_set is False when GITLAB_TOKEN is not set."""
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)

    result = await _get_infra_config()

    assert result["gitlab_token_set"] is False


@pytest.mark.asyncio
async def test_get_infra_config_gitlab_token_empty_string(monkeypatch):
    """gitlab_token_set is False when GITLAB_TOKEN is an empty string."""
    monkeypatch.setenv("GITLAB_TOKEN", "")

    result = await _get_infra_config()

    assert result["gitlab_token_set"] is False


# ---------------------------------------------------------------------------
# 4. _get_infra_config reads alert thresholds from env
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_infra_config_alert_thresholds(monkeypatch):
    """Custom alert thresholds should be read from env as floats."""
    monkeypatch.setenv("ALERT_THRESHOLD_CPU", "95.5")
    monkeypatch.setenv("ALERT_THRESHOLD_MEMORY", "70.0")
    monkeypatch.setenv("ALERT_THRESHOLD_DISK", "50.25")

    result = await _get_infra_config()

    assert result["alert_cpu"] == 95.5
    assert result["alert_memory"] == 70.0
    assert result["alert_disk"] == 50.25


@pytest.mark.asyncio
async def test_get_infra_config_alert_thresholds_are_float(monkeypatch):
    """Alert thresholds must be returned as float, not str."""
    monkeypatch.setenv("ALERT_THRESHOLD_CPU", "60")

    result = await _get_infra_config()

    assert isinstance(result["alert_cpu"], float)


# ---------------------------------------------------------------------------
# 5. Debug mode toggle — os.environ updated when infra.debug is set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_infra_config_debug_true(monkeypatch):
    """debug should be True when DEBUG=true."""
    monkeypatch.setenv("DEBUG", "true")

    result = await _get_infra_config()

    assert result["debug"] is True


@pytest.mark.asyncio
async def test_get_infra_config_debug_false(monkeypatch):
    """debug should be False when DEBUG=false."""
    monkeypatch.setenv("DEBUG", "false")

    result = await _get_infra_config()

    assert result["debug"] is False


@pytest.mark.asyncio
async def test_get_infra_config_debug_case_insensitive(monkeypatch):
    """debug should handle case-insensitive 'TRUE', 'True', etc."""
    monkeypatch.setenv("DEBUG", "TRUE")
    result = await _get_infra_config()
    assert result["debug"] is True

    monkeypatch.setenv("DEBUG", "True")
    result = await _get_infra_config()
    assert result["debug"] is True


def test_infra_update_debug_sets_env_var(monkeypatch):
    """Simulating infra update: setting debug=True should set DEBUG=true in env."""
    monkeypatch.delenv("DEBUG", raising=False)

    inf = {"debug": True}
    env_mapping = {
        "ssh_host": "SSH_HOST", "ssh_port": "SSH_PORT", "ssh_user": "HOST_USER",
        "gitlab_url": "GITLAB_URL", "gitlab_token": "GITLAB_TOKEN",
        "alert_cpu": "ALERT_THRESHOLD_CPU", "alert_memory": "ALERT_THRESHOLD_MEMORY",
        "alert_disk": "ALERT_THRESHOLD_DISK", "debug": "DEBUG", "log_level": "LOG_LEVEL",
    }
    for ik, iv in inf.items():
        env_key = env_mapping.get(ik)
        if env_key:
            os.environ[env_key] = str(iv).lower() if isinstance(iv, bool) else str(iv)

    assert os.environ["DEBUG"] == "true"

    # Cleanup
    monkeypatch.delenv("DEBUG", raising=False)


def test_infra_update_debug_false_sets_env_var(monkeypatch):
    """Simulating infra update: setting debug=False should set DEBUG=false."""
    monkeypatch.setenv("DEBUG", "true")

    inf = {"debug": False}
    env_mapping = {
        "ssh_host": "SSH_HOST", "ssh_port": "SSH_PORT", "ssh_user": "HOST_USER",
        "gitlab_url": "GITLAB_URL", "gitlab_token": "GITLAB_TOKEN",
        "alert_cpu": "ALERT_THRESHOLD_CPU", "alert_memory": "ALERT_THRESHOLD_MEMORY",
        "alert_disk": "ALERT_THRESHOLD_DISK", "debug": "DEBUG", "log_level": "LOG_LEVEL",
    }
    for ik, iv in inf.items():
        env_key = env_mapping.get(ik)
        if env_key:
            os.environ[env_key] = str(iv).lower() if isinstance(iv, bool) else str(iv)

    assert os.environ["DEBUG"] == "false"


# ---------------------------------------------------------------------------
# 6. Log level change — os.environ updated when infra.log_level is set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_infra_config_log_level(monkeypatch):
    """log_level should be read from LOG_LEVEL env var."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    result = await _get_infra_config()

    assert result["log_level"] == "DEBUG"


def test_infra_update_log_level_sets_env_var(monkeypatch):
    """Simulating infra update: setting log_level should update LOG_LEVEL."""
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    inf = {"log_level": "WARNING"}
    env_mapping = {
        "ssh_host": "SSH_HOST", "ssh_port": "SSH_PORT", "ssh_user": "HOST_USER",
        "gitlab_url": "GITLAB_URL", "gitlab_token": "GITLAB_TOKEN",
        "alert_cpu": "ALERT_THRESHOLD_CPU", "alert_memory": "ALERT_THRESHOLD_MEMORY",
        "alert_disk": "ALERT_THRESHOLD_DISK", "debug": "DEBUG", "log_level": "LOG_LEVEL",
    }
    for ik, iv in inf.items():
        env_key = env_mapping.get(ik)
        if env_key:
            os.environ[env_key] = str(iv).lower() if isinstance(iv, bool) else str(iv)

    assert os.environ["LOG_LEVEL"] == "WARNING"

    # Cleanup
    monkeypatch.delenv("LOG_LEVEL", raising=False)


def test_infra_update_log_level_error(monkeypatch):
    """log_level=ERROR should be persisted correctly."""
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    inf = {"log_level": "ERROR"}
    env_mapping = {"log_level": "LOG_LEVEL"}
    for ik, iv in inf.items():
        env_key = env_mapping.get(ik)
        if env_key:
            os.environ[env_key] = str(iv).lower() if isinstance(iv, bool) else str(iv)

    assert os.environ["LOG_LEVEL"] == "ERROR"

    monkeypatch.delenv("LOG_LEVEL", raising=False)


# ---------------------------------------------------------------------------
# 7. SSH env vars updated when infra settings patched
# ---------------------------------------------------------------------------


def test_infra_update_ssh_vars(monkeypatch):
    """Simulating infra update: SSH fields should set corresponding env vars."""
    monkeypatch.delenv("SSH_HOST", raising=False)
    monkeypatch.delenv("SSH_PORT", raising=False)
    monkeypatch.delenv("HOST_USER", raising=False)

    inf = {"ssh_host": "192.168.1.100", "ssh_port": 2222, "ssh_user": "admin"}
    env_mapping = {
        "ssh_host": "SSH_HOST", "ssh_port": "SSH_PORT", "ssh_user": "HOST_USER",
        "gitlab_url": "GITLAB_URL", "gitlab_token": "GITLAB_TOKEN",
        "alert_cpu": "ALERT_THRESHOLD_CPU", "alert_memory": "ALERT_THRESHOLD_MEMORY",
        "alert_disk": "ALERT_THRESHOLD_DISK", "debug": "DEBUG", "log_level": "LOG_LEVEL",
    }
    for ik, iv in inf.items():
        env_key = env_mapping.get(ik)
        if env_key:
            os.environ[env_key] = str(iv).lower() if isinstance(iv, bool) else str(iv)

    assert os.environ["SSH_HOST"] == "192.168.1.100"
    assert os.environ["SSH_PORT"] == "2222"
    assert os.environ["HOST_USER"] == "admin"

    # Cleanup
    monkeypatch.delenv("SSH_HOST", raising=False)
    monkeypatch.delenv("SSH_PORT", raising=False)
    monkeypatch.delenv("HOST_USER", raising=False)


def test_infra_update_gitlab_token(monkeypatch):
    """Simulating infra update: gitlab_token should set GITLAB_TOKEN env var."""
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)

    inf = {"gitlab_token": "glpat-new-token-value"}
    env_mapping = {
        "ssh_host": "SSH_HOST", "ssh_port": "SSH_PORT", "ssh_user": "HOST_USER",
        "gitlab_url": "GITLAB_URL", "gitlab_token": "GITLAB_TOKEN",
        "alert_cpu": "ALERT_THRESHOLD_CPU", "alert_memory": "ALERT_THRESHOLD_MEMORY",
        "alert_disk": "ALERT_THRESHOLD_DISK", "debug": "DEBUG", "log_level": "LOG_LEVEL",
    }
    for ik, iv in inf.items():
        env_key = env_mapping.get(ik)
        if env_key:
            os.environ[env_key] = str(iv).lower() if isinstance(iv, bool) else str(iv)

    assert os.environ["GITLAB_TOKEN"] == "glpat-new-token-value"

    monkeypatch.delenv("GITLAB_TOKEN", raising=False)


def test_infra_update_alert_thresholds(monkeypatch):
    """Simulating infra update: alert thresholds should set env vars as strings."""
    monkeypatch.delenv("ALERT_THRESHOLD_CPU", raising=False)
    monkeypatch.delenv("ALERT_THRESHOLD_MEMORY", raising=False)
    monkeypatch.delenv("ALERT_THRESHOLD_DISK", raising=False)

    inf = {"alert_cpu": 75.5, "alert_memory": 60.0, "alert_disk": 95.0}
    env_mapping = {
        "alert_cpu": "ALERT_THRESHOLD_CPU",
        "alert_memory": "ALERT_THRESHOLD_MEMORY",
        "alert_disk": "ALERT_THRESHOLD_DISK",
    }
    for ik, iv in inf.items():
        env_key = env_mapping.get(ik)
        if env_key:
            os.environ[env_key] = str(iv).lower() if isinstance(iv, bool) else str(iv)

    assert os.environ["ALERT_THRESHOLD_CPU"] == "75.5"
    assert os.environ["ALERT_THRESHOLD_MEMORY"] == "60.0"
    assert os.environ["ALERT_THRESHOLD_DISK"] == "95.0"

    monkeypatch.delenv("ALERT_THRESHOLD_CPU", raising=False)
    monkeypatch.delenv("ALERT_THRESHOLD_MEMORY", raising=False)
    monkeypatch.delenv("ALERT_THRESHOLD_DISK", raising=False)


def test_infra_update_unknown_key_ignored(monkeypatch):
    """Keys not in env_mapping should not cause errors or set env vars."""
    inf = {"unknown_field": "value123"}
    env_mapping = {
        "ssh_host": "SSH_HOST", "ssh_port": "SSH_PORT", "ssh_user": "HOST_USER",
        "gitlab_url": "GITLAB_URL", "gitlab_token": "GITLAB_TOKEN",
        "alert_cpu": "ALERT_THRESHOLD_CPU", "alert_memory": "ALERT_THRESHOLD_MEMORY",
        "alert_disk": "ALERT_THRESHOLD_DISK", "debug": "DEBUG", "log_level": "LOG_LEVEL",
    }
    for ik, iv in inf.items():
        env_key = env_mapping.get(ik)
        if env_key:
            os.environ[env_key] = str(iv).lower() if isinstance(iv, bool) else str(iv)

    # No env var should have been set for the unknown key
    assert os.getenv("unknown_field") is None


@pytest.mark.asyncio
async def test_infra_update_roundtrip(monkeypatch):
    """After simulating an update, _get_infra_config should reflect the changes."""
    # Clear all relevant env vars first
    for key in ["SSH_HOST", "SSH_PORT", "HOST_USER", "GITLAB_URL", "GITLAB_TOKEN",
                 "ALERT_THRESHOLD_CPU", "ALERT_THRESHOLD_MEMORY", "ALERT_THRESHOLD_DISK",
                 "DEBUG", "LOG_LEVEL"]:
        monkeypatch.delenv(key, raising=False)

    # Simulate infra update
    inf = {
        "ssh_host": "my-server.local",
        "ssh_port": 9922,
        "ssh_user": "operator",
        "debug": True,
        "log_level": "ERROR",
    }
    env_mapping = {
        "ssh_host": "SSH_HOST", "ssh_port": "SSH_PORT", "ssh_user": "HOST_USER",
        "gitlab_url": "GITLAB_URL", "gitlab_token": "GITLAB_TOKEN",
        "alert_cpu": "ALERT_THRESHOLD_CPU", "alert_memory": "ALERT_THRESHOLD_MEMORY",
        "alert_disk": "ALERT_THRESHOLD_DISK", "debug": "DEBUG", "log_level": "LOG_LEVEL",
    }
    for ik, iv in inf.items():
        env_key = env_mapping.get(ik)
        if env_key:
            os.environ[env_key] = str(iv).lower() if isinstance(iv, bool) else str(iv)

    # Verify _get_infra_config reflects these changes
    result = await _get_infra_config()

    assert result["ssh_host"] == "my-server.local"
    assert result["ssh_port"] == 9922
    assert result["ssh_user"] == "operator"
    assert result["debug"] is True
    assert result["log_level"] == "ERROR"


# ---------------------------------------------------------------------------
# 8. InfraConfigUpdate schema validation
# ---------------------------------------------------------------------------


class TestInfraConfigUpdateSchema:
    """Validate InfraConfigUpdate pydantic schema constraints."""

    def test_valid_full_update(self):
        """All fields provided with valid values should pass."""
        update = InfraConfigUpdate(
            ssh_host="10.0.0.1",
            ssh_port=22,
            ssh_user="root",
            gitlab_url="https://gitlab.example.com",
            gitlab_token="glpat-token",
            alert_cpu=80.0,
            alert_memory=85.0,
            alert_disk=90.0,
            debug=True,
            log_level="DEBUG",
        )
        assert update.ssh_host == "10.0.0.1"
        assert update.ssh_port == 22
        assert update.debug is True

    def test_valid_partial_update(self):
        """Partial updates (only some fields) should be valid."""
        update = InfraConfigUpdate(ssh_host="new-host")
        assert update.ssh_host == "new-host"
        assert update.ssh_port is None
        assert update.debug is None

    def test_valid_empty_update(self):
        """No fields provided should be valid (all optional)."""
        update = InfraConfigUpdate()
        assert update.ssh_host is None
        assert update.ssh_port is None

    # --- Port validation ---

    def test_port_min_valid(self):
        """Port = 1 should be valid (minimum)."""
        update = InfraConfigUpdate(ssh_port=1)
        assert update.ssh_port == 1

    def test_port_max_valid(self):
        """Port = 65535 should be valid (maximum)."""
        update = InfraConfigUpdate(ssh_port=65535)
        assert update.ssh_port == 65535

    def test_port_zero_invalid(self):
        """Port = 0 should fail validation (below minimum)."""
        with pytest.raises(ValidationError) as exc_info:
            InfraConfigUpdate(ssh_port=0)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("ssh_port",) for e in errors)

    def test_port_negative_invalid(self):
        """Negative port should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            InfraConfigUpdate(ssh_port=-1)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("ssh_port",) for e in errors)

    def test_port_too_high_invalid(self):
        """Port = 65536 should fail validation (above maximum)."""
        with pytest.raises(ValidationError) as exc_info:
            InfraConfigUpdate(ssh_port=65536)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("ssh_port",) for e in errors)

    # --- Alert CPU validation ---

    def test_alert_cpu_min_valid(self):
        """alert_cpu = 0 should be valid."""
        update = InfraConfigUpdate(alert_cpu=0.0)
        assert update.alert_cpu == 0.0

    def test_alert_cpu_max_valid(self):
        """alert_cpu = 100 should be valid."""
        update = InfraConfigUpdate(alert_cpu=100.0)
        assert update.alert_cpu == 100.0

    def test_alert_cpu_negative_invalid(self):
        """Negative alert_cpu should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            InfraConfigUpdate(alert_cpu=-1.0)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("alert_cpu",) for e in errors)

    def test_alert_cpu_over_100_invalid(self):
        """alert_cpu > 100 should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            InfraConfigUpdate(alert_cpu=100.1)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("alert_cpu",) for e in errors)

    # --- Alert memory validation ---

    def test_alert_memory_min_valid(self):
        """alert_memory = 0 should be valid."""
        update = InfraConfigUpdate(alert_memory=0.0)
        assert update.alert_memory == 0.0

    def test_alert_memory_max_valid(self):
        """alert_memory = 100 should be valid."""
        update = InfraConfigUpdate(alert_memory=100.0)
        assert update.alert_memory == 100.0

    def test_alert_memory_negative_invalid(self):
        """Negative alert_memory should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            InfraConfigUpdate(alert_memory=-0.1)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("alert_memory",) for e in errors)

    def test_alert_memory_over_100_invalid(self):
        """alert_memory > 100 should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            InfraConfigUpdate(alert_memory=101.0)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("alert_memory",) for e in errors)

    # --- Alert disk validation ---

    def test_alert_disk_min_valid(self):
        """alert_disk = 0 should be valid."""
        update = InfraConfigUpdate(alert_disk=0.0)
        assert update.alert_disk == 0.0

    def test_alert_disk_max_valid(self):
        """alert_disk = 100 should be valid."""
        update = InfraConfigUpdate(alert_disk=100.0)
        assert update.alert_disk == 100.0

    def test_alert_disk_negative_invalid(self):
        """Negative alert_disk should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            InfraConfigUpdate(alert_disk=-5.0)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("alert_disk",) for e in errors)

    def test_alert_disk_over_100_invalid(self):
        """alert_disk > 100 should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            InfraConfigUpdate(alert_disk=200.0)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("alert_disk",) for e in errors)

    # --- Log level validation ---

    def test_log_level_debug_valid(self):
        """log_level = DEBUG should be valid."""
        update = InfraConfigUpdate(log_level="DEBUG")
        assert update.log_level == "DEBUG"

    def test_log_level_info_valid(self):
        """log_level = INFO should be valid."""
        update = InfraConfigUpdate(log_level="INFO")
        assert update.log_level == "INFO"

    def test_log_level_warning_valid(self):
        """log_level = WARNING should be valid."""
        update = InfraConfigUpdate(log_level="WARNING")
        assert update.log_level == "WARNING"

    def test_log_level_error_valid(self):
        """log_level = ERROR should be valid."""
        update = InfraConfigUpdate(log_level="ERROR")
        assert update.log_level == "ERROR"

    def test_log_level_invalid_value(self):
        """Invalid log level (e.g. CRITICAL) should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            InfraConfigUpdate(log_level="CRITICAL")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("log_level",) for e in errors)

    def test_log_level_lowercase_invalid(self):
        """Lowercase log level should fail validation (pattern is uppercase)."""
        with pytest.raises(ValidationError) as exc_info:
            InfraConfigUpdate(log_level="debug")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("log_level",) for e in errors)

    def test_log_level_empty_string_invalid(self):
        """Empty string log level should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            InfraConfigUpdate(log_level="")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("log_level",) for e in errors)
