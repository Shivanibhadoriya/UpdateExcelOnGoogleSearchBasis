"""Pytest unit tests for application configuration loading."""

import pytest

from config import load_config


@pytest.fixture(autouse=True)
def clear_configuration_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove configuration variables so each test controls its own values."""

    for name in (
        "SERP_API_KEY",
        "INPUT_DIRECTORY",
        "OUTPUT_DIRECTORY",
        "CACHE_DIRECTORY",
        "LOG_DIRECTORY",
        "REQUEST_TIMEOUT_SECONDS",
        "MAX_RETRY_ATTEMPTS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_load_config_uses_required_key_and_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The required key produces a fully initialized configuration."""

    monkeypatch.setenv("SERP_API_KEY", "test-key")

    config = load_config()

    assert config.serp_api_key == "test-key"
    assert config.input_directory == "input/"
    assert config.output_directory == "output/"
    assert config.cache_directory == "cache/"
    assert config.log_directory == "logs/"
    assert config.request_timeout_seconds == 30
    assert config.max_retry_attempts == 3


def test_load_config_reads_all_optional_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configured directories and request limits replace their defaults."""

    values = {
        "SERP_API_KEY": "test-key",
        "INPUT_DIRECTORY": "source",
        "OUTPUT_DIRECTORY": "generated",
        "CACHE_DIRECTORY": "saved-cache",
        "LOG_DIRECTORY": "application-logs",
        "REQUEST_TIMEOUT_SECONDS": "45",
        "MAX_RETRY_ATTEMPTS": "4",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    config = load_config()

    assert config.input_directory == "source"
    assert config.output_directory == "generated"
    assert config.cache_directory == "saved-cache"
    assert config.log_directory == "application-logs"
    assert config.request_timeout_seconds == 45
    assert config.max_retry_attempts == 4


@pytest.mark.parametrize("value", [None, "", "   "])
def test_load_config_rejects_missing_api_key(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    """A missing or blank API key produces an actionable validation error."""

    if value is not None:
        monkeypatch.setenv("SERP_API_KEY", value)

    with pytest.raises(ValueError, match="SERP_API_KEY is required"):
        load_config()


@pytest.mark.parametrize(
    ("name", "value"),
    [("REQUEST_TIMEOUT_SECONDS", "0"), ("MAX_RETRY_ATTEMPTS", "many")],
)
def test_load_config_rejects_invalid_positive_integers(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    """Request settings must be parseable, positive integers."""

    monkeypatch.setenv("SERP_API_KEY", "test-key")
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=f"{name} must be a positive integer"):
        load_config()
