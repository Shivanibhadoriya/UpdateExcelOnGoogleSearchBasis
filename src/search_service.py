"""Company information search service interfaces."""

from abc import ABC, abstractmethod
import logging
from typing import Any

import requests
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import Config
from models import SearchResult


logger = logging.getLogger("company_location_enricher.search_service")
logger.addHandler(logging.NullHandler())


class SearchServiceError(Exception):
    """Base exception for search service failures."""


class SearchConfigurationError(SearchServiceError):
    """Raised when the search provider is not configured."""


class SearchRequestError(SearchServiceError):
    """Raised when a search provider request cannot be completed."""


class TransientSearchError(SearchRequestError):
    """Raised for provider responses that are safe to retry."""


class SearchService(ABC):
    """Define the contract for searching company information."""

    @abstractmethod
    def search(self, company_name: str) -> SearchResult:
        """Search for information about ``company_name``.

        Concrete implementations determine how the search is performed. This
        interface intentionally performs no external API calls.
        """
        raise NotImplementedError


class SerpApiSearchService(SearchService):
    """Search company information through SerpApi's Google search endpoint."""

    ENDPOINT = "https://serpapi.com/search.json"

    def __init__(self, config: Config) -> None:
        """Create the service from validated application configuration.

        Args:
            config: The application's single source of runtime configuration.
        """

        self._config = config

    def search(self, company_name: str) -> SearchResult:
        """Return the first organic SerpApi result for ``company_name``.

        A successful search with no organic results returns a ``SearchResult``
        whose result-detail fields are ``None``.
        """
        if not company_name.strip():
            raise ValueError("company_name must not be empty")

        if not self._config.serp_api_key:
            logger.error("SerpApi search is not configured: SERP_API_KEY is missing.")
            raise SearchConfigurationError("SERP_API_KEY is not configured")

        try:
            payload = self._fetch(company_name)
        except (requests.RequestException, SearchRequestError) as error:
            logger.error("SerpApi search failed for company %r: %s", company_name, error)
            if isinstance(error, SearchRequestError):
                raise
            raise SearchRequestError("Unable to complete SerpApi search") from error

        provider_error = payload.get("error")
        if isinstance(provider_error, str) and provider_error:
            logger.error("SerpApi returned an error for company %r: %s", company_name, provider_error)
            raise SearchRequestError("SerpApi returned an error response")

        return self._to_search_result(company_name, payload)

    def _fetch(self, company_name: str) -> dict[str, Any]:
        """Fetch a SerpApi response using the configured retry policy."""

        retrying = Retrying(
            retry=retry_if_exception_type(
                (requests.RequestException, TransientSearchError)
            ),
            stop=stop_after_attempt(self._config.max_retry_attempts),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            reraise=True,
        )
        return retrying(self._request, company_name)

    def _request(self, company_name: str) -> dict[str, Any]:
        """Perform one SerpApi request using values from ``Config``."""

        response = requests.get(
            self.ENDPOINT,
            params={
                "engine": "google",
                "q": company_name,
                "api_key": self._config.serp_api_key,
            },
            timeout=self._config.request_timeout_seconds,
        )

        if response.status_code == 429 or response.status_code >= 500:
            raise TransientSearchError(
                f"SerpApi temporarily unavailable (HTTP {response.status_code})"
            )

        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            raise SearchRequestError(
                f"SerpApi rejected the request (HTTP {response.status_code})"
            ) from error

        try:
            payload = response.json()
        except ValueError as error:
            raise SearchRequestError("SerpApi returned invalid JSON") from error
        if not isinstance(payload, dict):
            raise SearchRequestError("SerpApi returned an invalid response payload")
        return payload

    @staticmethod
    def _to_search_result(company_name: str, payload: dict[str, Any]) -> SearchResult:
        """Map SerpApi sections to the provider-neutral search-result model."""
        organic_results = payload.get("organic_results")
        normalized_organic_results = (
            tuple(item for item in organic_results if isinstance(item, dict))
            if isinstance(organic_results, list)
            else ()
        )
        first_result = (
            normalized_organic_results[0]
            if normalized_organic_results
            else {}
        )
        knowledge_graph = payload.get("knowledge_graph")

        return SearchResult(
            company_name=company_name,
            title=SerpApiSearchService._string_value(first_result, "title"),
            url=SerpApiSearchService._string_value(first_result, "link"),
            snippet=SerpApiSearchService._string_value(first_result, "snippet"),
            knowledge_graph=(
                knowledge_graph if isinstance(knowledge_graph, dict) else None
            ),
            organic_results=normalized_organic_results,
        )

    @staticmethod
    def _string_value(payload: dict[str, Any], key: str) -> str | None:
        """Return ``payload[key]`` only when it is a string."""

        value = payload.get(key)
        return value if isinstance(value, str) else None
