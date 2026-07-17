"""Data model definitions used by CompanyLocationEnricher."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchResult:
    """The result returned for a company search.

    The abstraction intentionally captures only the requested company name.
    Provider-specific fields can be added when a concrete search integration is
    introduced.
    """

    company_name: str
