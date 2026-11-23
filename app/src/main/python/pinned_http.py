"""Fail-closed SPKI pinning for the ALVISIA panel's Python HTTP calls."""
from __future__ import annotations

import base64
import hashlib
import hmac
from urllib.parse import urlparse

PANEL_HOSTS = frozenset(("alvsiapanel.unaux.com",))
# Owner-supplied current leaf and backup CA SPKI pins; match Android Vault.
PANEL_SPKI_PINS = tuple(
    base64.b64decode(p)
    for p in (
        "3dKRo5uvtVM2x5/NJsOEKFEy803l0rPct3Jv0AoiukE=",  # current leaf
        "xwyjb5aN7tSRWj02XSZa2cKGLxXLdKHUBfLT/7twjhQ=",  # ZeroSSL ECC DV SSL CA 2
        "sLVjNUaFYfW7n6EtgBeEpjOlcnBdNPMrZDRF36iwBdE=",  # Sectigo Public Server Authentication Root E46
    )
)


def _read_tlv(data: bytes, pos: int):
    if pos < 0 or pos + 2 > len(data):
        raise ValueError("truncated DER")
    tag = data[pos]
    first = data[pos + 1]
    cursor = pos + 2
    if first & 0x80:
        count = first & 0x7f
        if count == 0 or count > 4 or cursor + count > len(data):
            raise ValueError("invalid DER length")
        length = int.from_bytes(data[cursor:cursor + count], "big")
        cursor += count
    else:
        length = first
    end = cursor + length
    if end > len(data):
        raise ValueError("DER length exceeds certificate")
    return tag, pos, cursor, end, end


def extract_spki_der(cert_der: bytes) -> bytes:
    """Extract the full SubjectPublicKeyInfo DER sequence from an X.509 cert."""
    tag, _, value_start, value_end, _ = _read_tlv(cert_der, 0)
    if tag != 0x30 or value_end != len(cert_der):
        raise ValueError("invalid certificate sequence")
    tag, _, tbs_start, tbs_end, _ = _read_tlv(cert_der, value_start)
    if tag != 0x30:
        raise ValueError("missing TBSCertificate")
    fields = []
    pos = tbs_start
    while pos < tbs_end:
        field = _read_tlv(cert_der, pos)
        fields.append((field[0], field[1], field[4]))
        pos = field[4]
    if pos != tbs_end:
        raise ValueError("malformed TBSCertificate")
    offset = 1 if fields and fields[0][0] == 0xA0 else 0
    spki_index = offset + 5
    if len(fields) <= spki_index or fields[spki_index][0] != 0x30:
        raise ValueError("SubjectPublicKeyInfo not found")
    _, start, end = fields[spki_index]
    return cert_der[start:end]


def panel_post(url: str, **kwargs):
    """POST only to the configured panel, verify system TLS and pin the peer SPKI."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in PANEL_HOSTS:
        raise ValueError("Python panel client refuses an unpinned host")
    import requests
    session = requests.Session()
    session.trust_env = False
    kwargs["verify"] = True
    kwargs["stream"] = True
    response = None
    try:
        response = session.post(url, **kwargs)
        connection = getattr(response.raw, "connection", None)
        if connection is None:
            connection = getattr(response.raw, "_connection", None)
        sock = getattr(connection, "sock", None)
        if sock is None:
            raise requests.exceptions.SSLError("cannot inspect panel TLS peer")
        cert_der = sock.getpeercert(binary_form=True)
        if not cert_der:
            raise requests.exceptions.SSLError("panel peer certificate unavailable")
        actual = hashlib.sha256(extract_spki_der(cert_der)).digest()
        if not any(hmac.compare_digest(actual, pin) for pin in PANEL_SPKI_PINS):
            raise requests.exceptions.SSLError("panel SPKI pin mismatch")
        # Consume only after pin validation so the response can be safely used
        # after the temporary Session is closed.
        _ = response.content
        response.close()
        return response
    except Exception:
        if response is not None:
            response.close()
        raise
    finally:
        session.close()
