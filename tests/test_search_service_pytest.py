"""Pytest unit tests for SerpAPI response handling without network access."""

from unittest.mock import Mock, patch

import pytest
import requests

from config import Config
from search_service import SearchRequestError, SerpApiSearchService


@pytest.fixture
def config() -> Config:
    """Return deterministic search configuration for mocked requests."""

    return Config(
        serp_api_key="test-key",
        input_directory="input/",
        output_directory="output/",
        cache_directory="cache/",
        log_directory="logs/",
        request_timeout_seconds=12,
        max_retry_attempts=1,
    )


def test_search_maps_mocked_serpapi_response(config: Config) -> None:
    """A mocked HTTP response maps knowledge graph and organic results safely."""

    response = Mock(status_code=200)
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "knowledge_graph": {"Headquarters": "Pune, Maharashtra, India"},
        "organic_results": [
            {
                "title": "Example Corp",
                "link": "https://example.test",
                "snippet": "Pune, Maharashtra, India",
            }
        ],
    }

    with patch("search_service.requests.get", return_value=response) as get:
        result = SerpApiSearchService(config).search("Example Corp")

    assert result.title == "Example Corp"
    assert result.url == "https://example.test"
    assert result.knowledge_graph == {"Headquarters": "Pune, Maharashtra, India"}
    assert len(result.organic_results) == 1
    get.assert_called_once()


def test_search_wraps_non_successful_mocked_response(config: Config) -> None:
    """A mocked HTTP error is exposed as a service-specific exception."""

    response = Mock(status_code=400)
    response.raise_for_status.side_effect = requests.HTTPError("bad request")

    with patch("search_service.requests.get", return_value=response):
        with pytest.raises(SearchRequestError, match="HTTP 400"):
            SerpApiSearchService(config).search("Example Corp")
