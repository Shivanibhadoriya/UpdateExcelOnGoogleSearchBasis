"""Tests ensuring SerpApi runtime settings originate from ``Config``."""

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import Config
from search_service import SerpApiSearchService


class SearchServiceConfigurationTests(unittest.TestCase):
    """Verify that search service requests use only injected configuration."""

    def test_request_uses_api_key_and_timeout_from_config(self) -> None:
        """Configured credentials and timeout reach the HTTP request unchanged."""

        config = Config(
            serp_api_key="configured-key",
            input_directory="input/",
            output_directory="output/",
            cache_directory="cache/",
            log_directory="logs/",
            request_timeout_seconds=17,
            max_retry_attempts=1,
        )
        response = Mock(status_code=200)
        response.json.return_value = {}
        response.raise_for_status.return_value = None

        with patch("search_service.requests.get", return_value=response) as get:
            SerpApiSearchService(config).search("Example Corp")

        get.assert_called_once_with(
            SerpApiSearchService.ENDPOINT,
            params={
                "engine": "google",
                "q": "Example Corp",
                "api_key": "configured-key",
            },
            timeout=17,
        )


if __name__ == "__main__":
    unittest.main()
