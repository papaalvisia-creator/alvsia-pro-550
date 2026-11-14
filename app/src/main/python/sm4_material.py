"""Authorized SM4 material provider for the ALVSIA engine.

This module is the **single** source of SM4 key material at runtime. It never
contains project, game, or server keys. Material must be supplied by an
authorized caller through one of the supported channels:

1. Programmatic (preferred inside the app / tests)::

       import sm4_material
       sm4_material.install_material(secret_2=..., secret_4=..., candidates=[...])

2. Environment variable ``ALVSIA_SM4_MATERIAL`` containing a JSON object::

       {"secret_2": "...", "secret_4": "...", "candidates": ["...", "..."]}

3. Environment variable ``ALVSIA_SM4_MATERIAL_FILE`` pointing to a JSON file
   with the same shape (read once, never logged).

If no material has been supplied, every accessor fails **closed** with a clear
:class:`Sm4MaterialUnavailable` error. This is intentional: the public source
tree must not be able to disclose or silently substitute key material.

The legacy constants ``SM4_SECRET_2`` / ``SM4_SECRET_4`` / ``SM4_SECRET_NEW``
are exposed for backwards compatibility, but they are always empty / ``None``
unless material was explicitly installed. Callers that need the real value must
use the ``require_*`` accessors so the failure mode is explicit.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Iterable, Optional, Sequence, Tuple

__all__ = [
    "Sm4MaterialUnavailable",
    "install_material",
    "clear_material",
    "is_available",
    "get_secret_2",
    "get_secret_4",
    "get_candidates",
    "require_secret_2",
    "require_secret_4",
    "require_candidates",
    "describe",
    "SM4_SECRET_2",
    "SM4_SECRET_4",
    "SM4_SECRET_NEW",
    "SM4_SECRET_NEW_SET",
    "SM4_SECRET_NEW_EXPECTED_COUNT",
    "SM4_SECRET_NEW_VERSION",
]

ENV_INLINE = "ALVSIA_SM4_MATERIAL"
ENV_FILE = "ALVSIA_SM4_MATERIAL_FILE"
SM4_SECRET_NEW_VERSION = "external-authorized"

_LOCK = threading.RLock()
_SECRET_2: Optional[str] = None
_SECRET_4: Optional[str] = None
_CANDIDATES: Tuple[str, ...] = ()
_SOURCE: str = "unset"

# Backwards-compatible module attributes. These are *never* populated with
# embedded literals; they reflect whatever authorized material was installed.
SM4_SECRET_2: Optional[str] = None
SM4_SECRET_4: Optional[str] = None
SM4_SECRET_NEW: Tuple[str, ...] = ()
SM4_SECRET_NEW_SET: frozenset = frozenset()
SM4_SECRET_NEW_EXPECTED_COUNT = 0


class Sm4MaterialUnavailable(RuntimeError):
    """Raised when SM4 material is required but no authorized source exists."""


def _validate_value(name: str, value) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string, got {type(value).__name__}")
    if not (1 <= len(value) <= 64):
        raise ValueError(f"{name} length must be 1..64, got {len(value)}")
    return value


def _normalize_candidates(candidates: Optional[Iterable[str]]) -> Tuple[str, ...]:
    if not candidates:
        return ()
    values = tuple(candidates)
    for idx, key in enumerate(values):
        if not isinstance(key, str) or not (1 <= len(key) <= 64):
            raise ValueError(
                f"candidate[{idx}] must be a string of length 1..64"
            )
    return values


def _publish() -> None:
    """Refresh the backwards-compatible module attributes."""
    global SM4_SECRET_2, SM4_SECRET_4, SM4_SECRET_NEW
    global SM4_SECRET_NEW_SET, SM4_SECRET_NEW_EXPECTED_COUNT
    SM4_SECRET_2 = _SECRET_2
    SM4_SECRET_4 = _SECRET_4
    SM4_SECRET_NEW = _CANDIDATES
    SM4_SECRET_NEW_SET = frozenset(_CANDIDATES)
    SM4_SECRET_NEW_EXPECTED_COUNT = len(_CANDIDATES)


def install_material(
    *,
    secret_2: Optional[str] = None,
    secret_4: Optional[str] = None,
    candidates: Optional[Iterable[str]] = None,
    source: str = "caller_supplied",
) -> bool:
    """Install authorized SM4 material. Returns True on success.

    Passing ``None`` for a field leaves the current value untouched. Use
    :func:`clear_material` to wipe everything.
    """
    global _SECRET_2, _SECRET_4, _CANDIDATES, _SOURCE
    with _LOCK:
        if secret_2 is not None:
            _SECRET_2 = _validate_value("secret_2", secret_2)
        if secret_4 is not None:
            _SECRET_4 = _validate_value("secret_4", secret_4)
        if candidates is not None:
            _CANDIDATES = _normalize_candidates(candidates)
        _SOURCE = source or "caller_supplied"
        _publish()
        return True


def clear_material() -> None:
    global _SECRET_2, _SECRET_4, _CANDIDATES, _SOURCE
    with _LOCK:
        _SECRET_2 = None
        _SECRET_4 = None
        _CANDIDATES = ()
        _SOURCE = "unset"
        _publish()


def _load_from_environment() -> None:
    """Best-effort load from env on first access. Never raises."""
    global _SOURCE
    with _LOCK:
        if _SECRET_2 or _SECRET_4 or _CANDIDATES:
            return
        payload = os.environ.get(ENV_INLINE)
        if not payload:
            path = os.environ.get(ENV_FILE)
            if path and os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as handle:
                        payload = handle.read()
                except OSError:
                    return
        if not payload:
            return
        try:
            data = json.loads(payload)
        except (ValueError, TypeError):
            return
        if not isinstance(data, dict):
            return
        try:
            install_material(
                secret_2=data.get("secret_2"),
                secret_4=data.get("secret_4"),
                candidates=data.get("candidates"),
                source="environment",
            )
        except (ValueError, TypeError):
            # Malformed material must not partially install.
            clear_material()


def _ensure_loaded() -> None:
    if _SOURCE == "unset":
        _load_from_environment()


def is_available() -> bool:
    _ensure_loaded()
    return bool(_SECRET_2 or _SECRET_4 or _CANDIDATES)


def get_secret_2() -> Optional[str]:
    _ensure_loaded()
    return _SECRET_2


def get_secret_4() -> Optional[str]:
    _ensure_loaded()
    return _SECRET_4


def get_candidates() -> Sequence[str]:
    _ensure_loaded()
    return _CANDIDATES


def require_secret_2() -> str:
    value = get_secret_2()
    if not value:
        raise Sm4MaterialUnavailable(
            "SM4-2 material is not authorized/supplied; install via "
            "sm4_material.install_material(secret_2=...) or ALVSIA_SM4_MATERIAL"
        )
    return value


def require_secret_4() -> str:
    value = get_secret_4()
    if not value:
        raise Sm4MaterialUnavailable(
            "SM4-4 material is not authorized/supplied; install via "
            "sm4_material.install_material(secret_4=...) or ALVSIA_SM4_MATERIAL"
        )
    return value


def require_candidates() -> Sequence[str]:
    values = get_candidates()
    if not values:
        raise Sm4MaterialUnavailable(
            "SM4 candidate material is not authorized/supplied; install via "
            "sm4_material.install_material(candidates=[...]) or ALVSIA_SM4_MATERIAL"
        )
    return values


def describe() -> dict:
    _ensure_loaded()
    return {
        "available": is_available(),
        "source": _SOURCE,
        "has_secret_2": _SECRET_2 is not None,
        "has_secret_4": _SECRET_4 is not None,
        "candidate_count": len(_CANDIDATES),
        "version": SM4_SECRET_NEW_VERSION,
    }
