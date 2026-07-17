"""Company information search service interfaces."""

from abc import ABC, abstractmethod
import logging
import os
from typing import Any

import requests
from dotenv import load_dotenv
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from models import SearchResult


logger = logging.getLogger(__name__)
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
    REQUEST_TIMEOUT_SECONDS = 10

    def __init__(self, api_key: str | None = None) -> None:
        """Create the service, loading ``SERPAPI_API_KEY`` from ``.env``.

        ``api_key`` is accepted for controlled dependency injection, while the
        default path always reads the key from the application's environment.
        """
        load_dotenv()
        self._api_key = api_key or os.getenv("SERPAPI_API_KEY")

    def search(self, company_name: str) -> SearchResult:
        """Return the first organic SerpApi result for ``company_name``.

        A successful search with no organic results returns a ``SearchResult``
        whose result-detail fields are ``None``.
        """
        if not company_name.strip():
            raise ValueError("company_name must not be empty")

        if not self._api_key:
            logger.error("SerpApi search is not configured: SERPAPI_API_KEY is missing.")
            raise SearchConfigurationError("SERPAPI_API_KEY is not configured")

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

    @retry(
        retry=retry_if_exception_type((requests.RequestException, TransientSearchError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        reraise=True,
    )
    def _fetch(self, company_name: str) -> dict[str, Any]:
        """Fetch a SerpApi response, retrying transient failures only."""
        response = requests.get(
            self.ENDPOINT,
            params={"engine": "google", "q": company_name, "api_key": self._api_key},
            timeout=self.REQUEST_TIMEOUT_SECONDS,
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
        """Map the first organic SerpApi item to the provider-neutral model."""
        organic_results = payload.get("organic_results")
        first_result = (
            organic_results[0]
            if isinstance(organic_results, list) and organic_results and isinstance(organic_results[0], dict)
            else {}
        )

        return SearchResult(
            company_name=company_name,
            title=first_result.get("title") if isinstance(first_result.get("title"), str) else None,
            url=first_result.get("link") if isinstance(first_result.get("link"), str) else None,
            snippet=first_result.get("snippet") if isinstance(first_result.get("snippet"), str) else None,
        )
