"""Unit tests for persistent company-location cache behavior."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cache_service import CacheService
from models import Location


class CacheServiceTests(unittest.TestCase):
    """Verify persistence, normalized keys, and overwrite protection."""

    def setUp(self) -> None:
        """Create an isolated, automatically-created cache directory."""

        self.temporary_directory = TemporaryDirectory()
        self.cache_path = Path(self.temporary_directory.name) / "company-cache"
        self.service = CacheService(self.cache_path)

    def tearDown(self) -> None:
        """Remove the isolated cache directory."""

        self.temporary_directory.cleanup()

    def test_directory_is_created_and_empty_lookup_is_a_miss(self) -> None:
        """The constructor creates the directory and absent keys return None."""

        self.assertTrue(self.cache_path.is_dir())
        self.assertIsNone(self.service.get("Example Corp"))
        self.assertFalse(self.service.contains("Example Corp"))

    def test_lookup_is_case_and_whitespace_insensitive(self) -> None:
        """Equivalent company names resolve to the same persisted entry."""

        location = Location("Bengaluru", "Karnataka", "India")
        self.service.put("  Example   Corp ", location)

        self.assertEqual(self.service.get("example corp"), location)
        self.assertTrue(self.service.contains("EXAMPLE CORP"))

    def test_entries_persist_for_a_new_service_instance(self) -> None:
        """A new instance reads entries written by an earlier application run."""

        location = Location("Pune", "Maharashtra", "India")
        self.service.put("Example Corp", location)

        reloaded_service = CacheService(self.cache_path)

        self.assertEqual(reloaded_service.get("Example Corp"), location)

    def test_existing_entry_requires_explicit_overwrite(self) -> None:
        """A default put keeps the original location, while opt-in replaces it."""

        original = Location("Pune", "Maharashtra", "India")
        replacement = Location("Bengaluru", "Karnataka", "India")
        self.service.put("Example Corp", original)
        self.service.put("Example Corp", replacement)

        self.assertEqual(self.service.get("Example Corp"), original)

        self.service.put("Example Corp", replacement, overwrite=True)

        self.assertEqual(self.service.get("Example Corp"), replacement)


if __name__ == "__main__":
    unittest.main()
