"""Data model definitions used by CompanyLocationEnricher."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchResult:
    """The most relevant result returned for a company search."""

    company_name: str
    title: str | None = None
    url: str | None = None
    snippet: str | None = None
