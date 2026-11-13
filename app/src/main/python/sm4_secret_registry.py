"""Safe SM4 candidate registry interface.

No project/game/server keys are embedded in the application source.
SM4 candidates must be supplied by the caller from an authorized local
configuration or test fixture. This module intentionally exposes an empty
default registry so a public source tree cannot disclose key material.
"""

SM4_SECRET_NEW_VERSION = "external-authorized"
SM4_SECRET_NEW_EXPECTED_COUNT = 0
SM4_SECRET_NEW = ()
SM4_SECRET_NEW_SET = frozenset()


def validate_sm4_secret_set() -> dict:
    """Validate the built-in registry contract without shipping secrets."""
    valid = (
        SM4_SECRET_NEW == ()
        and len(SM4_SECRET_NEW_SET) == 0
        and SM4_SECRET_NEW_EXPECTED_COUNT == 0
    )
    return {
        "ok": valid,
        "version": SM4_SECRET_NEW_VERSION,
        "count": 0,
        "expected_count": 0,
        "source": "caller_supplied",
    }


def validate_candidate_keys(candidates) -> dict:
    """Validate caller-supplied SM4 candidates without persisting them."""
    values = tuple(candidates or ())
    valid = all(isinstance(key, str) and 1 <= len(key) <= 64 for key in values)
    return {
        "ok": valid,
        "count": len(values),
        "source": "caller_supplied",
    }
