"""Unit tests for deterministic company-location extraction."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from location_service import LocationService
from models import Location, SearchResult


class LocationServiceTests(unittest.TestCase):
    """Verify source priority and conservative address parsing."""

    def setUp(self) -> None:
        """Create the stateless service under test."""

        self.service = LocationService()

    def test_india_office_has_priority_over_headquarters(self) -> None:
        """India-office evidence wins when both source fields are present."""

        result = SearchResult(
            company_name="Example Corp",
            knowledge_graph={
                "India Office": "Bengaluru, Karnataka 560001, India",
                "Headquarters": "New York, New York, United States",
            },
        )

        self.assertEqual(
            self.service.extract_location(result),
            Location("Bengaluru", "Karnataka", "India"),
        )

    def test_headquarters_is_used_when_india_office_is_absent(self) -> None:
        """Headquarters data is used before generic address evidence."""

        result = SearchResult(
            company_name="Example Corp",
            knowledge_graph={
                "Headquarters": "Austin, Texas, USA",
                "Address": "Mumbai, Maharashtra, India",
            },
        )

        self.assertEqual(
            self.service.extract_location(result),
            Location("Austin", "Texas", "United States"),
        )

    def test_street_address_and_phone_number_are_discarded(self) -> None:
        """Street-level details do not appear in the normalized location."""

        result = SearchResult(
            company_name="Example Corp",
            knowledge_graph={
                "Address": (
                    "12 Residency Road, Bengaluru, Karnataka 560001, India, "
                    "+91 80 1234 5678"
                )
            },
        )

        self.assertEqual(
            self.service.extract_location(result),
            Location("Bengaluru", "Karnataka", "India"),
        )

    def test_organic_snippet_is_used_after_structured_fields(self) -> None:
        """Organic snippets provide a deterministic fallback source."""

        result = SearchResult(
            company_name="Example Corp",
            organic_results=(
                {
                    "snippet": (
                        "Example Corp is headquartered in Pune, Maharashtra, India."
                    )
                },
            ),
        )

        self.assertEqual(
            self.service.extract_location(result),
            Location("Pune", "Maharashtra", "India"),
        )

    def test_unreliable_data_returns_none(self) -> None:
        """A partial or unrecognized address is not treated as a location."""

        result = SearchResult(company_name="Example Corp", snippet="Call 555-0100")

        self.assertIsNone(self.service.extract_location(result))


if __name__ == "__main__":
    unittest.main()
