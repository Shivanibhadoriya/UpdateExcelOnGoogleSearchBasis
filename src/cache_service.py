"""Persistent, file-based cache support for company locations."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional, Union

from models import Location


PathLike = Union[str, Path]


class CacheService:
    """Persist normalized company locations as JSON files.

    Each normalized company name maps to one SHA-256-named JSON file. Hashing
    avoids unsafe filenames while the original normalized key remains in the
    file for validation. The service creates its cache directory during
    initialization and performs no network or business-logic operations.
    """

    def __init__(self, cache_directory: PathLike) -> None:
        """Create a cache service rooted at ``cache_directory``.

        Args:
            cache_directory: Directory in which JSON cache entries are stored.

        Raises:
            OSError: If the cache directory cannot be created.
        """

        self._cache_directory = Path(cache_directory)
        self._cache_directory.mkdir(parents=True, exist_ok=True)

    def get(self, company_name: str) -> Optional[Location]:
        """Return the cached location for ``company_name``, if it is valid.

        Company names are normalized before lookup, so differences in casing
        and repeated whitespace do not create cache misses. Missing, malformed,
        or mismatched entries are treated as cache misses.

        Args:
            company_name: Company name used as the cache lookup key.

        Returns:
            The cached :class:`Location`, or ``None`` when no valid entry exists.
        """

        normalized_name = self._normalize_company_name(company_name)
        path = self._entry_path(normalized_name)
        if not path.is_file():
            return None

        try:
            with path.open("r", encoding="utf-8") as cache_file:
                payload = json.load(cache_file)
        except (OSError, json.JSONDecodeError):
            return None

        return self._location_from_payload(payload, normalized_name)

    def put(
        self,
        company_name: str,
        location: Location,
        *,
        overwrite: bool = False,
    ) -> None:
        """Store ``location`` for ``company_name``.

        Existing files are never replaced unless ``overwrite=True`` is passed
        explicitly. New entries are created exclusively, preventing accidental
        replacement by another process that writes the same key first.

        Args:
            company_name: Company name to use as the cache key.
            location: Normalized company location to persist.
            overwrite: Whether an existing entry may be replaced.

        Raises:
            ValueError: If ``company_name`` is empty or ``location`` is invalid.
            OSError: If the entry cannot be written.
        """

        normalized_name = self._normalize_company_name(company_name)
        self._validate_location(location)
        path = self._entry_path(normalized_name)
        payload = {
            "company_name": normalized_name,
            "location": {
                "city": location.city,
                "state": location.state,
                "country": location.country,
            },
        }

        if overwrite:
            self._replace_entry(path, payload)
            return

        self._create_entry(path, payload)

    def contains(self, company_name: str) -> bool:
        """Return whether a valid cache entry exists for ``company_name``.

        Args:
            company_name: Company name to check, case-insensitively.

        Returns:
            ``True`` only when the corresponding entry can be read as a
            validated :class:`Location`.
        """

        return self.get(company_name) is not None

    @staticmethod
    def _normalize_company_name(company_name: str) -> str:
        """Return a case-insensitive, whitespace-normalized company key.

        Raises:
            ValueError: If ``company_name`` is empty or contains only whitespace.
        """

        normalized_name = " ".join(company_name.casefold().split())
        if not normalized_name:
            raise ValueError("company_name must not be empty.")
        return normalized_name

    def _entry_path(self, normalized_name: str) -> Path:
        """Return the deterministic JSON filename for a normalized company name."""

        digest = hashlib.sha256(normalized_name.encode("utf-8")).hexdigest()
        return self._cache_directory / f"{digest}.json"

    def _create_entry(self, path: Path, payload: dict[str, object]) -> None:
        """Create a new entry without replacing an existing file."""

        try:
            with path.open("x", encoding="utf-8") as cache_file:
                json.dump(payload, cache_file, ensure_ascii=False, indent=2)
                cache_file.write("\n")
        except FileExistsError:
            return

    def _replace_entry(self, path: Path, payload: dict[str, object]) -> None:
        """Atomically replace an entry after explicit overwrite authorization."""

        temporary_path: Optional[Path] = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._cache_directory,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(payload, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, path)
        except BaseException:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _location_from_payload(
        payload: object, normalized_name: str
    ) -> Optional[Location]:
        """Deserialize a location only when the stored key and fields are valid."""

        if not isinstance(payload, dict):
            return None
        if payload.get("company_name") != normalized_name:
            return None
        location = payload.get("location")
        if not isinstance(location, dict):
            return None

        city = location.get("city")
        state = location.get("state")
        country = location.get("country")
        values = (city, state, country)
        if not all(isinstance(value, str) and value.strip() for value in values):
            return None
        return Location(city=city, state=state, country=country)

    @staticmethod
    def _validate_location(location: Location) -> None:
        """Raise ``ValueError`` when a location cannot be safely persisted."""

        if not isinstance(location, Location):
            raise ValueError("location must be a Location instance.")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (location.city, location.state, location.country)
        ):
            raise ValueError("location city, state, and country must be non-empty.")
