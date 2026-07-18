"""Unit tests for application logging configuration."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import Config
from logger import APPLICATION_LOGGER_NAME, LOG_FILE_NAME, configure_logging


class LoggingConfigurationTests(unittest.TestCase):
    """Verify durable, idempotent logging setup."""

    def setUp(self) -> None:
        """Create an isolated log directory and valid configuration."""

        self.temporary_directory = TemporaryDirectory()
        self.log_directory = Path(self.temporary_directory.name) / "logs"
        self.config = Config(
            serp_api_key="test-key",
            input_directory="input/",
            output_directory="output/",
            cache_directory="cache/",
            log_directory=str(self.log_directory),
            request_timeout_seconds=30,
            max_retry_attempts=3,
        )

    def tearDown(self) -> None:
        """Release all test-owned logging resources and temporary files."""

        logger = __import__("logging").getLogger(APPLICATION_LOGGER_NAME)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()
        self.temporary_directory.cleanup()

    def test_configure_creates_console_and_rotating_file_handlers(self) -> None:
        """The logger creates its directory and both required destinations."""

        logger = configure_logging(self.config)

        self.assertTrue(self.log_directory.is_dir())
        self.assertEqual(logger.name, APPLICATION_LOGGER_NAME)
        self.assertEqual(len(logger.handlers), 2)

        logger.error("test message")
        for handler in logger.handlers:
            handler.flush()

        content = (self.log_directory / LOG_FILE_NAME).read_text(encoding="utf-8")
        self.assertIn("ERROR | test_logger | test message", content)

    def test_reconfiguration_does_not_duplicate_handlers(self) -> None:
        """Repeated configuration leaves exactly one console and one file handler."""

        logger = configure_logging(self.config)
        reconfigured_logger = configure_logging(self.config)

        self.assertIs(logger, reconfigured_logger)
        self.assertEqual(len(reconfigured_logger.handlers), 2)


if __name__ == "__main__":
    unittest.main()
