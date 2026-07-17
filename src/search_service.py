"""Company information search service interfaces."""

from abc import ABC, abstractmethod

from models import SearchResult


class SearchService(ABC):
    """Define the contract for searching company information."""

    @abstractmethod
    def search(self, company_name: str) -> SearchResult:
        """Search for information about ``company_name``.

        Concrete implementations determine how the search is performed. This
        interface intentionally performs no external API calls.
        """
        raise NotImplementedError
