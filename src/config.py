"""Configuration loading and validation for CompanyLocationEnricher.

Values are read from environment variables after ``python-dotenv`` loads the
project's ``.env`` file. This module deliberately contains no application
business logic.
"""

from dataclasses import dataclass
import os

from dotenv import load_dotenv


DEFAULT_INPUT_DIRECTORY: str = "input/"
DEFAULT_OUTPUT_DIRECTORY: str = "output/"
DEFAULT_CACHE_DIRECTORY: str = "cache/"
DEFAULT_LOG_DIRECTORY: str = "logs/"
DEFAULT_REQUEST_TIMEOUT_SECONDS: int = 30
DEFAULT_MAX_RETRY_ATTEMPTS: int = 3


@dataclass(frozen=True)
class Config:
    """Immutable application configuration sourced from environment variables.

    Attributes:
        serp_api_key: API key used to authenticate SerpApi requests.
        input_directory: Directory containing source files to process.
        output_directory: Directory for generated output files.
        cache_directory: Directory for cached request data.
        log_directory: Directory for application log files.
        request_timeout_seconds: Maximum duration of an HTTP request in seconds.
        max_retry_attempts: Maximum number of attempts for a retriable request.
    """

    serp_api_key: str
    input_directory: str
    output_directory: str
    cache_directory: str
    log_directory: str
    request_timeout_seconds: int
    max_retry_attempts: int


def _get_positive_integer(name: str, default: int) -> int:
    """Return a positive integer environment value or its default.

    Args:
        name: Name of the environment variable to read.
        default: Value to use when the variable is unset or empty.

    Raises:
        ValueError: If the configured value is not a positive integer.
    """

    value = os.getenv(name)
    if value is None or not value.strip():
        return default

    try:
        parsed_value = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer.") from error

    if parsed_value <= 0:
        raise ValueError(f"{name} must be a positive integer.")

    return parsed_value


def load_config() -> Config:
    """Load, validate, and return the fully initialized application config.

    The function loads variables from a ``.env`` file, preserving any values
    already set in the process environment. Directory settings default to the
    project's conventional ``input/``, ``output/``, ``cache/``, and ``logs/``
    locations. Request settings have safe defaults when they are not supplied.

    Raises:
        ValueError: If ``SERP_API_KEY`` is missing or numeric values are invalid.

    Returns:
        A validated :class:`Config` instance.
    """

    load_dotenv()

    serp_api_key = os.getenv("SERP_API_KEY", "").strip()
    if not serp_api_key:
        raise ValueError("SERP_API_KEY is required. Set it in the .env file.")

    return Config(
        serp_api_key=serp_api_key,
        input_directory=os.getenv("INPUT_DIRECTORY", DEFAULT_INPUT_DIRECTORY),
        output_directory=os.getenv("OUTPUT_DIRECTORY", DEFAULT_OUTPUT_DIRECTORY),
        cache_directory=os.getenv("CACHE_DIRECTORY", DEFAULT_CACHE_DIRECTORY),
        log_directory=os.getenv("LOG_DIRECTORY", DEFAULT_LOG_DIRECTORY),
        request_timeout_seconds=_get_positive_integer(
            "REQUEST_TIMEOUT_SECONDS", DEFAULT_REQUEST_TIMEOUT_SECONDS
        ),
        max_retry_attempts=_get_positive_integer(
            "MAX_RETRY_ATTEMPTS", DEFAULT_MAX_RETRY_ATTEMPTS
        ),
    )
