"""
Utilities for working with Korean administrative district (시군구) codes.

This module is inspired by https://github.com/divetocode/budongsan-api and
loads the bundled ``sigungu.json`` dataset to provide convenient lookups.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SigunguInfo:
    """Normalized information for a single 시군구 entry."""

    sido_name: str
    sido_fullname: str
    sido_code: str
    sigungu_name: str
    sigungu_code: str


class SigunguService:
    """Singleton-style helper for sigungu ⇄ code lookups."""

    _instance: SigunguService | None = None

    def __init__(self, data_path: Path | None = None) -> None:
        if data_path is None:
            data_path = Path(__file__).resolve().parent / "sample-data" / "sigungu.json"

        if not data_path.exists():
            raise FileNotFoundError(f"sigungu dataset not found: {data_path}")

        with data_path.open("r", encoding="utf-8") as fp:
            raw_data = json.load(fp)

        sigungu_by_code: dict[str, SigunguInfo] = {}
        sigungu_by_name: dict[str, list[SigunguInfo]] = {}

        for sido_entry in raw_data:
            sido_name = sido_entry.get("sido_name", "")
            sido_fullname = sido_entry.get("sido_fullname", sido_name)
            sido_code = str(sido_entry.get("sido_code", "")).zfill(2)

            for sigungu in sido_entry.get("sigungu_array", []):
                sigungu_name = sigungu.get("sigungu_name", "")
                sigungu_code = str(sigungu.get("sigungu_code", "")).zfill(5)

                info = SigunguInfo(
                    sido_name=sido_name,
                    sido_fullname=sido_fullname,
                    sido_code=sido_code,
                    sigungu_name=sigungu_name,
                    sigungu_code=sigungu_code,
                )

                sigungu_by_code[sigungu_code] = info
                sigungu_by_name.setdefault(sigungu_name, []).append(info)

        self._sigungu_by_code = sigungu_by_code
        self._sigungu_by_name = sigungu_by_name

    @classmethod
    def get_instance(cls) -> SigunguService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def all_sigungu(self) -> Iterable[SigunguInfo]:
        """Return an iterable of all known sigungu entries."""
        return self._sigungu_by_code.values()

    def get_by_code(self, code: str) -> SigunguInfo | None:
        """Look up sigungu metadata using the 5-digit administrative code."""
        return self._sigungu_by_code.get(str(code).zfill(5))

    def get_by_name(self, name: str, *, sido: str | None = None) -> SigunguInfo | None:
        """Resolve sigungu information by Korean name, optionally filtered by 시/도."""
        candidates = self._sigungu_by_name.get(name)
        if not candidates:
            return None

        if sido:
            normalized_sido = sido.replace(" ", "")
            for info in candidates:
                if (
                    info.sido_name.replace(" ", "") == normalized_sido
                    or info.sido_fullname.replace(" ", "") == normalized_sido
                ):
                    return info

        return candidates[0]

    def get_sigungu_map(self, key: str = "code") -> Mapping[str, SigunguInfo]:
        """
        Return a mapping of sigungu keyed either by ``code`` (default) or ``name``.
        """
        if key not in {"code", "name"}:
            raise ValueError("key must be 'code' or 'name'")

        if key == "code":
            return self._sigungu_by_code

        return {name: infos[0] for name, infos in self._sigungu_by_name.items()}


SigunguServiceSingleton = SigunguService.get_instance()
