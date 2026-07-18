"""Data model definitions used by CompanyLocationEnricher."""

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class Location:
    """A normalized, geographically meaningful company location.

    Attributes:
        city: City or locality of the company location.
        state: State, province, or equivalent administrative area.
        country: Country name in its normalized display form.
    """

    city: str
    state: str
    country: str


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Provider-neutral data returned for a company search.

    The structured fields preserve the SerpAPI sections needed by downstream,
    deterministic processors without coupling those processors to network I/O.
    """

    company_name: str
    title: str | None = None
    url: str | None = None
    snippet: str | None = None
    knowledge_graph: Mapping[str, Any] | None = None
    organic_results: tuple[Mapping[str, Any], ...] = ()
