"""Deterministic extraction of normalized locations from search results."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any, Optional

from models import Location, SearchResult


class LocationService:
    """Extract a reliable company location from already-fetched search data.

    The service performs no I/O and has no mutable state, which makes every
    extraction deterministic and straightforward to unit test. It evaluates
    evidence in this order: India-office fields, headquarters fields, then
    reliable address fields and organic-result snippets.
    """

    _INDIA_OFFICE_KEYS = (
        "india office",
        "india office address",
        "india offices",
    )
    _HEADQUARTERS_KEYS = (
        "headquarters",
        "headquarters location",
        "company headquarters",
        "hq",
    )
    _ADDRESS_KEYS = ("address", "location", "office address")
    _TEXT_KEYS = ("address", "snippet", "description", "title")
    _COUNTRIES = {
        "india": "India",
        "usa": "United States",
        "u.s.a.": "United States",
        "united states": "United States",
        "united states of america": "United States",
        "uk": "United Kingdom",
        "u.k.": "United Kingdom",
        "united kingdom": "United Kingdom",
        "uae": "United Arab Emirates",
        "u.a.e.": "United Arab Emirates",
        "united arab emirates": "United Arab Emirates",
        "canada": "Canada",
        "australia": "Australia",
        "singapore": "Singapore",
        "germany": "Germany",
        "france": "France",
        "japan": "Japan",
    }
    _INDIAN_STATES = {
        "andhra pradesh": "Andhra Pradesh",
        "assam": "Assam",
        "bihar": "Bihar",
        "chandigarh": "Chandigarh",
        "chhattisgarh": "Chhattisgarh",
        "delhi": "Delhi",
        "goa": "Goa",
        "gujarat": "Gujarat",
        "haryana": "Haryana",
        "karnataka": "Karnataka",
        "kerala": "Kerala",
        "madhya pradesh": "Madhya Pradesh",
        "maharashtra": "Maharashtra",
        "odisha": "Odisha",
        "orissa": "Odisha",
        "punjab": "Punjab",
        "rajasthan": "Rajasthan",
        "tamil nadu": "Tamil Nadu",
        "telangana": "Telangana",
        "uttar pradesh": "Uttar Pradesh",
        "west bengal": "West Bengal",
        "jammu and kashmir": "Jammu and Kashmir",
    }
    _US_STATES = {
        "california": "California",
        "new york": "New York",
        "texas": "Texas",
        "washington": "Washington",
        "massachusetts": "Massachusetts",
        "illinois": "Illinois",
        "florida": "Florida",
        "virginia": "Virginia",
        "new jersey": "New Jersey",
        "colorado": "Colorado",
    }
    _STREET_MARKERS = re.compile(
        r"\b(?:street|st\.?|road|rd\.?|avenue|ave\.?|lane|ln\.?|"
        r"boulevard|blvd\.?|floor|building|tower|block|plot|suite|unit|"
        r"sector|near|behind)\b",
        re.IGNORECASE,
    )
    _POSTAL_CODE = re.compile(r"\b\d{5,6}(?:-\d{4})?\b")
    _PHONE_NUMBER = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
    _WHITESPACE = re.compile(r"\s+")

    def extract_location(self, search_result: SearchResult) -> Optional[Location]:
        """Return the highest-priority reliable location in ``search_result``.

        India-office evidence wins over headquarters evidence. If neither is
        usable, the method checks labelled addresses before organic results and
        snippets. A result is returned only when city, state, and country can
        all be identified without guessing.
        """

        knowledge_graph = search_result.knowledge_graph or {}
        for keys in (
            self._INDIA_OFFICE_KEYS,
            self._HEADQUARTERS_KEYS,
            self._ADDRESS_KEYS,
        ):
            values = self._values_for_keys(knowledge_graph, keys)
            location = self._first_location(values)
            if location is not None:
                return location

        return self._first_location(self._organic_and_snippet_values(search_result))

    def _first_location(self, values: Iterable[object]) -> Optional[Location]:
        """Parse candidates in order and return the first reliable location."""

        for value in values:
            location = self._parse_candidate(value)
            if location is not None:
                return location
        return None

    def _values_for_keys(
        self, source: Mapping[str, Any], accepted_keys: Iterable[str]
    ) -> Iterable[object]:
        """Yield mapping values whose normalized keys are accepted."""

        accepted = {self._normalise_key(key) for key in accepted_keys}
        for key, value in source.items():
            if isinstance(key, str) and self._normalise_key(key) in accepted:
                yield value

    def _organic_and_snippet_values(
        self, search_result: SearchResult
    ) -> Iterable[object]:
        """Yield address-bearing organic fields followed by the main snippet."""

        for result in search_result.organic_results:
            for key in self._TEXT_KEYS:
                value = result.get(key)
                if isinstance(value, str):
                    yield value
        if search_result.snippet:
            yield search_result.snippet

    def _parse_candidate(self, value: object) -> Optional[Location]:
        """Parse a structured or textual address candidate without guessing."""

        if isinstance(value, Mapping):
            return self._parse_structured_candidate(value)
        if not isinstance(value, str):
            return None
        return self._parse_address_text(value)

    def _parse_structured_candidate(
        self, value: Mapping[object, object]
    ) -> Optional[Location]:
        """Build a location from explicit city, state, and country fields."""

        city = self._string_value(value, "city")
        state = self._string_value(value, "state")
        country = self._string_value(value, "country")
        if city and state and country:
            return self._build_location(city, state, country)

        for key in self._ADDRESS_KEYS:
            address = self._string_value(value, key)
            if address:
                return self._parse_address_text(address)
        return None

    def _parse_address_text(self, text: str) -> Optional[Location]:
        """Extract city, state, and country from a comma-separated address."""

        cleaned = self._clean_text(text)
        if not cleaned:
            return None
        parts = [part.strip(" .") for part in re.split(r"[,;|\n]", cleaned)]
        parts = [part for part in parts if part and not self._is_street_part(part)]
        if len(parts) < 3:
            return None

        country_index, country = self._find_country(parts)
        if country_index is None or country is None or country_index < 2:
            return None

        state_index, state = self._find_state(parts[:country_index], country)
        if state_index is None or state is None or state_index < 1:
            return None

        city = self._extract_city(parts[state_index - 1])
        return self._build_location(city, state, country)

    @staticmethod
    def _extract_city(value: str) -> str:
        """Remove common prose prefixes from a city-sized address segment."""

        match = re.search(
            r"(?:based|headquartered|located|operating|office)\s+in\s+(.+)$",
            value,
            flags=re.IGNORECASE,
        )
        return match.group(1).strip() if match else value

    def _find_country(
        self, parts: list[str]
    ) -> tuple[Optional[int], Optional[str]]:
        """Return the rightmost recognized country segment and its index."""

        for index in range(len(parts) - 1, -1, -1):
            country = self._COUNTRIES.get(parts[index].casefold())
            if country:
                return index, country
        return None, None

    def _find_state(
        self, parts: list[str], country: str
    ) -> tuple[Optional[int], Optional[str]]:
        """Return a recognized state appropriate to ``country``."""

        states = self._INDIAN_STATES if country == "India" else self._US_STATES
        for index in range(len(parts) - 1, -1, -1):
            state = states.get(parts[index].casefold())
            if state:
                return index, state
        return None, None

    def _build_location(
        self, city: str, state: str, country: str
    ) -> Optional[Location]:
        """Validate and normalize explicit location components."""

        normalized_city = self._normalise_component(city)
        normalized_country = self._COUNTRIES.get(country.casefold())
        states = (
            self._INDIAN_STATES
            if normalized_country == "India"
            else self._US_STATES
        )
        normalized_state = states.get(state.casefold())
        if not normalized_city or not normalized_country or not normalized_state:
            return None
        if self._is_street_part(normalized_city):
            return None
        return Location(normalized_city, normalized_state, normalized_country)

    def _clean_text(self, text: str) -> str:
        """Remove phone numbers and postal codes from text before parsing."""

        without_phone = self._PHONE_NUMBER.sub("", text)
        without_postal_code = self._POSTAL_CODE.sub("", without_phone)
        return self._WHITESPACE.sub(" ", without_postal_code).strip()

    def _is_street_part(self, value: str) -> bool:
        """Return whether a segment is likely street-level address detail."""

        return bool(self._STREET_MARKERS.search(value) or re.search(r"\d", value))

    @staticmethod
    def _normalise_key(value: str) -> str:
        """Return a case-insensitive, whitespace-normalized mapping key."""

        return " ".join(value.casefold().split())

    @staticmethod
    def _normalise_component(value: str) -> str:
        """Return a trimmed and whitespace-normalized location component."""

        return " ".join(value.strip().split())

    @staticmethod
    def _string_value(value: Mapping[object, object], key: str) -> Optional[str]:
        """Return a non-empty string for a case-insensitive mapping key."""

        target = LocationService._normalise_key(key)
        for candidate_key, candidate_value in value.items():
            if (
                isinstance(candidate_key, str)
                and LocationService._normalise_key(candidate_key) == target
                and isinstance(candidate_value, str)
                and candidate_value.strip()
            ):
                return candidate_value
        return None
