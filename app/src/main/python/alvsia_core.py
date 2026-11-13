"""ALVSIA PRO 5.5 — pure PAK core (non-interactive).

Source: cleaned PakCore engine. Branding ALVSIA.
Auth: ALVSIA_APK_SESSION=1 permits low-privilege calls only; protected operations require a valid server-signed RSA grant.
"""
from __future__ import annotations
from __future__ import annotations
import os, re, struct, subprocess, shutil, hashlib, json, sys, zipfile, fnmatch, tempfile, zlib, time, uuid, threading, platform, getpass, urllib.request, urllib.error
from dataclasses import dataclass, field
from pathlib import Path, PurePath, PurePosixPath
from functools import lru_cache
from collections import Counter
from typing import List, Dict, Tuple, Optional, Any, Union
import itertools as it
import math
try:
    import gmalg
except Exception:
    gmalg = None
try:
    from Crypto.Cipher import AES
    from Crypto.Cipher.AES import MODE_CBC
    from Crypto.Hash import SHA1
    from Crypto.Util.Padding import pad, unpad
except Exception:
    AES = None
    MODE_CBC = None
    SHA1 = None
    pad = unpad = None
if SHA1 is None:
    class SHA1:
        digest_size = 20
        @staticmethod
        def new(data=b''):
            class _H:
                def __init__(self, d=b''):
                    self._x = __import__('hashlib').sha1(d if d is not None else b'')
                def digest(self):
                    return self._x.digest()
                def hexdigest(self):
                    return self._x.hexdigest()
                def update(self, d):
                    self._x.update(d)
                    return self
            return _H(data if data is not None else b'')

try:
    from zstandard import ZstdDecompressor, ZstdCompressionDict, DICT_TYPE_AUTO, ZstdCompressor
except Exception:
    ZstdDecompressor = None
    ZstdCompressionDict = None
    DICT_TYPE_AUTO = None
    ZstdCompressor = None


# ---------------------------------------------------------------------------
# ALVSIA V3 CORE — core self-verification (server-signed operation proof)
# ---------------------------------------------------------------------------
_ALVSIA_CORE_BUILD_ID = 'ALVSIA-UNaux-20261028-RSA1'
_ALVSIA_CORE_VERSION = '4.0.0'
_ALVSIA_CORE_RSA_N_B64U = 'p2G8SVBzL8Ic_aTg10HZcc35LJdw2Iv-rP0LyXyyKp-06Ju-_nOxTpDE9gpDoBegkXh7sj37qO94Fx-SZn3JDVdRzKMARzkRSevUX0wOGveXd6JzggcCDe70-P3QhHgPE91HM78QkGeBV0vSebOCLEVjP7l0MjmmBK_7zuK3FuPaMBZUBOi8CwGuW8lhjqbPwwiKM5tHKG5bd9-hWVZ6O-XBP_jiQSafnXX-3Gy_z6LuniDzK79CfxBoxQwJPOOxowHzeVvgcVSy7ubJO3ZzsATsi-JPYCyMtIOC7eKDHFourkFaOYd0i4r838nPAylbpL659vkP2DD3hd4SW5JStPIH20sShkpWsCglhGa0Hukt_kh-HrD9YMhRGdc0Ymc8dU6LnSU4KKb6wmk1LLhgtLC3NoTaM_Yx_3Z5iqrY9ELiLT6teSWlyEpJWOFPkPz39EoThQlDpWf0aO7syXoo3iAXJMUpWUli1qPCC94TSumUEAYwULv1m4_nbLO6WwNR'
_ALVSIA_CORE_RSA_E_B64U = 'AQAB'
_ALVSIA_CORE_DIGESTINFO = bytes.fromhex('3031300d060960864801650304020105000420')
_ALVSIA_CORE_CRITICAL = (
    'alvsiatools.py',
    'alvsia_protectioncore.cpython-314-aarch64-linux-android.so',
    'alvsia_luacore.cpython-314-aarch64-linux-android.so',
    'alvsia_pakcore.cpython-314-aarch64-linux-android.so',
    'alvsia_aimbotcore.cpython-314-aarch64-linux-android.so',
    'alvsia_playerpawncore.cpython-314-aarch64-linux-android.so',
    'EXES/luac',
    'EXES/luadec',
    'EXES/unluac_pro.jar',
    'EXES/LUADEC',
)
_ALVSIA_CORE_ACTIVE_PROOF = None

def _alvsia_core_b64u_decode(value):
    import base64 as _b64
    raw = str(value or '').encode('ascii')
    raw += b'=' * ((4 - len(raw) % 4) % 4)
    return _b64.urlsafe_b64decode(raw)

def _alvsia_core_verify_rs256(message, signature_b64u):
    try:
        n = int.from_bytes(_alvsia_core_b64u_decode(_ALVSIA_CORE_RSA_N_B64U), 'big')
        e = int.from_bytes(_alvsia_core_b64u_decode(_ALVSIA_CORE_RSA_E_B64U), 'big')
        sig = _alvsia_core_b64u_decode(signature_b64u)
        k = (n.bit_length() + 7) // 8
        if len(sig) != k:
            return False
        em = pow(int.from_bytes(sig, 'big'), e, n).to_bytes(k, 'big')
        digest = __import__('hashlib').sha256(str(message).encode('utf-8')).digest()
        t = _ALVSIA_CORE_DIGESTINFO + digest
        if k < len(t) + 11:
            return False
        expected = b'\x00\x01' + b'\xff' * (k - len(t) - 3) + b'\x00' + t
        return em == expected
    except Exception:
        return False

def _alvsia_core_message(fields):
    lines = ['ALVSIA-R4', 'kind=operation_grant']
    for key in ('grant_id','nonce','build_id','manifest_hash','tool_hash','device_id','session_id','operation_id','issued_at','expires_at'):
        lines.append(f'{key}={fields.get(key, "")}')
    return '\n'.join(lines)

def _alvsia_core_sha256_file(path):
    h = __import__('hashlib').sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def _alvsia_core_live_measurement():
    import pathlib as _pl, os as _os
    if _os.environ.get('ALVSIA_APK_SESSION') == '1':
        h = __import__('hashlib').sha256(b'ALVSIA-APK-SESSION').hexdigest()
        return {'manifest_hash': h, 'tool_hash': h}
    root = _pl.Path(__file__).resolve().parent
    files = {}
    for name in _ALVSIA_CORE_CRITICAL:
        p = root / name
        if p.is_file():
            files[name] = _alvsia_core_sha256_file(p)
    if not files:
        h = __import__('hashlib').sha256(b'ALVSIA-DEV').hexdigest()
        return {'manifest_hash': h, 'tool_hash': h}
    canonical = '\n'.join([
        f'version={_ALVSIA_CORE_VERSION}',
        f'build_id={_ALVSIA_CORE_BUILD_ID}',
        *[f'{name}={files[name]}' for name in sorted(files)],
    ])
    th = files.get('alvsiatools.py') or files.get('alvsia_core.py') or list(files.values())[0]
    return {
        'manifest_hash': __import__('hashlib').sha256(canonical.encode('utf-8')).hexdigest(),
        'tool_hash': th,
    }

def _alvsia_core_parse_utc(value):
    import datetime as _dt
    s = str(value or '').strip()
    if not s:
        raise ValueError('missing timestamp')
    # Worker sqlDate() format: YYYY-MM-DD HH:MM:SS (UTC)
    dt = _dt.datetime.strptime(s, '%Y-%m-%d %H:%M:%S').replace(tzinfo=_dt.timezone.utc)
    return dt.timestamp()

def _alvsia_install_operation_proof(proof):
    global _ALVSIA_CORE_ACTIVE_PROOF
    try:
        p = dict(proof or {})
        sig = dict(p.pop('signature', {}) or {})
        if sig.get('alg') != 'RS256' or sig.get('kid') != 'alvsia-r4-20260923':
            raise ValueError
        required = ('grant_id','nonce','build_id','manifest_hash','tool_hash','device_id','session_id','operation_id','issued_at','expires_at')
        if any(not str(p.get(k, '')).strip() for k in required):
            raise ValueError
        _op_tokens = [x.strip() for x in str(p['operation_id']).split(',')]
        if not _op_tokens or len(_op_tokens) > 8 or any(
                not re.fullmatch(r'[a-z0-9_.]{1,48}', item) for item in _op_tokens):
            raise ValueError
        # On Android, bind the signed grant to the exact SessionGate token and
        # HWID supplied by the trusted Kotlin bridge. Never accept a grant minted
        # for another device/session, even when its RSA signature is valid.
        if __import__('os').environ.get('ALVSIA_APK_SESSION') == '1':
            expected_device = __import__('os').environ.get('ALVSIA_EXPECTED_DEVICE_ID', '').strip()
            expected_session = __import__('os').environ.get('ALVSIA_EXPECTED_SESSION_ID', '').strip()
            if not expected_device or not expected_session:
                raise ValueError
            if str(p['device_id']) != expected_device or str(p['session_id']) != expected_session:
                raise ValueError
        if str(p['build_id']) != _ALVSIA_CORE_BUILD_ID:
            raise ValueError
        measurement = _alvsia_core_live_measurement()
        if str(p['manifest_hash']).lower() != measurement['manifest_hash'].lower():
            raise ValueError
        if str(p['tool_hash']).lower() != measurement['tool_hash'].lower():
            raise ValueError
        now = __import__('time').time()
        issued = _alvsia_core_parse_utc(p['issued_at'])
        expires = _alvsia_core_parse_utc(p['expires_at'])
        if expires <= issued or expires - issued > 180 or now < issued - 30 or now >= expires:
            raise ValueError
        if not _alvsia_core_verify_rs256(_alvsia_core_message(p), str(sig.get('value',''))):
            raise ValueError
        p['signature'] = sig
        p['_expires_epoch'] = expires
        _ALVSIA_CORE_ACTIVE_PROOF = p
        return True
    except Exception:
        _ALVSIA_CORE_ACTIVE_PROOF = None
        return False

def _alvsia_install_operation_proof_json(proof_json):
    """Parse a JSON-serialized signed grant from the pinned Kotlin client."""
    try:
        raw = proof_json.decode('utf-8') if isinstance(proof_json, bytes) else str(proof_json or '')
        parsed = __import__('json').loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError('grant payload must be an object')
        return _alvsia_install_operation_proof(parsed)
    except Exception:
        _alvsia_clear_operation_proof()
        return False

def _alvsia_install_operation_grant_token(token, expected_operation):
    """Verify and install a compact RS256 JWT from the current Unaux panel."""
    global _ALVSIA_CORE_ACTIVE_PROOF
    try:
        parts = str(token or '').split('.')
        if len(parts) != 3 or not expected_operation:
            raise ValueError
        header = __import__('json').loads(_alvsia_core_b64u_decode(parts[0]).decode('utf-8'))
        claims = __import__('json').loads(_alvsia_core_b64u_decode(parts[1]).decode('utf-8'))
        if header.get('alg') != 'RS256' or header.get('kid') != 'alvsia-unaux-rsa1':
            raise ValueError
        if claims.get('kid') != 'alvsia-unaux-rsa1' or claims.get('iss') != 'https://alvsiapanel.unaux.com':
            raise ValueError
        if claims.get('aud') != 'com.alvsia.pro' or claims.get('build_id') != _ALVSIA_CORE_BUILD_ID:
            raise ValueError
        if claims.get('operation') != expected_operation or not re.fullmatch(r'[a-z0-9_]{2,64}', str(claims.get('operation',''))):
            raise ValueError
        if not re.fullmatch(r'[a-f0-9]{32}', str(claims.get('jti',''))):
            raise ValueError
        if not re.fullmatch(r'[a-f0-9]{16,64}', str(claims.get('request_id',''))):
            raise ValueError
        session = __import__('os').environ.get('ALVSIA_EXPECTED_SESSION_ID', '').strip()
        device = __import__('os').environ.get('ALVSIA_EXPECTED_DEVICE_ID', '').strip().lower()
        if not re.fullmatch(r'[a-f0-9]{64}', session) or not re.fullmatch(r'[a-f0-9]{64}', device):
            raise ValueError
        if claims.get('session_hash') != session:
            raise ValueError
        if claims.get('hwid_hash') != __import__('hashlib').sha256(device.encode('utf-8')).hexdigest():
            raise ValueError
        if not re.fullmatch(r'[a-f0-9]{64}', str(claims.get('license_hash',''))):
            raise ValueError
        now = __import__('time').time()
        issued, nbf, expires = float(claims.get('iat',0)), float(claims.get('nbf',0)), float(claims.get('exp',0))
        if issued <= 0 or expires <= issued or expires-issued > 180 or nbf > now+5 or issued > now+30 or now >= expires:
            raise ValueError
        if int(claims.get('ttl',0)) < 1 or int(claims.get('ttl',0)) > 180:
            raise ValueError
        if not _alvsia_core_verify_rs256(parts[0] + '.' + parts[1], parts[2]):
            raise ValueError
        _ALVSIA_CORE_ACTIVE_PROOF = {
            'grant_id': claims['jti'], 'nonce': claims['request_id'],
            'build_id': claims['build_id'], 'device_id': device,
            'session_id': session, 'operation_id': claims['operation'],
            '_expires_epoch': expires
        }
        return True
    except Exception:
        _ALVSIA_CORE_ACTIVE_PROOF = None
        return False

def _alvsia_clear_operation_proof():
    global _ALVSIA_CORE_ACTIVE_PROOF
    _ALVSIA_CORE_ACTIVE_PROOF = None

def _alvsia_set_expected_operation_identity(session_id, device_id):
    """Install the trusted Android identity supplied by Kotlin before tool dispatch."""
    import os as _os, re as _re
    session = str(session_id or '').strip()
    device = str(device_id or '').strip().lower()
    if not _re.fullmatch(r'[0-9A-Fa-f]{64}', session) or not _re.fullmatch(r'[0-9a-f]{64}', device):
        _os.environ.pop('ALVSIA_EXPECTED_SESSION_ID', None)
        _os.environ.pop('ALVSIA_EXPECTED_DEVICE_ID', None)
        _alvsia_clear_operation_proof()
        return False
    _os.environ['ALVSIA_EXPECTED_SESSION_ID'] = session
    _os.environ['ALVSIA_EXPECTED_DEVICE_ID'] = device
    return True

def _alvsia_require_operation(allowed_operations):
    """Require a live, server-signed RSA grant for each protected operation."""
    import os as _os, re as _re
    if _os.environ.get('ALVSIA_APK_SESSION') != '1':
        raise RuntimeError('Operation authorization failed: login required')
    session = _os.environ.get('ALVSIA_EXPECTED_SESSION_ID', '').strip()
    device = _os.environ.get('ALVSIA_EXPECTED_DEVICE_ID', '').strip().lower()
    if not _re.fullmatch(r'[0-9a-f]{64}', session) or not _re.fullmatch(r'[0-9a-f]{64}', device):
        raise RuntimeError('Operation authorization failed: session/device binding unavailable')
    if not allowed_operations:
        raise RuntimeError('Operation authorization failed: operation not specified')
    proof = _ALVSIA_CORE_ACTIVE_PROOF
    if not isinstance(proof, dict):
        raise RuntimeError('Operation authorization failed: RSA grant missing')
    if str(proof.get('session_id', '')) != session or str(proof.get('device_id', '')).lower() != device:
        _alvsia_clear_operation_proof()
        raise RuntimeError('Operation authorization failed: grant identity mismatch')
    try:
        expires = float(proof.get('_expires_epoch', 0) or 0)
    except Exception:
        expires = 0
    if __import__('time').time() >= expires:
        _alvsia_clear_operation_proof()
        raise RuntimeError('Operation authorization failed: grant expired')
    granted = {x.strip() for x in str(proof.get('operation_id', '')).split(',') if x.strip()}
    allowed = {str(x).strip() for x in allowed_operations if str(x).strip()}
    # Core internals inherit the server-signed module grant that gates dispatch.
    if any(x.startswith(('pak.', 'advanced.', 'asset.', 'lab.')) for x in allowed):
        allowed.add('pak_tools')
    if any(x.startswith('obb.') for x in allowed):
        allowed.add('obb_tools')
    if any(x.startswith('lua_') for x in allowed):
        allowed.add('lua_tools')
    if not granted.intersection(allowed):
        raise RuntimeError('Operation authorization failed: operation not granted')
    return True

class _AlvsiaPakConsole:
    """Small compatibility console for the adopted bahan.py PAK engine."""
    _tag_re = re.compile('\\[/?[^\\]]+\\]')

    def print(self, *args, **kwargs):
        rendered = ' '.join((str(x) for x in args))
        rendered = self._tag_re.sub('', rendered)
        print(rendered)
console = _AlvsiaPakConsole()
BASE_DIR = Path.cwd()
_ALVSIA_PAK_LEGACY_DISPLAY_BRAND = 'ALVSIA_LEGACY'
_ALVSIA_PAK_DISPLAY_BRAND = 'ALVSIA_PRO'

def _alvsia_pak_debug_display(value) -> str:
    return str(value).replace(_ALVSIA_PAK_LEGACY_DISPLAY_BRAND, _ALVSIA_PAK_DISPLAY_BRAND)
ZUC_KEY = bytes.fromhex('01010101010101010101010101010101')
ZUC_IV = bytes.fromhex('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF')
RSA_MOD_1 = bytes.fromhex('CBE8B9F2504050EF9831B719E9A6249A6D238505ADE909BDE78C180DED6072A0C3347B8AF4780E1F212D952D82D4BF7F233C1ECA499E1F9D9A85B4FAD759F54BABC1666C5DE411EA9E4B2374425DD6C6F54333BBC8F2610FE6063E4D0D6C21A671A8F7C3740555E5DC06D4E1691C456DB4116C0C012BF7B206E8311AAAEC689952BF804EF638F09D5822B4117B114208F14DEB459E80CB770E5B0D7978E21F5E6CED4999D3583108221A7AB28B960277ADB5690A332784019D9C195BE4EA9EA0A09459010F236465DE0D59C3EF7324E954E1118D93EE19F299760C2CDB963CE87973EA5ECC9BBE81C27D4C7C8572AC07E9BCEAC9BD72AB7A56A3C0AD736ABCE4')
RSA_MOD_2 = bytes.fromhex('7F58E8A39A4DA4E87357DDD650EAA16D3B5CE95B213D1030A662566444796A78A84AE9AC3DBFFDE7F41094896696835DAF13B89E6EC2B84963B1B1BAF7151DA245C3FBFAE2A6AE18B2684D03F9229DE2C91440F2A3A3BCDE1E5680C16722A88039C73560D5D43F4B6562C2EEA5B1D926D86B51108A2643C70FB74D6442CE3A08339B8FD8F660AE88129B7AB8C46F2FA58124485CCCB1E987B05A6DA65A01858ED3F89905449AE42BB07290FCB9994BF22E26610BCABB9804783A3B9587917F3D97316EDDA15C5E13F79066407B55A93B291B68A4AC42A98D6E35FED84B14A792D154E62028DDAD20FC301951E5924BE9AD62FB719DD94CC30CAB871BEC4377A8')
SIMPLE1_DECRYPT_KEY = 121
SIMPLE2_DECRYPT_KEY = bytes.fromhex('E55B4ED1')
SIMPLE2_BLOCK_SIZE = 4
SM4_SECRET_4 = 'eb691efea914241317a8'
SM4_SECRET_2 = 'Q0hVTKey$as*1ZFlQCiA'
# New/variant SM4 candidates are never embedded in the public source tree.
# They must be supplied by an authorized caller for the corresponding PAK.
from sm4_secret_registry import SM4_SECRET_NEW
_SM4_AUTHORIZED_CANDIDATES = ()

def set_authorized_sm4_candidates(candidates) -> bool:
    global _SM4_AUTHORIZED_CANDIDATES
    values = tuple(candidates or ())
    if not all(isinstance(key, str) and 1 <= len(key) <= 64 for key in values):
        return False
    _SM4_AUTHORIZED_CANDIDATES = values
    PakCrypto._derive_sm4_key.cache_clear()
    return True

def clear_authorized_sm4_candidates() -> None:
    global _SM4_AUTHORIZED_CANDIDATES
    _SM4_AUTHORIZED_CANDIDATES = ()
    PakCrypto._derive_sm4_key.cache_clear()

EM_SIMPLE1 = 1
EM_SIMPLE2 = 16
EM_SM4_2 = 2
EM_SM4_4 = 4
EM_SM4_NEW_BASE = 31
EM_SM4_NEW_MASK = ~EM_SM4_NEW_BASE
EM_UNKNOWN_17 = 17
CM_NONE = 0
CM_ZLIB = 1
CM_ZSTD = 6
CM_ZSTD_DICT = 8
CM_MASK = 15



# ---- ZUC-128 exact copy from gmalg 1.1.2 (ww-rm) — required for Tencent PAK footer ----
def _ROL32(X: int, count: int) -> int:
    count %= 32
    return ((X << count) | (X >> (32 - count))) & 0xffffffff

_ZUC_S0 = bytes([
    0x3e, 0x72, 0x5b, 0x47, 0xca, 0xe0, 0x00, 0x33, 0x04, 0xd1, 0x54, 0x98, 0x09, 0xb9, 0x6d, 0xcb,
    0x7b, 0x1b, 0xf9, 0x32, 0xaf, 0x9d, 0x6a, 0xa5, 0xb8, 0x2d, 0xfc, 0x1d, 0x08, 0x53, 0x03, 0x90,
    0x4d, 0x4e, 0x84, 0x99, 0xe4, 0xce, 0xd9, 0x91, 0xdd, 0xb6, 0x85, 0x48, 0x8b, 0x29, 0x6e, 0xac,
    0xcd, 0xc1, 0xf8, 0x1e, 0x73, 0x43, 0x69, 0xc6, 0xb5, 0xbd, 0xfd, 0x39, 0x63, 0x20, 0xd4, 0x38,
    0x76, 0x7d, 0xb2, 0xa7, 0xcf, 0xed, 0x57, 0xc5, 0xf3, 0x2c, 0xbb, 0x14, 0x21, 0x06, 0x55, 0x9b,
    0xe3, 0xef, 0x5e, 0x31, 0x4f, 0x7f, 0x5a, 0xa4, 0x0d, 0x82, 0x51, 0x49, 0x5f, 0xba, 0x58, 0x1c,
    0x4a, 0x16, 0xd5, 0x17, 0xa8, 0x92, 0x24, 0x1f, 0x8c, 0xff, 0xd8, 0xae, 0x2e, 0x01, 0xd3, 0xad,
    0x3b, 0x4b, 0xda, 0x46, 0xeb, 0xc9, 0xde, 0x9a, 0x8f, 0x87, 0xd7, 0x3a, 0x80, 0x6f, 0x2f, 0xc8,
    0xb1, 0xb4, 0x37, 0xf7, 0x0a, 0x22, 0x13, 0x28, 0x7c, 0xcc, 0x3c, 0x89, 0xc7, 0xc3, 0x96, 0x56,
    0x07, 0xbf, 0x7e, 0xf0, 0x0b, 0x2b, 0x97, 0x52, 0x35, 0x41, 0x79, 0x61, 0xa6, 0x4c, 0x10, 0xfe,
    0xbc, 0x26, 0x95, 0x88, 0x8a, 0xb0, 0xa3, 0xfb, 0xc0, 0x18, 0x94, 0xf2, 0xe1, 0xe5, 0xe9, 0x5d,
    0xd0, 0xdc, 0x11, 0x66, 0x64, 0x5c, 0xec, 0x59, 0x42, 0x75, 0x12, 0xf5, 0x74, 0x9c, 0xaa, 0x23,
    0x0e, 0x86, 0xab, 0xbe, 0x2a, 0x02, 0xe7, 0x67, 0xe6, 0x44, 0xa2, 0x6c, 0xc2, 0x93, 0x9f, 0xf1,
    0xf6, 0xfa, 0x36, 0xd2, 0x50, 0x68, 0x9e, 0x62, 0x71, 0x15, 0x3d, 0xd6, 0x40, 0xc4, 0xe2, 0x0f,
    0x8e, 0x83, 0x77, 0x6b, 0x25, 0x05, 0x3f, 0x0c, 0x30, 0xea, 0x70, 0xb7, 0xa1, 0xe8, 0xa9, 0x65,
    0x8d, 0x27, 0x1a, 0xdb, 0x81, 0xb3, 0xa0, 0xf4, 0x45, 0x7a, 0x19, 0xdf, 0xee, 0x78, 0x34, 0x60
])
_ZUC_S1 = bytes([
    0x55, 0xc2, 0x63, 0x71, 0x3b, 0xc8, 0x47, 0x86, 0x9f, 0x3c, 0xda, 0x5b, 0x29, 0xaa, 0xfd, 0x77,
    0x8c, 0xc5, 0x94, 0x0c, 0xa6, 0x1a, 0x13, 0x00, 0xe3, 0xa8, 0x16, 0x72, 0x40, 0xf9, 0xf8, 0x42,
    0x44, 0x26, 0x68, 0x96, 0x81, 0xd9, 0x45, 0x3e, 0x10, 0x76, 0xc6, 0xa7, 0x8b, 0x39, 0x43, 0xe1,
    0x3a, 0xb5, 0x56, 0x2a, 0xc0, 0x6d, 0xb3, 0x05, 0x22, 0x66, 0xbf, 0xdc, 0x0b, 0xfa, 0x62, 0x48,
    0xdd, 0x20, 0x11, 0x06, 0x36, 0xc9, 0xc1, 0xcf, 0xf6, 0x27, 0x52, 0xbb, 0x69, 0xf5, 0xd4, 0x87,
    0x7f, 0x84, 0x4c, 0xd2, 0x9c, 0x57, 0xa4, 0xbc, 0x4f, 0x9a, 0xdf, 0xfe, 0xd6, 0x8d, 0x7a, 0xeb,
    0x2b, 0x53, 0xd8, 0x5c, 0xa1, 0x14, 0x17, 0xfb, 0x23, 0xd5, 0x7d, 0x30, 0x67, 0x73, 0x08, 0x09,
    0xee, 0xb7, 0x70, 0x3f, 0x61, 0xb2, 0x19, 0x8e, 0x4e, 0xe5, 0x4b, 0x93, 0x8f, 0x5d, 0xdb, 0xa9,
    0xad, 0xf1, 0xae, 0x2e, 0xcb, 0x0d, 0xfc, 0xf4, 0x2d, 0x46, 0x6e, 0x1d, 0x97, 0xe8, 0xd1, 0xe9,
    0x4d, 0x37, 0xa5, 0x75, 0x5e, 0x83, 0x9e, 0xab, 0x82, 0x9d, 0xb9, 0x1c, 0xe0, 0xcd, 0x49, 0x89,
    0x01, 0xb6, 0xbd, 0x58, 0x24, 0xa2, 0x5f, 0x38, 0x78, 0x99, 0x15, 0x90, 0x50, 0xb8, 0x95, 0xe4,
    0xd0, 0x91, 0xc7, 0xce, 0xed, 0x0f, 0xb4, 0x6f, 0xa0, 0xcc, 0xf0, 0x02, 0x4a, 0x79, 0xc3, 0xde,
    0xa3, 0xef, 0xea, 0x51, 0xe6, 0x6b, 0x18, 0xec, 0x1b, 0x2c, 0x80, 0xf7, 0x74, 0xe7, 0xff, 0x21,
    0x5a, 0x6a, 0x54, 0x1e, 0x41, 0x31, 0x92, 0x35, 0xc4, 0x33, 0x07, 0x0a, 0xba, 0x7e, 0x0e, 0x34,
    0x88, 0xb1, 0x98, 0x7c, 0xf3, 0x3d, 0x60, 0x6c, 0x7b, 0xca, 0xd3, 0x1f, 0x32, 0x65, 0x04, 0x28,
    0x64, 0xbe, 0x85, 0x9b, 0x2f, 0x59, 0x8a, 0xd7, 0xb0, 0x25, 0xac, 0xaf, 0x12, 0x03, 0xe2, 0xf2
])
_ZUC_D = [
    0b100010011010111, 0b010011010111100, 0b110001001101011, 0b001001101011110,
    0b101011110001001, 0b011010111100010, 0b111000100110101, 0b000100110101111,
    0b100110101111000, 0b010111100010011, 0b110101111000100, 0b001101011110001,
    0b101111000100110, 0b011110001001101, 0b111100010011010, 0b100011110101100
]

def _ZUC_BS(X):
    return (
        (_ZUC_S0[(X >> 24) & 0xff] << 24) ^
        (_ZUC_S1[(X >> 16) & 0xff] << 16) ^
        (_ZUC_S0[(X >> 8) & 0xff] << 8) ^
        (_ZUC_S1[X & 0xff])
    )

def _ZUC_L1(X):
    return X ^ _ROL32(X, 2) ^ _ROL32(X, 10) ^ _ROL32(X, 18) ^ _ROL32(X, 24)

def _ZUC_L2(X):
    return X ^ _ROL32(X, 8) ^ _ROL32(X, 14) ^ _ROL32(X, 22) ^ _ROL32(X, 30)

class _AlvsiaZUC:
    """gmalg-compatible ZUC-128."""
    def __init__(self, key: bytes, iv: bytes):
        if len(key) != 16 or len(iv) != 16:
            raise ValueError('ZUC key/iv must be 16 bytes')
        self._key = key
        self._iv = iv
        self._lfsr = [0] * 16
        self._R1 = 0
        self._R2 = 0
        self._init()
        self.generate()  # discard first word (gmalg behavior)

    def _lfsr_work(self, u: int = 0):
        S = self._lfsr
        s16 = ((S[15] << 15) + (S[13] << 17) + (S[10] << 21) + (S[4] << 20) + (S[0] << 8) + S[0] + u) % 0x7fffffff
        S.append(0x7fffffff if s16 == 0 else s16)
        S.pop(0)

    def _F(self, X0, X1, X2):
        R1, R2 = self._R1, self._R2
        W = ((X0 ^ R1) + R2) & 0xffffffff
        W1 = (R1 + X1) & 0xffffffff
        W2 = R2 ^ X2
        self._R1 = _ZUC_BS(_ZUC_L1(((W1 & 0xffff) << 16) ^ (W2 >> 16)))
        self._R2 = _ZUC_BS(_ZUC_L2(((W2 & 0xffff) << 16) ^ (W1 >> 16)))
        return W

    def _init(self):
        S = self._lfsr
        for i in range(16):
            S[i] = (self._key[i] << 23) | (_ZUC_D[i] << 8) | (self._iv[i])
        for _ in range(32):
            X0 = (S[15] >> 15 << 16) | (S[14] & 0xffff)
            X1 = ((S[11] & 0xffff) << 16) | (S[9] >> 15)
            X2 = ((S[7] & 0xffff) << 16) | (S[5] >> 15)
            self._lfsr_work(self._F(X0, X1, X2) >> 1)

    def generate(self) -> bytes:
        S = self._lfsr
        X0 = (S[15] >> 15 << 16) | (S[14] & 0xffff)
        X1 = ((S[11] & 0xffff) << 16) | (S[9] >> 15)
        X2 = ((S[7] & 0xffff) << 16) | (S[5] >> 15)
        X3 = ((S[2] & 0xffff) << 16) | (S[0] >> 15)
        Z = self._F(X0, X1, X2) ^ X3
        self._lfsr_work()
        return Z.to_bytes(4, 'big')


def _alvsia_zuc_keystream_pure(key: bytes, iv: bytes, n: int = 16):
    """Return n uint32 words matching gmalg.ZUC(key,iv).generate() x n."""
    z = _AlvsiaZUC(key, iv)
    out = []
    for _ in range(n):
        out.append(int.from_bytes(z.generate(), 'big'))
    return out



class SM4:
    """SM4 Algorithm Implementation."""
    _S_BOX = bytes([52, 102, 37, 116, 137, 120, 228, 169, 90, 65, 188, 122, 214, 22, 33, 35, 77, 97, 218, 148, 155, 223, 19, 60, 105, 58, 49, 10, 95, 215, 153, 149, 241, 174, 114, 61, 7, 96, 36, 182, 152, 238, 196, 162, 45, 136, 221, 141, 4, 234, 187, 17, 202, 62, 93, 161, 246, 63, 176, 151, 128, 71, 43, 166, 230, 247, 217, 177, 89, 192, 124, 190, 84, 40, 183, 126, 79, 248, 67, 110, 160, 80, 14, 245, 144, 184, 251, 163, 123, 98, 25, 70, 3, 42, 185, 143, 159, 119, 180, 91, 131, 135, 8, 235, 226, 30, 66, 240, 15, 232, 113, 106, 117, 173, 85, 31, 181, 171, 51, 250, 127, 21, 189, 133, 216, 6, 104, 179, 82, 48, 72, 11, 0, 237, 239, 178, 87, 142, 231, 108, 213, 229, 46, 83, 130, 5, 249, 129, 244, 86, 191, 140, 75, 227, 219, 74, 145, 76, 44, 211, 64, 41, 78, 32, 20, 54, 121, 9, 111, 209, 55, 224, 57, 12, 138, 146, 56, 18, 53, 109, 225, 253, 147, 154, 23, 212, 201, 156, 107, 132, 38, 157, 175, 118, 193, 158, 208, 150, 197, 203, 233, 115, 73, 210, 205, 100, 195, 199, 1, 125, 243, 172, 252, 222, 164, 68, 50, 27, 194, 186, 28, 2, 198, 39, 69, 139, 242, 24, 167, 16, 81, 29, 200, 207, 99, 255, 47, 13, 88, 206, 101, 165, 220, 26, 59, 134, 254, 34, 92, 168, 94, 103, 170, 236, 112, 204])
    _FK = [1184304796, 1270900830, 1493524870, 3164752158]
    _CK = [964907, 973793155, 2654690407, 2916866751, 2071233739, 1226140771, 3348805095, 2045549823, 388349611, 800627875, 612403927, 3721562911, 1195432523, 3150178931, 612053223, 2445162591, 67183755, 1174197155, 1393249511, 3331183455, 3822152747, 1332317203, 1804781383, 1990130463, 1282653851, 3376591251, 2910902311, 925872959, 332098219, 735840931, 396665415, 3588844719]

    @staticmethod
    def ROL32(x, n):
        return x << n & 4294967295 | x >> 32 - n

    @staticmethod
    def _BS(X):
        return SM4._S_BOX[X >> 24 & 255] << 24 | SM4._S_BOX[X >> 16 & 255] << 16 | SM4._S_BOX[X >> 8 & 255] << 8 | SM4._S_BOX[X & 255]

    @staticmethod
    def _T0(X):
        X = SM4._BS(X)
        return X ^ SM4.ROL32(X, 2) ^ SM4.ROL32(X, 10) ^ SM4.ROL32(X, 18) ^ SM4.ROL32(X, 24)

    @staticmethod
    def _T1(X):
        X = SM4._BS(X)
        return X ^ SM4.ROL32(X, 13) ^ SM4.ROL32(X, 23)

    @staticmethod
    def _key_expand(key: bytes, rkey: list):
        _s675e6878edf5 = int.from_bytes(key[0:4], 'big') ^ SM4._FK[0]
        _s76e8209e75a7 = int.from_bytes(key[4:8], 'big') ^ SM4._FK[1]
        _s37d5d30b5139 = int.from_bytes(key[8:12], 'big') ^ SM4._FK[2]
        _s8c360ca2c48a = int.from_bytes(key[12:16], 'big') ^ SM4._FK[3]
        for _sc04fd27b9cdf in range(0, 32, 4):
            _s675e6878edf5 = _s675e6878edf5 ^ SM4._T1(_s76e8209e75a7 ^ _s37d5d30b5139 ^ _s8c360ca2c48a ^ SM4._CK[_sc04fd27b9cdf])
            rkey[_sc04fd27b9cdf] = _s675e6878edf5
            _s76e8209e75a7 = _s76e8209e75a7 ^ SM4._T1(_s37d5d30b5139 ^ _s8c360ca2c48a ^ _s675e6878edf5 ^ SM4._CK[_sc04fd27b9cdf + 1])
            rkey[_sc04fd27b9cdf + 1] = _s76e8209e75a7
            _s37d5d30b5139 = _s37d5d30b5139 ^ SM4._T1(_s8c360ca2c48a ^ _s675e6878edf5 ^ _s76e8209e75a7 ^ SM4._CK[_sc04fd27b9cdf + 2])
            rkey[_sc04fd27b9cdf + 2] = _s37d5d30b5139
            _s8c360ca2c48a = _s8c360ca2c48a ^ SM4._T1(_s675e6878edf5 ^ _s76e8209e75a7 ^ _s37d5d30b5139 ^ SM4._CK[_sc04fd27b9cdf + 3])
            rkey[_sc04fd27b9cdf + 3] = _s8c360ca2c48a

    @classmethod
    def key_length(cls):
        return 16

    @classmethod
    def block_length(cls):
        return 16

    def __init__(self, key: bytes):
        if len(key) != self.key_length():
            raise ValueError(f'Key must be {self.key_length()} bytes')
        self._key = key
        self._rkey = [0] * 32
        SM4._key_expand(self._key, self._rkey)
        self._block_buffer = bytearray()

    def encrypt(self, block: bytes) -> bytes:
        if len(block) != self.block_length():
            raise ValueError(f'Block must be {self.block_length()} bytes')
        _sc1c516bb51fa = self._rkey
        _s575e5e04834a = int.from_bytes(block[0:4], 'big')
        _sdc8fde238313 = int.from_bytes(block[4:8], 'big')
        _s9ca2b966fe13 = int.from_bytes(block[8:12], 'big')
        _s4d48730788eb = int.from_bytes(block[12:16], 'big')
        for _s4db069a1d720 in range(0, 32, 4):
            _s575e5e04834a = _s575e5e04834a ^ SM4._T0(_sdc8fde238313 ^ _s9ca2b966fe13 ^ _s4d48730788eb ^ _sc1c516bb51fa[_s4db069a1d720])
            _sdc8fde238313 = _sdc8fde238313 ^ SM4._T0(_s9ca2b966fe13 ^ _s4d48730788eb ^ _s575e5e04834a ^ _sc1c516bb51fa[_s4db069a1d720 + 1])
            _s9ca2b966fe13 = _s9ca2b966fe13 ^ SM4._T0(_s4d48730788eb ^ _s575e5e04834a ^ _sdc8fde238313 ^ _sc1c516bb51fa[_s4db069a1d720 + 2])
            _s4d48730788eb = _s4d48730788eb ^ SM4._T0(_s575e5e04834a ^ _sdc8fde238313 ^ _s9ca2b966fe13 ^ _sc1c516bb51fa[_s4db069a1d720 + 3])
        _see62ae2378cb = self._block_buffer
        _see62ae2378cb.clear()
        _see62ae2378cb.extend(_s4d48730788eb.to_bytes(4, 'big'))
        _see62ae2378cb.extend(_s9ca2b966fe13.to_bytes(4, 'big'))
        _see62ae2378cb.extend(_sdc8fde238313.to_bytes(4, 'big'))
        _see62ae2378cb.extend(_s575e5e04834a.to_bytes(4, 'big'))
        return bytes(_see62ae2378cb)

    def decrypt(self, block: bytes) -> bytes:
        if len(block) != self.block_length():
            raise ValueError(f'Block must be {self.block_length()} bytes')
        _s4fac0e604588 = self._rkey
        _s9b8e65aabd3c = int.from_bytes(block[0:4], 'big')
        _s299d3838170f = int.from_bytes(block[4:8], 'big')
        _sc7c6fe8df4be = int.from_bytes(block[8:12], 'big')
        _s4b763ba958ab = int.from_bytes(block[12:16], 'big')
        for _sda06635f34a6 in range(0, 32, 4):
            _s9b8e65aabd3c = _s9b8e65aabd3c ^ SM4._T0(_s299d3838170f ^ _sc7c6fe8df4be ^ _s4b763ba958ab ^ _s4fac0e604588[31 - _sda06635f34a6])
            _s299d3838170f = _s299d3838170f ^ SM4._T0(_sc7c6fe8df4be ^ _s4b763ba958ab ^ _s9b8e65aabd3c ^ _s4fac0e604588[30 - _sda06635f34a6])
            _sc7c6fe8df4be = _sc7c6fe8df4be ^ SM4._T0(_s4b763ba958ab ^ _s9b8e65aabd3c ^ _s299d3838170f ^ _s4fac0e604588[29 - _sda06635f34a6])
            _s4b763ba958ab = _s4b763ba958ab ^ SM4._T0(_s9b8e65aabd3c ^ _s299d3838170f ^ _sc7c6fe8df4be ^ _s4fac0e604588[28 - _sda06635f34a6])
        _s0c55977ac20c = self._block_buffer
        _s0c55977ac20c.clear()
        _s0c55977ac20c.extend(_s4b763ba958ab.to_bytes(4, 'big'))
        _s0c55977ac20c.extend(_sc7c6fe8df4be.to_bytes(4, 'big'))
        _s0c55977ac20c.extend(_s299d3838170f.to_bytes(4, 'big'))
        _s0c55977ac20c.extend(_s9b8e65aabd3c.to_bytes(4, 'big'))
        return bytes(_s0c55977ac20c)

class Misc:

    @staticmethod
    def pad_to_n(data: bytes, n: int) -> bytes:
        assert n > 0
        _sdf8ea9172aca = n - len(data) % n
        if _sdf8ea9172aca == n:
            return data
        return data + b'\x00' * _sdf8ea9172aca

    @staticmethod
    def align_up(x: int, n: int) -> int:
        return (x + n - 1) // n * n

class PakReader:

    def __init__(self, buffer, cursor=0):
        self._buffer = buffer
        self._cursor = cursor

    def u1(self, move_cursor=True) -> int:
        return self.unpack('B', move_cursor=move_cursor)[0]

    def u4(self, move_cursor=True) -> int:
        return self.unpack('<I', move_cursor=move_cursor)[0]

    def u8(self, move_cursor=True) -> int:
        return self.unpack('<Q', move_cursor=move_cursor)[0]

    def i1(self, move_cursor=True) -> int:
        return self.unpack('b', move_cursor=move_cursor)[0]

    def i4(self, move_cursor=True) -> int:
        return self.unpack('<i', move_cursor=move_cursor)[0]

    def i8(self, move_cursor=True) -> int:
        return self.unpack('<q', move_cursor=move_cursor)[0]

    def s(self, n: int, move_cursor=True) -> bytes:
        return self.unpack(f'{n}s', move_cursor=move_cursor)[0]

    def unpack(self, f: Union[str, bytes], offset=0, move_cursor=True):
        _s6cb15be33ea2 = struct.unpack_from(f, self._buffer, self._cursor + offset)
        if move_cursor:
            self._cursor += struct.calcsize(f)
        return _s6cb15be33ea2

    def string(self, move_cursor=True) -> str:
        _s0cc99f169bdd = self.i4(move_cursor=move_cursor)
        if _s0cc99f169bdd == 0:
            return str()
        assert _s0cc99f169bdd > 0
        _s416c98aeba25 = 0 if move_cursor else 4
        return self.unpack(f'{_s0cc99f169bdd}s', offset=_s416c98aeba25, move_cursor=move_cursor)[0].rstrip(b'\x00').decode()

class PakInfo:

    def __init__(self, buffer, keystream: List[int]):

        def decrypt_index_encrypted(x: int) -> int:
            _s6bab90fc4ab8 = 255
            return (x ^ keystream[3]) & _s6bab90fc4ab8

        def decrypt_magic(x: int) -> int:
            return x ^ keystream[2]

        def decrypt_index_hash(x: bytes) -> bytes:
            key = struct.pack('<5I', *keystream[4:][:5])
            assert len(x) == len(key)
            return bytes((a ^ b for a, b in zip(x, key)))

        def decrypt_index_size(x: int) -> int:
            return x ^ (keystream[10] << 32 | keystream[11])

        def decrypt_index_offset(x: int) -> int:
            return x ^ (keystream[0] << 32 | keystream[1])
        reader = PakReader(buffer[-PakInfo._mem_size(-1):])
        self.index_encrypted: bool = decrypt_index_encrypted(reader.u1()) == 1
        self.magic: int = decrypt_magic(reader.u4())
        self.version: int = reader.u4()
        self.index_hash: bytes = decrypt_index_hash(reader.s(20)) if self.version >= 6 else bytes()
        self.index_size: int = decrypt_index_size(reader.u8())
        self.index_offset: int = decrypt_index_offset(reader.u8())
        if self.version <= 3:
            self.index_encrypted = False

    @staticmethod
    def _mem_size(_: int) -> int:
        return 1 + 4 + 4 + 20 + 8 + 8

class TencentPakInfo(PakInfo):

    def __init__(self, buffer, keystream: List[int]):

        def decrypt_unk(x: bytes) -> bytes:
            key = struct.pack('<8I', *keystream[7:][:8])
            assert len(x) == len(key)
            return bytes((a ^ b for a, b in zip(x, key)))

        def decrypt_stem_hash(x: int) -> int:
            return x ^ keystream[8]

        def decrypt_unk_hash(x: int) -> int:
            return x ^ keystream[9]
        super().__init__(buffer, keystream)
        reader = PakReader(buffer[-TencentPakInfo._mem_size(self.version):])
        self.unk1: bytes = decrypt_unk(reader.s(32)) if self.version >= 7 else bytes()
        self.packed_key: bytes = reader.s(256) if self.version >= 8 else bytes()
        self.packed_iv: bytes = reader.s(256) if self.version >= 8 else bytes()
        self.packed_index_hash: bytes = reader.s(256) if self.version >= 8 else bytes()
        self.stem_hash: int = decrypt_stem_hash(reader.u4()) if self.version >= 9 else 0
        self.unk2: int = decrypt_unk_hash(reader.u4()) if self.version >= 9 else 0
        self.content_org_hash: bytes = reader.s(20) if self.version >= 12 else bytes()

    @staticmethod
    def _mem_size(version: int) -> int:
        _s2d9696b0690f = 32 if version >= 7 else 0
        _s4d01566231cb = 256 * 3 if version >= 8 else 0
        _s5e8c6b2d84ca = 4 * 2 if version >= 9 else 0
        _s6f8f7c152ca5 = 20 if version >= 12 else 0
        return PakInfo._mem_size(version) + _s2d9696b0690f + _s4d01566231cb + _s5e8c6b2d84ca + _s6f8f7c152ca5

class PakCompressedBlock:

    def __init__(self, reader: PakReader):
        self.start: int = reader.u8()
        self.end: int = reader.u8()

@dataclass
class TencentPakEntry:

    def __init__(self, reader: PakReader, version: int):
        self.content_hash: bytes = reader.s(20)
        if version <= 1:
            _ = reader.u8()
        self.offset: int = reader.u8()
        self.uncompressed_size: int = reader.u8()
        self.compression_method: int = reader.u4() & CM_MASK
        self.size: int = reader.u8()
        self.unk1: int = reader.u1() if version >= 5 else 0
        self.unk2: bytes = reader.s(20) if version >= 5 else bytes()
        self.compressed_blocks: List[PakCompressedBlock] = [PakCompressedBlock(reader) for _ in range(reader.u4())] if self.compression_method != 0 and version >= 3 else []
        self.compression_block_size: int = reader.u4() if version >= 4 else 0
        self.encrypted: bool = reader.u1() == 1 if version >= 4 else False
        self.encryption_method: int = reader.u4() if version >= 12 else 0
        self.index_new_sep: int = reader.u4() if version >= 12 else 0

    def _mem_size(self, version: int) -> int:
        _sc406064ed7f7 = 20 + 8 + 8 + 4 + 8 + (8 if version == 1 else 0)
        _s7729abb79481 = 4 + 1 if version >= 4 else 0
        _sdf708330ae6c = 4 + len(self.compressed_blocks) * 16 if self.compressed_blocks else 0
        _sb82161dbd1a7 = 1 + 20 if version >= 5 else 0
        _s7d6502d56c25 = 4 if version >= 12 else 0
        return _sc406064ed7f7 + _s7729abb79481 + _sb82161dbd1a7 + _s7d6502d56c25 + _sdf708330ae6c

class PakCrypto:

    class _LCG:

        def __init__(self, seed: int):
            self.state = seed

        def next(self) -> int:
            MASK_32 = 4294967295
            MSB_1 = 1 << 31

            def wrap(x: int) -> int:
                x &= MASK_32
                if not x & MSB_1:
                    return x
                else:
                    return (x + MSB_1 & MASK_32) - MSB_1
            x1 = wrap(1103515245 * self.state)
            self.state = wrap(x1 + 12345)
            x2 = wrap(x1 + 77880) if self.state < 0 else self.state
            return (x2 >> 16 & MASK_32) % 32767

    @staticmethod
    def zuc_keystream() -> List[int]:
        # Prefer embedded gmalg-exact ZUC (works offline / Chaquopy without pip gmalg)
        try:
            return _alvsia_zuc_keystream_pure(ZUC_KEY, ZUC_IV, 16)
        except Exception:
            pass
        if gmalg is not None:
            zuc = gmalg.ZUC(ZUC_KEY, ZUC_IV)
            return [struct.unpack('>I', zuc.generate())[0] for _ in range(16)]
        raise RuntimeError('ZUC keystream unavailable')

    @staticmethod
    def _xorxor(buffer, x) -> bytes:
        return bytes((buffer[i] ^ x[i % len(x)] for i in range(len(buffer))))

    @staticmethod
    def _hashhash(buffer, n: int) -> bytes:
        _s59baeeaef8af = bytes()
        for _s6af6e5bfddf7 in range(math.ceil(n / SHA1.digest_size)):
            _s59baeeaef8af += SHA1.new(buffer).digest()
        if len(_s59baeeaef8af) >= n:
            _s59baeeaef8af = _s59baeeaef8af[:n]
        else:
            _s59baeeaef8af += b'\x00' * (n - len(_s59baeeaef8af))
        return _s59baeeaef8af

    @staticmethod
    def _meowmeow(buffer) -> bytes:

        def unpad(x):
            skip = 1 + next((i for i in range(len(x)) if x[i] != 0))
            return x[skip:]
        if len(buffer) < 43:
            return bytes()
        x1 = buffer[1:][:SHA1.digest_size]
        x2 = buffer[SHA1.digest_size + 1:]
        x1 = PakCrypto._xorxor(x1, PakCrypto._hashhash(x2, len(x1)))
        x2 = PakCrypto._xorxor(x2, PakCrypto._hashhash(x1, len(x2)))
        part1, m = (x2[:SHA1.digest_size], x2[SHA1.digest_size:])
        if part1 != SHA1.new(b'\x00' * SHA1.digest_size).digest():
            return bytes()
        return unpad(m)

    @staticmethod
    def rsa_extract(signature: bytes, modulus: bytes) -> bytes:
        _s111eea9de461 = int.from_bytes(signature, 'little')
        _s55ed6d4fd331 = int.from_bytes(modulus, 'little')
        _s095c3755c6f0 = 65537
        _se1fe0c965606 = pow(_s111eea9de461, _s095c3755c6f0, _s55ed6d4fd331).to_bytes(256, 'little').rstrip(b'\x00')
        return PakCrypto._meowmeow(Misc.pad_to_n(_se1fe0c965606, 4))

    @staticmethod
    def _decrypt_simple1(ciphertext) -> bytes:
        return bytes((x ^ SIMPLE1_DECRYPT_KEY for x in ciphertext))

    @staticmethod
    def _decrypt_simple2(ciphertext) -> bytes:

        class RollingKey:

            def __init__(self, initial_value: int):
                self._value = initial_value

            def update(self, x: int) -> int:
                self._value ^= x
                return self._value
        assert len(ciphertext) % SIMPLE2_BLOCK_SIZE == 0
        initial_key, = struct.unpack('<I', SIMPLE2_DECRYPT_KEY)
        rolling_key = RollingKey(initial_key)
        plaintext = (struct.pack('<I', rolling_key.update(x)) for x in struct.unpack(f'<{len(ciphertext) // 4}I', ciphertext))
        return bytes(it.chain.from_iterable(plaintext))

    @staticmethod
    @lru_cache(maxsize=1)
    def _derive_sm4_key(file_path: PurePath, encryption_method: int) -> bytes:
        _s5faefbac755f = file_path.stem.lower()
        if encryption_method == EM_SM4_2:
            _sbd281f3d3181 = SM4_SECRET_2
        elif encryption_method == EM_SM4_4:
            _sbd281f3d3181 = SM4_SECRET_4
        elif encryption_method == EM_UNKNOWN_17:
            candidates = _SM4_AUTHORIZED_CANDIDATES
            if not candidates:
                raise RuntimeError('SM4 candidate material is not authorized/supplied')
            _s2b8e7b87d9f2 = (encryption_method - EM_SM4_NEW_BASE) % len(candidates)
            _sbd281f3d3181 = candidates[_s2b8e7b87d9f2]
        else:
            candidates = _SM4_AUTHORIZED_CANDIDATES
            if not candidates:
                raise RuntimeError('SM4 candidate material is not authorized/supplied')
            _s2b8e7b87d9f2 = (encryption_method - EM_SM4_NEW_BASE) % len(candidates)
            _sbd281f3d3181 = f'{candidates[_s2b8e7b87d9f2]}{encryption_method}'
        return SHA1.new(str(_s5faefbac755f + _sbd281f3d3181).encode()).digest()[:SM4.key_length()]

    @staticmethod
    @lru_cache(maxsize=1)
    def _sm4_context_for_key(key: bytes) -> SM4:
        return SM4(key)

    @staticmethod
    def _decrypt_sm4(ciphertext, file_path: PurePath, encryption_method: int) -> bytes:
        assert len(ciphertext) % SM4.block_length() == 0
        key = PakCrypto._derive_sm4_key(file_path, encryption_method)
        sm4 = PakCrypto._sm4_context_for_key(key)
        block_size = SM4.block_length()
        return b''.join(
            sm4.decrypt(ciphertext[i:i + block_size])
            for i in range(0, len(ciphertext), block_size)
        )

    @staticmethod
    def decrypt_index(ciphertext, pak_info: TencentPakInfo) -> bytes:
        _sf57f815e306f = BASE_DIR / 'index_debug.txt'
        if pak_info.version > 7:
            _s6d658520201a = PakCrypto.rsa_extract(pak_info.packed_key, RSA_MOD_1)
            _s7df51ea341e1 = PakCrypto.rsa_extract(pak_info.packed_iv, RSA_MOD_1)
            _sdfce38baa9ff = f'\n=== AES INDEX DEBUG ===\nPAK version       : {pak_info.version}\nIndex encrypted   : {pak_info.index_encrypted}\nCiphertext length : {len(ciphertext)}\nCiphertext % 16   : {len(ciphertext) % 16}\nAES key length    : {len(_s6d658520201a)}\nIV length         : {len(_s7df51ea341e1)}\n=======================\n'
            print(_sdfce38baa9ff, flush=True)
            try:
                BASE_DIR.mkdir(parents=True, exist_ok=True)
                with open(_sf57f815e306f, 'a', encoding='utf-8') as _s110c157ac958:
                    _s110c157ac958.write(_sdfce38baa9ff)
            except Exception as e:
                print('Debug file write error:', e, flush=True)
            if len(_s6d658520201a) != 32:
                raise ValueError(f'Invalid AES key length: {len(_s6d658520201a)}')
            if len(_s7df51ea341e1) < 16:
                raise ValueError(f'Invalid IV length: {len(_s7df51ea341e1)}')
            if len(ciphertext) % AES.block_size != 0:
                raise ValueError(f'Encrypted index length is not aligned to AES block size: {len(ciphertext)} bytes')
            _scb460bac2d84 = AES.new(_s6d658520201a, MODE_CBC, _s7df51ea341e1[:16])
            _s970428e04040 = _scb460bac2d84.decrypt(ciphertext)
            _s285ad5d1da15 = f'\n=== AES DECRYPT RESULT ===\nDecrypted length  : {len(_s970428e04040)}\nFirst 16 bytes    : {_s970428e04040[:16].hex()}\nLast 16 bytes     : {_s970428e04040[-16:].hex()}\n==========================\n'
            print(_s285ad5d1da15, flush=True)
            try:
                with open(_sf57f815e306f, 'a', encoding='utf-8') as _s110c157ac958:
                    _s110c157ac958.write(_s285ad5d1da15)
            except Exception:
                pass
            try:
                _s0aecf0486bd3 = SHA1.new(_s970428e04040).digest()
                _s13f9d17236b6 = pak_info.index_hash
                _sf6b6965d0240 = _s0aecf0486bd3 == _s13f9d17236b6
                _sceb8ace10522 = None
                _s2599eac6ebec = None
                if len(_s970428e04040) >= 4:
                    _sceb8ace10522 = struct.unpack_from('<i', _s970428e04040, 0)[0]
                    if 0 < _sceb8ace10522 < 1024 and len(_s970428e04040) >= 4 + _sceb8ace10522:
                        _sce7a66c51c13 = _s970428e04040[4:4 + _sceb8ace10522]
                        _s2599eac6ebec = _sce7a66c51c13.rstrip(b'\\x00').decode('utf-8', errors='replace')
                _s8202ab0c7d3c = f'\n=== RAW INDEX CHECK ===\nExpected SHA1     : {_s13f9d17236b6.hex()}\nRaw SHA1          : {_s0aecf0486bd3.hex()}\nHASH MATCH        : {_sf6b6965d0240}\nFirst length      : {_sceb8ace10522}\nFirst string      : {_s2599eac6ebec}\n=======================\n'
                print(_s8202ab0c7d3c, flush=True)
                try:
                    with open(_sf57f815e306f, 'a', encoding='utf-8') as _s110c157ac958:
                        _s110c157ac958.write(_s8202ab0c7d3c)
                except Exception:
                    pass
            except Exception as e:
                _s955ef3f2949b = f'\n=== RAW INDEX CHECK ERROR ===\n{type(e).__name__}: {e}\n=============================\n'
                print(_s955ef3f2949b, flush=True)
                try:
                    with open(_sf57f815e306f, 'a', encoding='utf-8') as _s110c157ac958:
                        _s110c157ac958.write(_s955ef3f2949b)
                except Exception:
                    pass
            try:
                _sf9a1a1bab682 = unpad(_s970428e04040, AES.block_size)
            except ValueError as e:
                _s0aecf0486bd3 = SHA1.new(_s970428e04040).digest()
                _s13f9d17236b6 = pak_info.index_hash
                if _s0aecf0486bd3 == _s13f9d17236b6:
                    _s0cf61c10ae02 = f'\n=== PADDING FALLBACK ===\nUnpad error       : {e}\nRaw SHA1 matches expected index hash.\nUsing raw decrypted index without PKCS#7 unpad.\n========================\n'
                    print(_s0cf61c10ae02, flush=True)
                    try:
                        with open(_sf57f815e306f, 'a', encoding='utf-8') as _s110c157ac958:
                            _s110c157ac958.write(_s0cf61c10ae02)
                    except Exception:
                        pass
                    _sf9a1a1bab682 = _s970428e04040
                else:
                    _se3c61c4c947e = _s970428e04040[-1] if _s970428e04040 else None
                    _sb71dc219a486 = f'\n=== DECRYPT FAILURE ===\nError             : {e}\nDecrypted length  : {len(_s970428e04040)}\nLast byte         : {_se3c61c4c947e}\nLast 16 bytes     : {_s970428e04040[-16:].hex()}\nExpected SHA1     : {_s13f9d17236b6.hex()}\nRaw SHA1          : {_s0aecf0486bd3.hex()}\n=======================\n'
                    print(_sb71dc219a486, flush=True)
                    try:
                        with open(_sf57f815e306f, 'a', encoding='utf-8') as _s110c157ac958:
                            _s110c157ac958.write(_sb71dc219a486)
                    except Exception:
                        pass
                    raise
            _sbe3b813d7bcd = f'\n=== DECRYPT SUCCESS ===\nResult length     : {len(_sf9a1a1bab682)}\n=======================\n'
            print(_sbe3b813d7bcd, flush=True)
            try:
                with open(_sf57f815e306f, 'a', encoding='utf-8') as _s110c157ac958:
                    _s110c157ac958.write(_sbe3b813d7bcd)
            except Exception:
                pass
            return _sf9a1a1bab682
        return bytes(PakCrypto._decrypt_simple1(ciphertext))

    @staticmethod
    def _is_simple1_method(encryption_method: int) -> bool:
        return encryption_method == EM_SIMPLE1

    @staticmethod
    def _is_simple2_method(encryption_method: int) -> bool:
        return encryption_method == EM_SIMPLE2 or encryption_method == 17

    @staticmethod
    def _is_sm4_method(encryption_method: int) -> bool:
        return encryption_method == EM_SM4_2 or encryption_method == EM_SM4_4 or encryption_method == EM_UNKNOWN_17 or (encryption_method & EM_SM4_NEW_MASK != 0)

    @staticmethod
    def align_encrypted_content_size(n: int, encryption_method: int) -> int:
        if PakCrypto._is_simple2_method(encryption_method):
            return Misc.align_up(n, SIMPLE2_BLOCK_SIZE)
        elif PakCrypto._is_sm4_method(encryption_method):
            return Misc.align_up(n, SM4.block_length())
        else:
            return n

    @staticmethod
    def decrypt_block(ciphertext, file: PurePath, encryption_method: int) -> bytes:
        if PakCrypto._is_simple1_method(encryption_method):
            return PakCrypto._decrypt_simple1(ciphertext)
        elif PakCrypto._is_simple2_method(encryption_method):
            return PakCrypto._decrypt_simple2(ciphertext)
        elif PakCrypto._is_sm4_method(encryption_method):
            return PakCrypto._decrypt_sm4(ciphertext, file, encryption_method)
        else:
            raise ValueError(f'Unknown encryption method: {encryption_method}')

    @staticmethod
    @lru_cache(maxsize=33)
    def generate_block_indices(n: int, encryption_method: int) -> List[int]:
        if not PakCrypto._is_sm4_method(encryption_method):
            return list(range(n))
        _s3a075bc662d9 = []
        _s6e382a72ca37 = PakCrypto._LCG(n)
        while len(_s3a075bc662d9) != n:
            _sfe84feb5bf53 = _s6e382a72ca37.next() % n
            if _sfe84feb5bf53 not in _s3a075bc662d9:
                _s3a075bc662d9.append(_sfe84feb5bf53)
        _sba12f1c4fab3 = [0] * len(_s3a075bc662d9)
        for _sc2e19a16b623, _sfe84feb5bf53 in enumerate(_s3a075bc662d9):
            _sba12f1c4fab3[_sfe84feb5bf53] = _sc2e19a16b623
        return _sba12f1c4fab3

class PakCompression:

    @staticmethod
    @lru_cache(maxsize=1)
    def _zstd_decompressor_without_dict() -> ZstdDecompressor:
        """Create a plain Zstandard decoder without passing a null dictionary."""
        if ZstdDecompressor is None:
            raise RuntimeError("zstandard module is unavailable")
        return ZstdDecompressor()

    @staticmethod
    @lru_cache(maxsize=33)
    def _zstd_decompressor_with_dict(dict: ZstdCompressionDict) -> ZstdDecompressor:
        if ZstdDecompressor is None:
            raise RuntimeError("zstandard module is unavailable")
        if dict is None:
            raise ValueError("ZSTD dictionary is required for dictionary-compressed block")
        return ZstdDecompressor(dict)

    @staticmethod
    def _zstd_decompressor(dict: Optional[ZstdCompressionDict]) -> ZstdDecompressor:
        """Select the correct decoder constructor for plain vs dictionary ZSTD."""
        if dict is None:
            return PakCompression._zstd_decompressor_without_dict()
        return PakCompression._zstd_decompressor_with_dict(dict)

    @staticmethod
    def zstd_dictionary(dict_data) -> ZstdCompressionDict:
        if ZstdCompressionDict is None or DICT_TYPE_AUTO is None:
            raise RuntimeError("zstandard module is unavailable")
        if not dict_data:
            raise ValueError("empty ZSTD dictionary")
        return ZstdCompressionDict(dict_data, DICT_TYPE_AUTO)

    @staticmethod
    def decompress_block(
        block,
        dict: Optional[ZstdCompressionDict],
        compression_method: int,
        max_output_size: Optional[int] = None,
    ) -> bytes:
        if compression_method == CM_ZLIB:
            # Try standard zlib (with header) first.
            try:
                result = zlib.decompress(block)
            except zlib.error:
                # Fallback: raw DEFLATE (no zlib/gzip header, negative wbits).
                try:
                    result = zlib.decompress(block, wbits=-zlib.MAX_WBITS)
                except zlib.error as exc:
                    raise ValueError(
                        "decompression failed: block is neither valid zlib nor raw DEFLATE"
                    ) from exc
            if max_output_size and len(result) > int(max_output_size):
                raise ValueError("decompressed block exceeds declared output limit")
            return result
        elif compression_method == CM_ZSTD or compression_method == CM_ZSTD_DICT:
            if compression_method != CM_ZSTD_DICT:
                dict = None
            # Tencent PAK ZSTD frames may omit the content-size field. The
            # default decompress() then raises "error determining content size
            # from frame header". Supply a strict per-block output bound.
            limit = int(max_output_size or (64 * 1024 * 1024))
            if limit <= 0 or limit > 512 * 1024 * 1024:
                raise ValueError("invalid ZSTD output limit")
            result = PakCompression._zstd_decompressor(dict).decompress(
                block, max_output_size=limit
            )
            if len(result) > limit:
                raise ValueError("ZSTD block exceeds declared output limit")
            return result
        else:
            raise ValueError(f'Unknown compression method: {compression_method}')

class TencentPakFile:

    def __init__(self, file_path: PurePath, is_od=True):
        _alvsia_require_operation(('pak.unpack', 'pak.repack', 'pak.unpack_single', 'pak.repack_single', 'pak.diagnostics', 'pak.delete_entry', 'pak.delete_all', 'advanced.inject_any', 'advanced.inject_brplayer', 'advanced.same_size_hashfix', 'advanced.zsdic_hashfix', 'asset.unpack', 'obb.unpack', 'obb.repack', 'lab.editor.auto_pak', 'lab.playerpawn.auto_pak'))
        self._file_path = file_path
        with open(file_path, 'rb') as _sb1e9a39131ae:
            self._file_content = memoryview(_sb1e9a39131ae.read())
        self._is_od = is_od
        self._mount_point = PurePath()
        self._is_zstd_with_dict = 'zsdic' in str(self._file_path)
        self._zstd_dict = None
        self._files: List[TencentPakEntry] = []
        self._index: Dict[PurePath, Dict[str, TencentPakEntry]] = {}
        self._pak_info = TencentPakInfo(self._file_content, PakCrypto.zuc_keystream())
        self._verify_stem_hash()
        self._tencent_load_index()

    def _verify_stem_hash(self) -> None:
        if not self._is_od and self._pak_info.version >= 9:
            assert self._pak_info.stem_hash == zlib.crc32(self._file_path.stem.encode('utf-32le'))

    def _tencent_load_index(self) -> None:
        _s348b5384ebf7 = BASE_DIR / 'index_debug.txt'
        _sa051e2872adf = self._file_content[self._pak_info.index_offset:][:self._pak_info.index_size]
        _s76e0849234b7 = len(self._file_content)
        _sa8818ce51f00 = self._pak_info.index_offset + self._pak_info.index_size
        _scc798660995b = f'\n=================================\n        PAK INDEX DEBUG\n=================================\nPAK file          : {self._file_path}\nPAK file size     : {_s76e0849234b7}\nPAK version       : {self._pak_info.version}\nIndex encrypted   : {self._pak_info.index_encrypted}\nIndex offset      : {self._pak_info.index_offset}\nIndex size        : {self._pak_info.index_size}\nRaw index length  : {len(_sa051e2872adf)}\nIndex end         : {_sa8818ce51f00}\n=================================\n'
        print(_scc798660995b, flush=True)
        try:
            BASE_DIR.mkdir(parents=True, exist_ok=True)
            with open(_s348b5384ebf7, 'w', encoding='utf-8') as _s4bc868e5e0cb:
                _s4bc868e5e0cb.write(_scc798660995b)
        except Exception as e:
            print('Debug file write error:', e, flush=True)
        if self._pak_info.index_offset < 0 or self._pak_info.index_size < 0 or _sa8818ce51f00 > _s76e0849234b7:
            _s8808166cce94 = f'\n=== INDEX RANGE ERROR ===\nFile size         : {_s76e0849234b7}\nIndex offset      : {self._pak_info.index_offset}\nIndex size        : {self._pak_info.index_size}\nIndex end         : {_sa8818ce51f00}\n=========================\n'
            print(_s8808166cce94, flush=True)
            try:
                with open(_s348b5384ebf7, 'a', encoding='utf-8') as _s4bc868e5e0cb:
                    _s4bc868e5e0cb.write(_s8808166cce94)
            except Exception:
                pass
            raise ValueError('PAK index offset/size is outside the file.')
        if self._pak_info.index_encrypted:
            print('Index encryption detected.', flush=True)
            try:
                _sa051e2872adf = PakCrypto.decrypt_index(_sa051e2872adf, self._pak_info)
            except Exception as e:
                _s9fa7d45d95f7 = f'\n=== INDEX DECRYPT ERROR ===\n{type(e).__name__}: {e}\n===========================\n'
                print(_s9fa7d45d95f7, flush=True)
                try:
                    with open(_s348b5384ebf7, 'a', encoding='utf-8') as _s4bc868e5e0cb:
                        _s4bc868e5e0cb.write(_s9fa7d45d95f7)
                except Exception:
                    pass
                raise
        else:
            print('Index is not encrypted.', flush=True)
        _s63b65c85941d = f'\n=== INDEX AFTER DECRYPT ===\nIndex length      : {len(_sa051e2872adf)}\nFirst 16 bytes    : {bytes(_sa051e2872adf[:16]).hex()}\n===========================\n'
        print(_s63b65c85941d, flush=True)
        try:
            with open(_s348b5384ebf7, 'a', encoding='utf-8') as _s4bc868e5e0cb:
                _s4bc868e5e0cb.write(_s63b65c85941d)
        except Exception:
            pass
        try:
            self._verify_index_hash(_sa051e2872adf)
        except Exception as e:
            _s9f7c93207141 = f'\n=== INDEX HASH ERROR ===\n{type(e).__name__}: {e}\n========================\n'
            print(_s9f7c93207141, flush=True)
            try:
                with open(_s348b5384ebf7, 'a', encoding='utf-8') as _s4bc868e5e0cb:
                    _s4bc868e5e0cb.write(_s9f7c93207141)
            except Exception:
                pass
            raise
        try:
            self._load_index(_sa051e2872adf)
        except Exception as e:
            _s619995a82fa4 = f'\n=== INDEX LOAD ERROR ===\n{type(e).__name__}: {e}\n========================\n'
            print(_s619995a82fa4, flush=True)
            try:
                with open(_s348b5384ebf7, 'a', encoding='utf-8') as _s4bc868e5e0cb:
                    _s4bc868e5e0cb.write(_s619995a82fa4)
            except Exception:
                pass
            raise
        _s571239371976 = '\n=================================\n INDEX LOAD COMPLETED SUCCESSFULLY\n=================================\n'
        print(_s571239371976, flush=True)
        try:
            with open(_s348b5384ebf7, 'a', encoding='utf-8') as _s4bc868e5e0cb:
                _s4bc868e5e0cb.write(_s571239371976)
        except Exception:
            pass

    def _verify_index_hash(self, index_data) -> None:
        _s860f9b0ab543 = self._pak_info.index_hash
        if not self._is_od and self._pak_info.version >= 8:
            assert _s860f9b0ab543 == PakCrypto.rsa_extract(self._pak_info.packed_index_hash, RSA_MOD_2)
        assert _s860f9b0ab543 == SHA1.new(index_data).digest()

    @staticmethod
    def _construct_mount_point(mount_point: str) -> PurePath:
        _s618c3a7399cb = PurePath()
        for _s683bf62df053 in PurePath(mount_point).parts:
            if _s683bf62df053 != '..':
                _s618c3a7399cb /= _s683bf62df053
        return _s618c3a7399cb

    def _peek_content(self, offset: int, size: int, encryption_method: int) -> memoryview:
        size = PakCrypto.align_encrypted_content_size(size, encryption_method)
        return self._file_content[offset:][:size]

    def _peek_block_content(self, block: PakCompressedBlock, encryption_method: int) -> memoryview:
        _sef994aeed7fb = PakCrypto.align_encrypted_content_size(block.end - block.start, encryption_method)
        return self._file_content[block.start:][:_sef994aeed7fb]

    def _construct_zstd_dict(self, dict_entry: TencentPakEntry) -> None:
        assert not self._zstd_dict
        assert not dict_entry.encrypted
        assert dict_entry.compression_method == CM_NONE
        _s41bb931c4a96 = PakReader(self._peek_content(dict_entry.offset, dict_entry.size, 0))
        _scc7cac6d6f06 = _s41bb931c4a96.u8()
        _s2ce972b6572e = _s41bb931c4a96.u4()
        assert _scc7cac6d6f06 == _s41bb931c4a96.u4()
        _s086160e11595 = _s41bb931c4a96.s(_scc7cac6d6f06)
        self._zstd_dict = PakCompression.zstd_dictionary(_s086160e11595)

    def _load_index(self, index_data) -> None:
        if self._pak_info.version <= 10:
            raise ValueError(f'Unsupported version: {self._pak_info.version}')
        debug_path = BASE_DIR / 'index_debug.txt'
        reader = PakReader(index_data)
        self._mount_point = self._construct_mount_point(reader.string())
        file_count = reader.u4()
        self._files = [TencentPakEntry(reader, self._pak_info.version) for _ in range(file_count)]
        dir_count = reader.u8()
        skipped_bad_refs = 0
        skipped_bad_paths = 0

        def log_skip(message: str) -> None:
            _s540ed156ec16 = _alvsia_pak_debug_display(message)
            print(_s540ed156ec16, flush=True)
            try:
                with open(debug_path, 'a', encoding='utf-8') as _s7a74957a9147:
                    _s7a74957a9147.write(_s540ed156ec16 + '\n')
            except Exception:
                pass
        for dir_no in range(dir_count):
            raw_dir = reader.string()
            entry_count = reader.u8()
            parsed_entries = []
            for entry_no in range(entry_count):
                file_name = reader.string()
                raw_file_index = reader.i4()
                mapped_index = ~raw_file_index
                parsed_entries.append((entry_no, file_name, raw_file_index, mapped_index))
            dir_obj = PurePath(raw_dir)
            dir_parts = dir_obj.parts
            unsafe_dir = '\x00' in raw_dir or dir_obj.is_absolute() or '..' in dir_parts or ('\\' in raw_dir)
            if unsafe_dir:
                skipped_bad_paths += 1
                log_skip(f'[INDEX SKIP] dir={dir_no} unsafe path: {raw_dir!r}')
                continue
            e = {}
            for entry_no, file_name, raw_file_index, mapped_index in parsed_entries:
                unsafe_name = '\x00' in file_name or '/' in file_name or '\\' in file_name or (file_name in ('.', '..'))
                if unsafe_name:
                    skipped_bad_paths += 1
                    log_skip(f'[INDEX SKIP] dir={dir_no} entry={entry_no} unsafe filename: {file_name!r}')
                    continue
                if not 0 <= mapped_index < len(self._files):
                    skipped_bad_refs += 1
                    log_skip(f'[INDEX SKIP] dir={dir_no} entry={entry_no} file={file_name!r} raw_ref={raw_file_index} mapped_ref={mapped_index} files={len(self._files)}')
                    continue
                e[file_name] = self._files[mapped_index]
            if self._is_zstd_with_dict and dir_obj.name == 'zstddic':
                if len(e) == 1:
                    self._construct_zstd_dict(next(iter(e.values())))
                elif e:
                    log_skip(f'[INDEX SKIP] zstddic directory has {len(e)} valid entries; expected exactly 1')
                continue
            if e:
                self._index[dir_obj] = e
        self._index_parse_stats = {'file_entries': len(self._files), 'directory_records': dir_count, 'loaded_directories': len(self._index), 'skipped_bad_refs': skipped_bad_refs, 'skipped_bad_paths': skipped_bad_paths, 'reader_cursor': reader._cursor, 'index_length': len(index_data)}
        summary = f'\n=== INDEX PARSE SUMMARY ===\nFile entries       : {len(self._files)}\nDirectory records  : {dir_count}\nLoaded directories : {len(self._index)}\nSkipped bad refs   : {skipped_bad_refs}\nSkipped bad paths  : {skipped_bad_paths}\nPakReader cursor      : {reader._cursor}/{len(index_data)}\n===========================\n'
        print(summary, flush=True)
        try:
            with open(debug_path, 'a', encoding='utf-8') as f:
                f.write(summary)
        except Exception:
            pass

    def detect_dominant_style(self) -> dict:
        comp_counter = Counter()
        enc_counter = Counter()
        blk_counter = Counter()
        enc_flag_counter = Counter()
        total = len(self._files)
        if total == 0:
            return {'comp_method': CM_ZSTD, 'enc_method': 0, 'encrypted': False, 'block_size': 65536}
        for entry in self._files:
            comp_counter[entry.compression_method] += 1
            if entry.encrypted:
                enc_counter[entry.encryption_method] += 1
                enc_flag_counter['encrypted'] += 1
            else:
                enc_flag_counter['plain'] += 1
            if entry.compression_block_size:
                blk_counter[entry.compression_block_size] += 1
        non_none = [(m, c) for m, c in comp_counter.items() if m != CM_NONE]
        comp_method = max(non_none, key=lambda x: x[1])[0] if non_none else CM_NONE
        encrypted = enc_flag_counter.get('encrypted', 0) > enc_flag_counter.get('plain', 0)
        enc_method = enc_counter.most_common(1)[0][0] if encrypted and enc_counter else 0
        block_size = blk_counter.most_common(1)[0][0] if blk_counter else 65536
        return {'comp_method': comp_method, 'enc_method': enc_method, 'encrypted': encrypted, 'block_size': block_size}

    def list_existing_paths(self) -> List[str]:
        _s923c21165935 = []
        for _s0ae1e3cd5262, _s68f1c0e6347e in self._index.items():
            for _s9bb2390cf2a1 in _s68f1c0e6347e.keys():
                _s923c21165935.append(str(_s0ae1e3cd5262 / _s9bb2390cf2a1).replace('\\', '/').lstrip('/'))
        return _s923c21165935

    @staticmethod
    def _extract_entry_plain(pak_buffer: memoryview, entry: TencentPakEntry, file_path_for_crypto: PurePath, zstd_dict) -> bytes:
        """Extract a single entry's plaintext (decrypted + decompressed) bytes."""
        if entry.compression_method == CM_NONE:
            _se741c9e5b336 = PakCrypto.align_encrypted_content_size(entry.size, entry.encryption_method)
            _s2c1f87975662 = bytes(pak_buffer[entry.offset:][:_se741c9e5b336])
            if entry.encrypted:
                _s2c1f87975662 = PakCrypto.decrypt_block(_s2c1f87975662, file_path_for_crypto, entry.encryption_method)
            return _s2c1f87975662
        _sa2b725aa04a1 = []
        for _s233f3b8af19b in PakCrypto.generate_block_indices(len(entry.compressed_blocks), entry.encryption_method):
            _s352a9973d0a5 = entry.compressed_blocks[_s233f3b8af19b]
            _se51624ae001c = PakCrypto.align_encrypted_content_size(_s352a9973d0a5.end - _s352a9973d0a5.start, entry.encryption_method)
            _s3ab48815ace4 = bytes(pak_buffer[_s352a9973d0a5.start:][:_se51624ae001c])
            if entry.encrypted:
                _s3ab48815ace4 = PakCrypto.decrypt_block(_s3ab48815ace4, file_path_for_crypto, entry.encryption_method)
            _sbe77522f0741 = PakCompression.decompress_block(_s3ab48815ace4, zstd_dict, entry.compression_method)
            _sa2b725aa04a1.append(_sbe77522f0741)
        return b''.join(_sa2b725aa04a1)

    def inject_files(self, inject_plan: list, output_pak: Path) -> None:
        """Inject new files into this PAK, producing a new PAK at output_pak."""
        if not inject_plan:
            raise ValueError('inject_plan is empty — nothing to inject')
        console.print('[bold magenta]💉 CUSTOM INJECT[/bold magenta]')
        console.print(f'[white]Source PAK:[/] [yellow]{self._file_path.name}[/yellow]')
        console.print(f'[white]Output    :[/] [cyan]{output_pak.name}[/cyan]')
        console.print(f'[white]Injecting :[/] [green]{len(inject_plan)} new file(s)[/green]')
        console.print('[green]AUTO-INSERT: OFF — only files selected by the user are added.[/green]')
        console.print('\n[bold magenta]━━ STEP 1/5 : LOADING INJECT FILES ━━[/bold magenta]')
        work_items = []
        for i, item in enumerate(inject_plan):
            if item.get('plain_bytes') is not None:
                plain = item['plain_bytes']
            elif item.get('src_path') is not None:
                try:
                    plain = Path(item['src_path']).read_bytes()
                except Exception as e:
                    console.print(f"   [red]✗ Cannot read {item['src_path']}: {e} — skipping[/red]")
                    continue
            else:
                console.print(f'   [red]✗ Inject item {i} has no src_path or plain_bytes — skipping[/red]')
                continue
            internal = item['internal_path'].replace('\\', '/').lstrip('/')
            if not internal:
                console.print(f'   [red]✗ Empty internal_path for item {i} — skipping[/red]')
                continue
            parts = internal.rsplit('/', 1)
            if len(parts) == 2:
                dir_str, file_name = (parts[0], parts[1])
            else:
                dir_str, file_name = ('', parts[0])
            work_items.append({'dir_str': dir_str, 'file_name': file_name, 'internal_path': internal, 'plain': plain, 'comp_method': item['comp_method'], 'enc_method': item['enc_method'], 'encrypted': bool(item['encrypted']), 'block_size': item['block_size'], 'comp_level': item.get('comp_level', 19)})
            console.print(f'   [blue]✨[/] {internal} [dim]({len(plain):,} bytes)[/dim]')
        if not work_items:
            raise RuntimeError('No valid inject items after loading')
        console.print(f'[green]✔ Loaded {len(work_items)} file(s)[/green]')
        console.print('\n[bold magenta]━━ STEP 2/5 : ENCODING INJECT FILES ━━[/bold magenta]')
        keystream = PakCrypto.zuc_keystream()
        version = self._pak_info.version
        header_size = TencentPakInfo._mem_size(version)
        PAK_MAGIC = self._pak_info.magic
        orig_index_offset = self._pak_info.index_offset
        current_new_offset = orig_index_offset
        new_data_region = bytearray()
        new_injected_entries = []
        preferred_level = 19

        def _encrypt_plaintext(plaintext, pak_relative_path, encryption_method):
            if PakCrypto._is_simple1_method(encryption_method):
                return bytes((b ^ SIMPLE1_DECRYPT_KEY for b in plaintext))
            elif PakCrypto._is_simple2_method(encryption_method):
                pad = -len(plaintext) % SIMPLE2_BLOCK_SIZE
                plaintext += b'\x00' * pad
                key, = struct.unpack('<I', SIMPLE2_DECRYPT_KEY)
                rolling = key
                out = []
                for x, in struct.iter_unpack('<I', plaintext):
                    c = rolling ^ x
                    out.append(c)
                    rolling ^= c
                return struct.pack(f'<{len(out)}I', *out)
            elif PakCrypto._is_sm4_method(encryption_method):
                key = PakCrypto._derive_sm4_key(pak_relative_path, encryption_method)
                sm4 = PakCrypto._sm4_context_for_key(key)
                pad_len = -len(plaintext) % 16
                if pad_len > 0:
                    plaintext = plaintext + b'\x00' * pad_len
                out = bytearray()
                for i in range(0, len(plaintext), 16):
                    block = plaintext[i:i + 16]
                    if len(block) < 16:
                        block = block.ljust(16, b'\x00')
                    out.extend(sm4.encrypt(block))
                return bytes(out)
            return plaintext
        for item in work_items:
            plain = item['plain']
            comp_method = item['comp_method']
            enc_method = item['enc_method']
            encrypted = item['encrypted']
            block_size_val = item['block_size']
            file_path_for_crypto = PurePath(item['file_name'])
            if len(plain) == 0:
                new_injected_entries.append({'content_hash': SHA1.new(b'').digest(), 'offset': current_new_offset, 'uncompressed_size': 0, 'size': 0, 'comp_method': CM_NONE, 'enc_method': 0, 'encrypted': False, 'block_size_val': 0, 'compressed_blocks': [], 'unk1': 0, 'unk2': b'\x00' * 20, 'index_new_sep': 0, '_dir_path': PurePath(item['dir_str']) if item['dir_str'] else PurePath(), '_file_name': item['file_name']})
                continue
            if comp_method == CM_NONE:
                if encrypted:
                    aligned_size = PakCrypto.align_encrypted_content_size(len(plain), enc_method)
                    padded = plain + b'\x00' * (aligned_size - len(plain))
                    stored_data = _encrypt_plaintext(padded, file_path_for_crypto, enc_method)
                else:
                    stored_data = plain
                new_size = len(stored_data)
                new_compressed_blocks = []
            else:
                chunks = [plain[i:i + block_size_val] for i in range(0, len(plain), block_size_val)]
                if not chunks:
                    chunks = [b'']
                compressed_chunks = []
                for chunk in chunks:
                    comp = None
                    if comp_method in (CM_ZSTD, CM_ZSTD_DICT):
                        zstd_dict = self._zstd_dict if comp_method == CM_ZSTD_DICT else None
                        for lvl in range(22, 0, -1):
                            try:
                                c = ZstdCompressor(level=lvl, dict_data=zstd_dict, threads=1)
                                comp = c.compress(chunk)
                                break
                            except:
                                continue
                    elif comp_method == CM_ZLIB:
                        comp = zlib.compress(chunk, level=9)
                    if comp is None:
                        comp = chunk
                    compressed_chunks.append(comp)
                encrypted_chunks = []
                for comp_data in compressed_chunks:
                    if encrypted:
                        comp_data = _encrypt_plaintext(comp_data, file_path_for_crypto, enc_method)
                    encrypted_chunks.append(comp_data)
                n_blocks = len(encrypted_chunks)
                indices = PakCrypto.generate_block_indices(n_blocks, enc_method)
                physical_blocks = [None] * n_blocks
                for j, chunk_data in enumerate(encrypted_chunks):
                    physical_blocks[indices[j]] = chunk_data
                physical_offsets = []
                block_cursor = current_new_offset
                for phys_block in physical_blocks:
                    physical_offsets.append((block_cursor, block_cursor + len(phys_block)))
                    block_cursor += len(phys_block)
                new_compressed_blocks = physical_offsets
                stored_data = b''.join(physical_blocks)
                new_size = len(stored_data)
                if encrypted:
                    aligned_total = PakCrypto.align_encrypted_content_size(new_size, enc_method)
                    if aligned_total > new_size:
                        stored_data = stored_data + b'\x00' * (aligned_total - new_size)
                        new_size = aligned_total
            new_content_hash = SHA1.new(stored_data).digest()
            new_data_region.extend(stored_data)
            new_injected_entries.append({'content_hash': new_content_hash, 'offset': current_new_offset, 'uncompressed_size': len(plain), 'size': new_size, 'comp_method': comp_method, 'enc_method': enc_method if encrypted else 0, 'encrypted': encrypted, 'block_size_val': block_size_val, 'compressed_blocks': new_compressed_blocks, 'unk1': 0, 'unk2': b'\x00' * 20, 'index_new_sep': 0, '_dir_path': PurePath(item['dir_str']) if item['dir_str'] else PurePath(), '_file_name': item['file_name']})
            current_new_offset += new_size
        console.print(f'[green]✔ Encoded {len(new_injected_entries)} file(s)[/green]')
        new_entries = []
        entry_to_path = {}
        for dir_path, files in self._index.items():
            for fname, entry in files.items():
                entry_to_path[id(entry)] = (dir_path, fname)
        for i, entry in enumerate(self._files):
            dir_path, fname = entry_to_path.get(id(entry), (PurePath(), f'unknown_{i}'))
            new_entries.append({'content_hash': entry.content_hash, 'offset': entry.offset, 'uncompressed_size': entry.uncompressed_size, 'size': entry.size, 'comp_method': entry.compression_method, 'enc_method': entry.encryption_method if entry.encrypted else 0, 'encrypted': entry.encrypted, 'block_size_val': entry.compression_block_size, 'compressed_blocks': [(b.start, b.end) for b in entry.compressed_blocks], 'unk1': entry.unk1, 'unk2': entry.unk2, 'index_new_sep': entry.index_new_sep})
        new_entries.extend(new_injected_entries)
        index_data = bytearray()
        raw_orig_index = self._file_content[self._pak_info.index_offset:][:self._pak_info.index_size]
        if self._pak_info.index_encrypted:
            orig_index_decoded = PakCrypto.decrypt_index(bytes(raw_orig_index), self._pak_info)
        else:
            orig_index_decoded = bytes(raw_orig_index)
        orig_reader = PakReader(orig_index_decoded)
        orig_mount_len = orig_reader.i4()
        orig_mount_bytes = bytes(orig_reader.s(orig_mount_len))
        index_data.extend(struct.pack('<I', orig_mount_len))
        index_data.extend(orig_mount_bytes)
        index_data.extend(struct.pack('<I', len(new_entries)))
        for item in new_entries:
            index_data.extend(item['content_hash'])
            if version <= 1:
                index_data.extend(struct.pack('<Q', 0))
            index_data.extend(struct.pack('<Q', item['offset']))
            index_data.extend(struct.pack('<Q', item['uncompressed_size']))
            index_data.extend(struct.pack('<I', item['comp_method'] & CM_MASK))
            index_data.extend(struct.pack('<Q', item['size']))
            if version >= 5:
                index_data.extend(struct.pack('<B', item['unk1']))
                index_data.extend(item['unk2'] if item['unk2'] else b'\x00' * 20)
            if item['comp_method'] != CM_NONE and version >= 3:
                index_data.extend(struct.pack('<I', len(item['compressed_blocks'])))
                for start, end in item['compressed_blocks']:
                    index_data.extend(struct.pack('<Q', start))
                    index_data.extend(struct.pack('<Q', end))
            if version >= 4:
                index_data.extend(struct.pack('<I', item['block_size_val']))
                index_data.extend(struct.pack('<B', 1 if item['encrypted'] else 0))
            if version >= 12:
                index_data.extend(struct.pack('<I', item['enc_method']))
                index_data.extend(struct.pack('<I', item['index_new_sep']))
        file_to_dirname = {}
        for dir_path, files_dict in self._index.items():
            dir_str = dir_path.as_posix()
            for fname, entry in files_dict.items():
                for i, fe in enumerate(self._files):
                    if id(fe) == id(entry):
                        file_to_dirname[i] = (dir_str, fname)
                        break
        for i, item in enumerate(new_entries):
            if i not in file_to_dirname:
                if '_dir_path' in item:
                    file_to_dirname[i] = (item['_dir_path'].as_posix(), item['_file_name'])
                else:
                    file_to_dirname[i] = ('', f'file_{i}')
        all_dirs = []
        dir_to_files = {}
        for dir_path in self._index.keys():
            ds = dir_path.as_posix()
            all_dirs.append(ds)
            dir_to_files[ds] = []
        for i, item in enumerate(new_entries):
            ds, fn = file_to_dirname[i]
            if ds not in dir_to_files:
                dir_to_files[ds] = []
                all_dirs.append(ds)
            dir_to_files[ds].append((fn, i))
        index_data.extend(struct.pack('<Q', len(all_dirs)))
        for dir_str in all_dirs:
            files_list = dir_to_files[dir_str]
            if not dir_str or dir_str == '.':
                index_data.extend(struct.pack('<I', 0))
            else:
                if not dir_str.endswith('/'):
                    dir_str_with_slash = dir_str + '/'
                else:
                    dir_str_with_slash = dir_str
                dir_bytes = dir_str_with_slash.encode('utf-8') + b'\x00'
                index_data.extend(struct.pack('<I', len(dir_bytes)))
                index_data.extend(dir_bytes)
            index_data.extend(struct.pack('<Q', len(files_list)))
            for file_name, fi in files_list:
                name_bytes = file_name.encode('utf-8') + b'\x00'
                index_data.extend(struct.pack('<I', len(name_bytes)))
                index_data.extend(name_bytes)
                index_data.extend(struct.pack('<i', -fi - 1))
        index_data.extend(b'\x1d\x00\x00\x00..')
        index_hash = SHA1.new(bytes(index_data)).digest()
        if version > 7 and self._pak_info.index_encrypted:
            key = PakCrypto.rsa_extract(self._pak_info.packed_key, RSA_MOD_1)
            iv = PakCrypto.rsa_extract(self._pak_info.packed_iv, RSA_MOD_1)
            assert len(key) == 32 and len(iv) == 32
            padded = pad(bytes(index_data), AES.block_size)
            aes = AES.new(key, MODE_CBC, iv[:16])
            encrypted_index = aes.encrypt(padded)
        elif self._pak_info.index_encrypted:
            encrypted_index = bytes((b ^ SIMPLE1_DECRYPT_KEY for b in bytes(index_data)))
        else:
            encrypted_index = bytes(index_data)
        index_size = len(encrypted_index)
        new_index_offset = orig_index_offset + len(new_data_region)
        encrypted_magic = self._pak_info.magic ^ keystream[2]
        key_stream_hash = struct.pack('<5I', *keystream[4:][:5])
        encrypted_index_hash = bytes((a ^ b for a, b in zip(index_hash, key_stream_hash)))
        encrypted_index_size = index_size ^ (keystream[10] << 32 | keystream[11])
        encrypted_index_offset = new_index_offset ^ (keystream[0] << 32 | keystream[1])
        encrypted_flag_byte = (1 if self._pak_info.index_encrypted else 0) ^ keystream[3] & 255
        orig_data_region = bytearray(self._file_content[0:orig_index_offset])
        output_pak.parent.mkdir(parents=True, exist_ok=True)
        with open(output_pak, 'wb') as f:
            f.write(bytes(orig_data_region))
            f.write(bytes(new_data_region))
            f.write(encrypted_index)
            if version >= 7:
                key_unk1 = struct.pack('<8I', *keystream[7:][:8])
                unk1_plain = self._pak_info.unk1 if self._pak_info.unk1 else b'\x00' * 32
                encrypted_unk1 = bytes((a ^ b for a, b in zip(unk1_plain, key_unk1)))
                f.write(encrypted_unk1)
            if version >= 8:
                f.write(self._pak_info.packed_key if self._pak_info.packed_key else b'\x00' * 256)
                f.write(self._pak_info.packed_iv if self._pak_info.packed_iv else b'\x00' * 256)
                f.write(self._pak_info.packed_index_hash if self._pak_info.packed_index_hash else b'\x00' * 256)
            if version >= 9:
                f.write(struct.pack('<I', (self._pak_info.stem_hash or 0) ^ keystream[8]))
                f.write(struct.pack('<I', (self._pak_info.unk2 or 0) ^ keystream[9]))
            if version >= 12:
                f.write(self._pak_info.content_org_hash if self._pak_info.content_org_hash else b'\x00' * 20)
            f.write(struct.pack('<B', encrypted_flag_byte))
            f.write(struct.pack('<I', encrypted_magic))
            f.write(struct.pack('<I', version))
            if version >= 6:
                f.write(encrypted_index_hash)
            else:
                f.write(b'\x00' * 20)
            f.write(struct.pack('<Q', encrypted_index_size))
            f.write(struct.pack('<Q', encrypted_index_offset))
        console.print('[bold green]🎉 INJECT COMPLETE![/bold green]')
        console.print(f'[white]Output  :[/] [cyan]{output_pak.name}[/cyan]')

    def _write_to_disk(self, file_path: PurePath, entry: TencentPakEntry) -> None:
        _se33e912f7767 = entry.encryption_method
        _s5206fe150a33 = entry.compression_method
        console.print(f'[#00CCFF]{file_path.name}[/#00CCFF] - Encryption: {_se33e912f7767}, Compression: {_s5206fe150a33}, Blocks: {len(entry.compressed_blocks)}')
        # All writes go through a temp file and are renamed atomically on success.
        # This ensures the original file (if any) is preserved when decompression
        # or decryption fails — previously a "wb" open truncated the file before
        # any error could be detected.
        # Create an unpredictable, exclusive temporary file in the destination
        # directory. A predictable sibling name can be pre-created as a symlink
        # and make open(..., "wb") write outside the extraction root.
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=str(file_path.parent),
            prefix="." + file_path.name + ".",
            suffix=".alvsia-tmp",
            delete=False,
        ) as temp_handle:
            tmp_path = Path(temp_handle.name)
        try:
            if _se33e912f7767 == 17:
                with open(tmp_path, 'wb') as _sbb61cc6b3e63:
                    for _s576e50701491 in entry.compressed_blocks:
                        _s366d3d829edf = self._file_content[_s576e50701491.start:_s576e50701491.end]
                        _sbb61cc6b3e63.write(_s366d3d829edf)
                tmp_path.replace(file_path)
                return
            with open(tmp_path, 'wb') as _sbb61cc6b3e63:
                if _s5206fe150a33 == CM_NONE:
                    _sb96393f68f4d = self._peek_content(entry.offset, entry.size, _se33e912f7767)
                    if entry.encrypted:
                        _sb96393f68f4d = PakCrypto.decrypt_block(bytes(_sb96393f68f4d), file_path, _se33e912f7767)
                    _sbb61cc6b3e63.write(_sb96393f68f4d)
                    tmp_path.replace(file_path)
                    return
                for _s1f6d01ab75cb in PakCrypto.generate_block_indices(len(entry.compressed_blocks), _se33e912f7767):
                    _sb96393f68f4d = self._peek_block_content(entry.compressed_blocks[_s1f6d01ab75cb], _se33e912f7767)
                    if entry.encrypted:
                        _sb96393f68f4d = PakCrypto.decrypt_block(bytes(_sb96393f68f4d), file_path, _se33e912f7767)
                    remaining_size = max(0, int(getattr(entry, 'uncompressed_size', 0)) - _sbb61cc6b3e63.tell())
                    block_limit = None
                    if entry.compression_block_size > 0 and remaining_size > 0:
                        block_limit = min(int(entry.compression_block_size), remaining_size)
                    _sb96393f68f4d = PakCompression.decompress_block(
                        _sb96393f68f4d, self._zstd_dict, _s5206fe150a33,
                        max_output_size=block_limit,
                    )
                    if block_limit and len(_sb96393f68f4d) > block_limit:
                        raise ValueError("decompressed block exceeds PAK compression block size")
                    _sbb61cc6b3e63.write(_sb96393f68f4d)
            # Validate decompressed size before committing the rename.
            actual_size = tmp_path.stat().st_size
            expected_size = getattr(entry, 'uncompressed_size', None)
            if expected_size is not None and expected_size > 0 and actual_size != expected_size:
                raise ValueError(
                    f"decompressed size mismatch: expected {expected_size}, got {actual_size}"
                )
            tmp_path.replace(file_path)
        except Exception:
            # Clean up the temp file without touching the original.
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise

    def dump(self, out_path: PurePath) -> dict:
        """Extract every indexed file and return verifiable per-file statistics."""
        debug_path = BASE_DIR / 'index_debug.txt'

        def _log_path_debug(title, **values):
            try:
                BASE_DIR.mkdir(parents=True, exist_ok=True)
                lines = ['', f'=== {title} ===']
                for key, value in values.items():
                    lines.append(f'{key:<20}: {value!r}')
                lines.append('=' * (8 + len(title)))
                rendered = '\n'.join(lines) + '\n'
                print(rendered, flush=True)
                with open(debug_path, 'a', encoding='utf-8') as handle:
                    handle.write(rendered)
            except Exception:
                pass

        expected_files = sum(len(items) for items in self._index.values())
        stats = {
            'ok': False,
            'expected_files': expected_files,
            'written_files': 0,
            'skipped_files': 0,
            'skipped_directories': 0,
            'written_bytes': 0,
            'failures': [],
            'index_parse': getattr(self, '_index_parse_stats', {}),
        }

        def _failure(path, exc):
            item = {'path': str(path), 'error': f'{type(exc).__name__}: {exc}'[:500]}
            if len(stats['failures']) < 100:
                stats['failures'].append(item)
            _log_path_debug('EXTRACTION ENTRY FAILED', **item)

        mount_text = str(self._mount_point)
        if '\x00' in mount_text:
            raise ValueError('PAK mount point contains an embedded NUL character.')
        base_root = Path(out_path).resolve()
        safe_root = (base_root / mount_text).resolve()
        try:
            safe_root.relative_to(base_root)
        except ValueError as exc:
            raise ValueError('PAK mount point escapes the extraction directory.') from exc

        for dir_path, entries in self._index.items():
            dir_text = str(dir_path)
            if '\x00' in dir_text:
                stats['skipped_directories'] += 1
                stats['skipped_files'] += len(entries)
                _failure(dir_text, ValueError('directory contains an embedded NUL'))
                continue
            # Normalize PAK directory records before joining them to the
            # validated mount root. Some valid indexes encode the root as
            # "."/"" or "/" and must not be treated as host-absolute paths.
            dir_norm = dir_text.replace("\\", "/")
            dir_parts = tuple(
                part for part in dir_norm.split("/")
                if part not in ("", ".")
            )
            if any(part == ".." for part in dir_norm.split("/")):
                stats['skipped_directories'] += 1
                stats['skipped_files'] += len(entries)
                _failure(dir_text, ValueError('unsafe PAK directory path'))
                continue
            current_out_path = (
                safe_root / Path(*dir_parts)
                if dir_parts else safe_root
            ).resolve()
            try:
                current_out_path.relative_to(safe_root)
                current_out_path.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                stats['skipped_directories'] += 1
                stats['skipped_files'] += len(entries)
                _failure(dir_text, exc)
                continue

            for file_name, entry in entries.items():
                file_text = str(file_name)
                relative_name = str(PurePath(dir_path) / file_text).replace('\\', '/')
                # Some valid PAK indexes store the full relative filename in
                # the entry name instead of splitting it into directory records.
                # Treat separators as path components, but keep extraction strictly
                # beneath the validated mount root.
                if not file_text or '\x00' in file_text or file_text in ('.', '..'):
                    stats['skipped_files'] += 1
                    _failure(relative_name, ValueError('unsafe PAK filename'))
                    continue
                normalized_name = file_text.replace('\\', '/')
                # A root-level PAK directory is commonly represented as "." or
                # an empty PurePath. Do not reject that legitimate root component.
                dir_norm = str(dir_path).replace('\\', '/').strip('/')
                base_parts = () if dir_norm in ('', '.') else tuple(
                    part for part in dir_norm.split('/') if part not in ('', '.')
                )
                name_parts = tuple(part for part in normalized_name.split('/') if part not in ('', '.'))
                rel_parts = base_parts + name_parts
                rel_candidate = PurePosixPath(*rel_parts)
                if (
                    rel_candidate.is_absolute()
                    or not rel_parts
                    or any(part == '..' for part in rel_parts)
                ):
                    stats['skipped_files'] += 1
                    _failure(relative_name, ValueError('unsafe PAK relative path'))
                    continue
                target = (safe_root / Path(*rel_candidate.parts)).resolve()
                try:
                    target.relative_to(safe_root)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    self._write_to_disk(target, entry)
                    if not target.is_file():
                        raise OSError('extractor returned without creating a regular file')
                    actual_size = target.stat().st_size
                    expected_size = int(getattr(entry, 'uncompressed_size', 0) or 0)
                    if expected_size > 0 and actual_size != expected_size:
                        try:
                            target.unlink()
                        except OSError:
                            pass
                        raise ValueError(
                            f'output size mismatch: expected {expected_size}, got {actual_size}'
                        )
                    stats['written_files'] += 1
                    stats['written_bytes'] += actual_size
                except Exception as exc:
                    stats['skipped_files'] += 1
                    _failure(relative_name, exc)

        stats['ok'] = (
            stats['expected_files'] > 0
            and stats['written_files'] == stats['expected_files']
            and stats['skipped_files'] == 0
            and stats['skipped_directories'] == 0
        )
        _log_path_debug(
            'DUMP PATH SUMMARY',
            expected_files=stats['expected_files'],
            written_files=stats['written_files'],
            skipped_files=stats['skipped_files'],
            skipped_directories=stats['skipped_directories'],
            written_bytes=stats['written_bytes'],
        )
        return stats

    def dump_filtered(self, out_path: PurePath, extensions) -> dict:
        """
        Extract only entries whose filename ends with one of `extensions`.
        Internal directory structure is preserved under out_path.
        """
        normalized = tuple((ext.lower() if str(ext).startswith('.') else '.' + str(ext).lower() for ext in extensions))
        stats = {'matched': 0, 'extracted': 0, 'failed': 0, 'errors': []}
        safe_root = Path(out_path).resolve()
        for dir_path, files in self._index.items():
            for file_name, entry in files.items():
                if not str(file_name).lower().endswith(normalized):
                    continue
                stats['matched'] += 1
                target_dir = (safe_root / str(dir_path)).resolve()
                target_file = (target_dir / str(file_name)).resolve()
                try:
                    target_dir.relative_to(safe_root)
                    target_file.relative_to(safe_root)
                    target_dir.mkdir(parents=True, exist_ok=True)
                    self._write_to_disk(target_file, entry)
                    stats['extracted'] += 1
                except Exception as e:
                    stats['failed'] += 1
                    stats['errors'].append({'file': str(dir_path / file_name).replace('\\', '/'), 'error': str(e)})
                    console.print(f'[yellow]⚠ Skip {str(dir_path / file_name)}: {str(e)}[/yellow]')
        return stats

def _build_pak_filename_map(pak_file):
    """Build safe filename → full pak path map"""
    _se7f3ca17d472 = {}
    for _s7e683b8ac5c2, _se352e8c8e360 in pak_file._index.items():
        for _s36b96ef37a21 in _se352e8c8e360.keys():
            _sb2fd256adcad = str(PurePath(_s7e683b8ac5c2) / _s36b96ef37a21).replace('\\', '/')
            _s0787b701de33 = Path(_s36b96ef37a21).stem.lower()
            _s255a5bcfbd89 = Path(_s36b96ef37a21).suffix.lower()
            _s838b26bde2d8 = _s36b96ef37a21.lower()
            _s38f204919472 = f'{_s0787b701de33}{_s255a5bcfbd89}'
            _s947b4016c945 = _s0787b701de33
            for _sad3366e40b68 in (_s838b26bde2d8, _s38f204919472, _s947b4016c945):
                _se7f3ca17d472.setdefault(_sad3366e40b68, []).append(_sb2fd256adcad)
    return _se7f3ca17d472

def dump_unpacking_log(pak_file, output_log_path: Path):
    """Dump detailed unpacking log"""
    with open(output_log_path, 'w', encoding='utf-8') as log_file:
        log_file.write('=' * 80 + '\n')
        log_file.write('PAK UNPACKING DEBUG LOG\n')
        log_file.write('=' * 80 + '\n\n')
        log_file.write(f'PAK File: {pak_file._file_path}\n')
        log_file.write(f'PAK Info Version: {pak_file._pak_info.version}\n')
        log_file.write(f'Mount Point: {pak_file._mount_point}\n')
        log_file.write(f'Is ZSTD with Dict: {pak_file._is_zstd_with_dict}\n')
        log_file.write(f'Has ZSTD Dict: {pak_file._zstd_dict is not None}\n')
        log_file.write('-' * 80 + '\n\n')
        file_count = 0
        compression_stats = {}
        encryption_stats = {}
        block_stats = {}
        for dir_path, files in pak_file._index.items():
            for file_name, entry in files.items():
                file_count += 1
                full_path = str(PurePath(dir_path) / file_name).replace('\\', '/')
                comp_method = entry.compression_method
                compression_stats[comp_method] = compression_stats.get(comp_method, 0) + 1
                enc_method = entry.encryption_method
                encryption_stats[enc_method] = encryption_stats.get(enc_method, 0) + 1
                block_count = len(entry.compressed_blocks)
                block_stats[block_count] = block_stats.get(block_count, 0) + 1
                log_file.write(f'\n[{file_count}] {full_path}\n')
                log_file.write(f"  {'─' * 60}\n")
                log_file.write(f'  Uncompressed Size: {entry.uncompressed_size:,} bytes\n')
                log_file.write(f'  Compressed Size:   {entry.size:,} bytes\n')
                comp_method_name = {CM_NONE: 'NONE', CM_ZLIB: 'ZLIB', CM_ZSTD: 'ZSTD', CM_ZSTD_DICT: 'ZSTD_DICT'}.get(comp_method, f'UNKNOWN({comp_method})')
                log_file.write(f'  Compression Method: {comp_method_name} ({comp_method})\n')
                enc_method_name = 'NONE'
                if enc_method == EM_SIMPLE1:
                    enc_method_name = 'SIMPLE1'
                elif enc_method in (EM_SIMPLE2, EM_UNKNOWN_17):
                    enc_method_name = 'SIMPLE2'
                elif enc_method == EM_SM4_2:
                    enc_method_name = 'SM4_2'
                elif enc_method == EM_SM4_4:
                    enc_method_name = 'SM4_4'
                elif enc_method & EM_SM4_NEW_MASK != 0:
                    enc_method_name = f'SM4_NEW({enc_method})'
                else:
                    enc_method_name = f'UNKNOWN({enc_method})'
                log_file.write(f'  Encryption Method: {enc_method_name}\n')
                log_file.write(f'  Is Encrypted: {entry.encrypted}\n')
                log_file.write(f'  Compressed Blocks: {len(entry.compressed_blocks)}\n')
                log_file.write(f'  Compression Block Size: {entry.compression_block_size:,} bytes\n')
                if entry.compressed_blocks:
                    total_compressed = sum((blk.end - blk.start for blk in entry.compressed_blocks))
                    log_file.write(f'  Total Compressed Space: {total_compressed:,} bytes\n')
                    if entry.uncompressed_size > 0:
                        compression_ratio = total_compressed / entry.uncompressed_size
                        log_file.write(f'  Compression Ratio: {compression_ratio:.2%}\n')
                    for i, blk in enumerate(entry.compressed_blocks[:10]):
                        block_size = blk.end - blk.start
                        log_file.write(f'    Block {i}: Offset={blk.start:,} Size={block_size:,} bytes\n')
                    if len(entry.compressed_blocks) > 10:
                        log_file.write(f'    ... and {len(entry.compressed_blocks) - 10} more blocks\n')
                    block_sizes = [blk.end - blk.start for blk in entry.compressed_blocks]
                    if block_sizes:
                        log_file.write(f'  Min Block Size: {min(block_sizes):,} bytes\n')
                        log_file.write(f'  Max Block Size: {max(block_sizes):,} bytes\n')
                        log_file.write(f'  Avg Block Size: {sum(block_sizes) / len(block_sizes):,.0f} bytes\n')
                log_file.write(f"  {'─' * 60}\n")
        log_file.write('\n' + '=' * 80 + '\n')
        log_file.write('SUMMARY STATISTICS\n')
        log_file.write('=' * 80 + '\n\n')
        log_file.write(f'Total Files: {file_count}\n\n')
        log_file.write('Compression Methods:\n')
        for method, count in sorted(compression_stats.items()):
            method_name = {CM_NONE: 'NONE', CM_ZLIB: 'ZLIB', CM_ZSTD: 'ZSTD', CM_ZSTD_DICT: 'ZSTD_DICT'}.get(method, f'UNKNOWN({method})')
            log_file.write(f'  {method_name}: {count} files ({count / file_count * 100:.1f}%)\n')
        log_file.write('\nEncryption Methods:\n')
        for method, count in sorted(encryption_stats.items()):
            if method == EM_SIMPLE1:
                method_name = 'SIMPLE1'
            elif method == EM_SIMPLE2:
                method_name = 'SIMPLE2'
            elif method == EM_SM4_2:
                method_name = 'SM4_2'
            elif method == EM_SM4_4:
                method_name = 'SM4_4'
            elif method & EM_SM4_NEW_MASK != 0:
                method_name = f'SM4_NEW({method})'
            else:
                method_name = f'UNKNOWN({method})'
            log_file.write(f'  {method_name}: {count} files ({count / file_count * 100:.1f}%)\n')
        log_file.write('\nBlock Count Distribution:\n')
        for block_count, file_count_with_blocks in sorted(block_stats.items()):
            percentage = file_count_with_blocks / file_count * 100
            log_file.write(f'  {block_count:3d} blocks: {file_count_with_blocks:4d} files ({percentage:5.1f}%)\n')
        log_file.write('\n' + '=' * 80 + '\n')
        log_file.write('END OF LOG\n')
        log_file.write('=' * 80 + '\n')
    console.print(f'[bold #00FF88]✅ Debug log saved to: {output_log_path}[/bold #00FF88]')

def _alvsia_pak_encrypt_plaintext(plaintext: bytes, pak_relative_path: PurePath, encryption_method: int) -> bytes:
    """Mirror bahan.py payload encryption behavior for existing entries."""
    if PakCrypto._is_simple1_method(encryption_method):
        return bytes((b ^ SIMPLE1_DECRYPT_KEY for b in plaintext))
    if PakCrypto._is_simple2_method(encryption_method):
        pad_len = -len(plaintext) % SIMPLE2_BLOCK_SIZE
        plaintext += b'\x00' * pad_len
        key, = struct.unpack('<I', SIMPLE2_DECRYPT_KEY)
        rolling = key
        out = []
        for x, in struct.iter_unpack('<I', plaintext):
            c = rolling ^ x
            out.append(c)
            rolling ^= c
        return struct.pack(f'<{len(out)}I', *out)
    if PakCrypto._is_sm4_method(encryption_method):
        key = PakCrypto._derive_sm4_key(pak_relative_path, encryption_method)
        sm4 = PakCrypto._sm4_context_for_key(key)
        pad_len = -len(plaintext) % 16
        if pad_len:
            plaintext += b'\x00' * pad_len
        out = bytearray()
        for i in range(0, len(plaintext), 16):
            block = plaintext[i:i + 16]
            if len(block) < 16:
                block = block.ljust(16, b'\x00')
            out.extend(sm4.encrypt(block))
        return bytes(out)
    return plaintext

def _alvsia_pak_entry_map(pak):
    _s4184cf47039f = {}
    for _s0532244b9740, _s51252d1c742f in pak._index.items():
        for _s1a7065710c82, _sa6bb7cd505c6 in _s51252d1c742f.items():
            _s716d7db7eccd = str(PurePath(_s0532244b9740) / _s1a7065710c82).replace('\\', '/').lstrip('/')
            _s4184cf47039f[_s716d7db7eccd.lower()] = (_s716d7db7eccd, _sa6bb7cd505c6)
    return _s4184cf47039f

def _alvsia_pak_is_tool_artifact(path: Path) -> bool:
    _s1b0f995aa9bb = Path(path).name.lower()
    if _s1b0f995aa9bb in {'pak_manifest.json', 'index_debug.txt', '.ds_store', 'patched.txt'}:
        return True
    if _s1b0f995aa9bb.startswith('debug_') and _s1b0f995aa9bb.endswith('.log'):
        return True
    if _s1b0f995aa9bb.endswith('.validation.log') or _s1b0f995aa9bb.endswith('.acceptance_audit.log') or _s1b0f995aa9bb.endswith('.compare.log'):
        return True
    if _s1b0f995aa9bb.endswith('.stage_replace') or _s1b0f995aa9bb.startswith('.tmp_'):
        return True
    return False

def _alvsia_pak_normalize_repack_path(pak, repack_root: Path, file_path: Path) -> str:
    rel = file_path.relative_to(repack_root).as_posix().lstrip('/')
    mount = str(getattr(pak, '_mount_point', '')).replace('\\', '/').strip('/')
    safe_mount = '/'.join((part for part in mount.split('/') if part not in ('', '.', '..')))
    if safe_mount and rel.lower().startswith((safe_mount + '/').lower()):
        rel = rel[len(safe_mount) + 1:]
    return rel.lstrip('/')

def _alvsia_pak_scan_repack(pak, repack_root: Path) -> dict:
    """Classify Repack files strictly against existing source PAK paths."""
    source_map = _alvsia_pak_entry_map(pak)
    basename_map = {}
    for _key, (internal, entry) in source_map.items():
        basename_map.setdefault(PurePath(internal).name.lower(), []).append((internal, entry))
    matched = []
    unknown = []
    ignored = []
    for p in sorted(repack_root.rglob('*'), key=lambda x: str(x).lower()):
        if not p.is_file():
            continue
        if _alvsia_pak_is_tool_artifact(p):
            ignored.append(p)
            continue
        rel = _alvsia_pak_normalize_repack_path(pak, repack_root, p)
        key = rel.lower()
        row = source_map.get(key)
        if row is not None:
            matched.append((p, row[0]))
            continue
        if '/' in key:
            suffix = [row for src_key, row in source_map.items() if src_key.endswith('/' + key)]
            if len(suffix) == 1:
                matched.append((p, suffix[0][0]))
                continue
        if '/' not in rel:
            candidates = basename_map.get(p.name.lower(), [])
            if len(candidates) == 1:
                matched.append((p, candidates[0][0]))
                continue
        unknown.append((p, rel))
    return {'matched': matched, 'unknown': unknown, 'ignored': ignored}

def _alvsia_pak_extract_plain(pak, internal: str, entry) -> bytes:
    _s108c63e1eda0 = TencentPakFile._extract_entry_plain(pak._file_content, entry, PurePath(internal), pak._zstd_dict)
    return _s108c63e1eda0[:entry.uncompressed_size]

def _alvsia_pak_profile(entry):
    return {'compression_method': int(entry.compression_method), 'encrypted': bool(entry.encrypted), 'encryption_method': int(entry.encryption_method if entry.encrypted else 0), 'block_size': int(entry.compression_block_size or 0)}

def _alvsia_validate_dynamic_repack(original_path: Path, output_path: Path, targets: list, sample_non_targets: int=8) -> dict:
    """
    Validate dynamic repack using the RAW entry table as the source of truth.

    Why:
    Protected/obfuscated PAKs may expose several safe directory aliases that
    point to the same raw file entry, while other directory records are skipped.
    Path-level sampling therefore can count one raw entry several times.

    Hard invariants:
      - raw file-entry count/order stays stable
      - target raw entries may change size/offset/hash/blocks, but must preserve
        compression/encryption style and extract to the edited bytes exactly
      - every non-target raw entry keeps identical metadata and stored payload
      - protected directory/index tail remains byte-identical
      - PAK version, mount point, index-encryption state and safe path set remain valid
    """
    checks = []
    warnings = []

    def add(name, ok, detail=''):
        checks.append((name, bool(ok), str(detail)))
        return bool(ok)
    try:
        src = TencentPakFile(original_path)
        rep = TencentPakFile(output_path)
        add('PAK reopen', True, f'v{rep._pak_info.version}')
    except Exception as e:
        add('PAK reopen', False, f'{type(e).__name__}: {e}')
        return {'ok': False, 'checks': checks, 'warnings': warnings}
    add('PAK version', src._pak_info.version == rep._pak_info.version, f'{src._pak_info.version} == {rep._pak_info.version}')
    add('Mount point', str(src._mount_point) == str(rep._mount_point), f'{src._mount_point} == {rep._mount_point}')
    add('Index encryption', bool(src._pak_info.index_encrypted) == bool(rep._pak_info.index_encrypted), f'{bool(src._pak_info.index_encrypted)} == {bool(rep._pak_info.index_encrypted)}')
    smap = _alvsia_pak_entry_map(src)
    rmap = _alvsia_pak_entry_map(rep)
    add('Entry path set', set(smap) == set(rmap), f'missing={len(set(smap) - set(rmap))}, added={len(set(rmap) - set(smap))}')
    add('Raw entry count', len(src._files) == len(rep._files), f'{len(src._files)} == {len(rep._files)}')
    if len(src._files) != len(rep._files):
        return {'ok': False, 'checks': checks, 'warnings': warnings}
    src_id_to_raw = {id(e): i for i, e in enumerate(src._files)}
    target_raw = {}
    target_resolution_ok = True
    for t in targets:
        key = t['internal'].lower()
        row = smap.get(key)
        if row is None:
            warnings.append(f"Target missing in original path map: {t['internal']}")
            target_resolution_ok = False
            continue
        _internal, src_entry = row
        raw_idx = src_id_to_raw.get(id(src_entry))
        if raw_idx is None:
            warnings.append(f"Target has no raw-entry identity: {t['internal']}")
            target_resolution_ok = False
            continue
        if raw_idx in target_raw:
            prev = target_raw[raw_idx]
            if prev['data'] != t['data']:
                warnings.append(f"Aliased edited paths resolve to raw entry {raw_idx} with different data: {prev['internal']} vs {t['internal']}")
                target_resolution_ok = False
        else:
            target_raw[raw_idx] = t
    add('Target raw mapping', target_resolution_ok and len(target_raw) >= 1, f'{len(target_raw)} unique raw target(s)')

    def meta_signature(e):
        return (bytes(e.content_hash), int(e.offset), int(e.uncompressed_size), int(e.size), int(e.compression_method), bool(e.encrypted), int(e.encryption_method if e.encrypted else 0), int(e.compression_block_size or 0), tuple(((int(b.start), int(b.end)) for b in e.compressed_blocks)), int(e.unk1), bytes(e.unk2) if e.unk2 else b'', int(e.index_new_sep))

    def profile_signature(e):
        return (int(e.compression_method), bool(e.encrypted), int(e.encryption_method if e.encrypted else 0), int(e.compression_block_size or 0) if e.compression_method != CM_NONE else 0)

    def raw_payload_equal(obj_a, ea, obj_b, eb):
        if ea.compression_method == CM_NONE:
            _s45b5fbe9d38d = int(ea.offset)
            _sc38237768740 = _s45b5fbe9d38d + int(ea.size)
            _s0025a519bfa2 = int(eb.offset)
            _s29b49838969f = _s0025a519bfa2 + int(eb.size)
            return obj_a._file_content[_s45b5fbe9d38d:_sc38237768740] == obj_b._file_content[_s0025a519bfa2:_s29b49838969f]
        if len(ea.compressed_blocks) != len(eb.compressed_blocks):
            return False
        for _s01b565b31fac, _sb4c0ac578b4b in zip(ea.compressed_blocks, eb.compressed_blocks):
            _s768abd1cbf1b = obj_a._file_content[int(_s01b565b31fac.start):int(_s01b565b31fac.end)]
            _s0d9fc60b820e = obj_b._file_content[int(_sb4c0ac578b4b.start):int(_sb4c0ac578b4b.end)]
            if _s768abd1cbf1b != _s0d9fc60b820e:
                return False
        return True
    target_exact = 0
    target_profile = 0
    for raw_idx, t in target_raw.items():
        src_entry = src._files[raw_idx]
        rep_entry = rep._files[raw_idx]
        if profile_signature(src_entry) == profile_signature(rep_entry):
            target_profile += 1
        rep_internal = None
        row = rmap.get(t['internal'].lower())
        if row is not None:
            rep_internal = row[0]
            rep_entry_for_path = row[1]
        else:
            rep_entry_for_path = rep_entry
            for _k, (candidate_path, candidate_entry) in rmap.items():
                try:
                    rep_raw_idx = rep._files.index(candidate_entry)
                except ValueError:
                    continue
                if rep_raw_idx == raw_idx:
                    rep_internal = candidate_path
                    rep_entry_for_path = candidate_entry
                    break
        if rep_internal is None:
            warnings.append(f"No safe path alias found for rebuilt raw entry {raw_idx}: {t['internal']}")
            continue
        try:
            recovered = _alvsia_pak_extract_plain(rep, rep_internal, rep_entry_for_path)
            if recovered == t['data']:
                target_exact += 1
        except Exception as e:
            warnings.append(f'Raw target {raw_idx} extraction failed ({rep_internal}): {e}')
    add('Edited targets exact', target_exact == len(target_raw) and len(target_raw) > 0, f'{target_exact}/{len(target_raw)} raw target(s) exact')
    add('Edited profile preserved', target_profile == len(target_raw) and len(target_raw) > 0, f'{target_profile}/{len(target_raw)} raw target(s) preserve style')
    untouched_indices = [i for i in range(len(src._files)) if i not in target_raw]
    untouched_meta_ok = 0
    untouched_raw_ok = 0
    for i in untouched_indices:
        se = src._files[i]
        re_ = rep._files[i]
        if meta_signature(se) == meta_signature(re_):
            untouched_meta_ok += 1
        if raw_payload_equal(src, se, rep, re_):
            untouched_raw_ok += 1
    add('Untouched raw metadata', untouched_meta_ok == len(untouched_indices), f'{untouched_meta_ok}/{len(untouched_indices)} raw entry(s) identical')
    add('Untouched raw payload', untouched_raw_ok == len(untouched_indices), f'{untouched_raw_ok}/{len(untouched_indices)} raw entry(s) identical')

    def plain_index_and_tail(obj):
        _s62b30480d8d8 = bytes(obj._file_content[obj._pak_info.index_offset:obj._pak_info.index_offset + obj._pak_info.index_size])
        _s3d42721312c3 = PakCrypto.decrypt_index(_s62b30480d8d8, obj._pak_info) if obj._pak_info.index_encrypted else _s62b30480d8d8
        _s4faa7c951b1b = PakReader(_s3d42721312c3)
        _s2f5755627522 = _s4faa7c951b1b.i4()
        _s4faa7c951b1b.s(_s2f5755627522)
        _sca00e3a4ff81 = _s4faa7c951b1b.u4()
        for _sde29b3493cbd in range(_sca00e3a4ff81):
            TencentPakEntry(_s4faa7c951b1b, obj._pak_info.version)
        return (_s3d42721312c3, bytes(_s3d42721312c3[_s4faa7c951b1b._cursor:]))
    try:
        _src_plain, src_tail = plain_index_and_tail(src)
        _rep_plain, rep_tail = plain_index_and_tail(rep)
        add('Directory/index tail', src_tail == rep_tail, f'{len(src_tail)} == {len(rep_tail)} bytes; ' + ('IDENTICAL' if src_tail == rep_tail else 'DIFFERENT'))
    except Exception as e:
        add('Directory/index tail', False, f'{type(e).__name__}: {e}')
    return {'ok': all((ok for _name, ok, _detail in checks)), 'checks': checks, 'warnings': warnings}

def _dynamic_replace_single_entry(pak, target_entry, internal: str, new_plain: bytes, output_pak: Path) -> None:
    """Append a rebuilt payload for one existing entry and rebuild only entry metadata.

    The original payload area is kept byte-identical. The edited target payload is appended
    immediately before the rebuilt index. Directory/index tail bytes are preserved verbatim,
    so file-index references and protected directory records keep their original order.
    """
    version = pak._pak_info.version
    keystream = PakCrypto.zuc_keystream()
    orig_index_offset = pak._pak_info.index_offset
    target_index = None
    for i, e in enumerate(pak._files):
        if id(e) == id(target_entry):
            target_index = i
            break
    if target_index is None:
        raise RuntimeError('Target entry is not present in raw PAK entry table.')
    comp_method = target_entry.compression_method
    enc_method = target_entry.encryption_method if target_entry.encrypted else 0
    encrypted = bool(target_entry.encrypted)
    block_size = target_entry.compression_block_size or 65536
    crypto_path = PurePath(internal)

    def _compress_chunk(chunk: bytes) -> bytes:
        if comp_method == CM_NONE:
            return chunk
        if comp_method == CM_ZLIB:
            return zlib.compress(chunk, level=9)
        if comp_method in (CM_ZSTD, CM_ZSTD_DICT):
            _sb8c7274fd37c = pak._zstd_dict if comp_method == CM_ZSTD_DICT else None
            _s716541b85619 = None
            for _sabd395aeeb1c in range(22, 0, -1):
                try:
                    return ZstdCompressor(level=_sabd395aeeb1c, dict_data=_sb8c7274fd37c, threads=1).compress(chunk)
                except Exception as e:
                    _s716541b85619 = e
            raise RuntimeError(f'ZSTD compression failed: {_s716541b85619}')
        raise ValueError(f'Unsupported compression method: {comp_method}')
    new_payload_offset = orig_index_offset
    new_blocks = []
    if len(new_plain) == 0:
        stored = b''
        new_size = 0
        new_comp_method = CM_NONE
        new_enc_method = 0
        new_encrypted = False
        new_block_size = 0
    elif comp_method == CM_NONE:
        payload = new_plain
        if encrypted:
            aligned = PakCrypto.align_encrypted_content_size(len(payload), enc_method)
            payload = payload + b'\x00' * (aligned - len(payload))
            stored = _alvsia_pak_encrypt_plaintext(payload, crypto_path, enc_method)
        else:
            stored = payload
        new_size = len(stored)
        new_comp_method = CM_NONE
        new_enc_method = enc_method
        new_encrypted = encrypted
        new_block_size = 0
    else:
        chunks = [new_plain[i:i + block_size] for i in range(0, len(new_plain), block_size)]
        encoded_logical = []
        for chunk in chunks:
            comp = _compress_chunk(chunk)
            encoded = _alvsia_pak_encrypt_plaintext(comp, crypto_path, enc_method) if encrypted else comp
            encoded_logical.append(encoded)
        order = PakCrypto.generate_block_indices(len(encoded_logical), enc_method)
        physical = [None] * len(encoded_logical)
        for logical_idx, encoded in enumerate(encoded_logical):
            physical[order[logical_idx]] = encoded
        cursor = new_payload_offset
        for blob in physical:
            if blob is None:
                raise RuntimeError('Block permutation produced an empty physical slot.')
            new_blocks.append((cursor, cursor + len(blob)))
            cursor += len(blob)
        stored = b''.join(physical)
        new_size = len(stored)
        new_comp_method = comp_method
        new_enc_method = enc_method
        new_encrypted = encrypted
        new_block_size = block_size
    target_meta = {'content_hash': SHA1.new(stored).digest(), 'offset': new_payload_offset, 'uncompressed_size': len(new_plain), 'size': new_size, 'comp_method': new_comp_method, 'enc_method': new_enc_method, 'encrypted': new_encrypted, 'block_size_val': new_block_size, 'compressed_blocks': new_blocks, 'unk1': target_entry.unk1, 'unk2': target_entry.unk2, 'index_new_sep': target_entry.index_new_sep}
    raw_orig_index = bytes(pak._file_content[pak._pak_info.index_offset:pak._pak_info.index_offset + pak._pak_info.index_size])
    orig_plain_index = PakCrypto.decrypt_index(raw_orig_index, pak._pak_info) if pak._pak_info.index_encrypted else raw_orig_index
    r = PakReader(orig_plain_index)
    mount_len = r.i4()
    mount_bytes = bytes(r.s(mount_len))
    file_count = r.u4()
    if file_count != len(pak._files):
        raise RuntimeError(f'Index file-count mismatch: parsed={file_count}, loaded={len(pak._files)}')
    for _ in range(file_count):
        TencentPakEntry(r, version)
    original_tail = orig_plain_index[r._cursor:]
    index_data = bytearray()
    index_data.extend(struct.pack('<I', mount_len))
    index_data.extend(mount_bytes)
    index_data.extend(struct.pack('<I', file_count))
    for i, old in enumerate(pak._files):
        if i == target_index:
            item = target_meta
        else:
            item = {'content_hash': old.content_hash, 'offset': old.offset, 'uncompressed_size': old.uncompressed_size, 'size': old.size, 'comp_method': old.compression_method, 'enc_method': old.encryption_method if old.encrypted else 0, 'encrypted': old.encrypted, 'block_size_val': old.compression_block_size, 'compressed_blocks': [(b.start, b.end) for b in old.compressed_blocks], 'unk1': old.unk1, 'unk2': old.unk2, 'index_new_sep': old.index_new_sep}
        index_data.extend(item['content_hash'])
        if version <= 1:
            index_data.extend(struct.pack('<Q', 0))
        index_data.extend(struct.pack('<Q', item['offset']))
        index_data.extend(struct.pack('<Q', item['uncompressed_size']))
        index_data.extend(struct.pack('<I', item['comp_method'] & CM_MASK))
        index_data.extend(struct.pack('<Q', item['size']))
        if version >= 5:
            index_data.extend(struct.pack('<B', item['unk1']))
            index_data.extend(item['unk2'] if item['unk2'] else b'\x00' * 20)
        if item['comp_method'] != CM_NONE and version >= 3:
            index_data.extend(struct.pack('<I', len(item['compressed_blocks'])))
            for start, end in item['compressed_blocks']:
                index_data.extend(struct.pack('<Q', start))
                index_data.extend(struct.pack('<Q', end))
        if version >= 4:
            index_data.extend(struct.pack('<I', item['block_size_val']))
            index_data.extend(struct.pack('<B', 1 if item['encrypted'] else 0))
        if version >= 12:
            index_data.extend(struct.pack('<I', item['enc_method']))
            index_data.extend(struct.pack('<I', item['index_new_sep']))
    index_data.extend(original_tail)
    index_hash = SHA1.new(bytes(index_data)).digest()
    if version > 7 and pak._pak_info.index_encrypted:
        key = PakCrypto.rsa_extract(pak._pak_info.packed_key, RSA_MOD_1)
        iv = PakCrypto.rsa_extract(pak._pak_info.packed_iv, RSA_MOD_1)
        if len(key) != 32 or len(iv) < 16:
            raise RuntimeError('Invalid AES index key/IV while rebuilding dynamic index.')
        encrypted_index = AES.new(key, MODE_CBC, iv[:16]).encrypt(pad(bytes(index_data), AES.block_size))
    elif pak._pak_info.index_encrypted:
        encrypted_index = bytes((b ^ SIMPLE1_DECRYPT_KEY for b in bytes(index_data)))
    else:
        encrypted_index = bytes(index_data)
    new_index_offset = orig_index_offset + len(stored)
    index_size = len(encrypted_index)
    encrypted_magic = pak._pak_info.magic ^ keystream[2]
    key_stream_hash = struct.pack('<5I', *keystream[4:][:5])
    encrypted_index_hash = bytes((a ^ b for a, b in zip(index_hash, key_stream_hash)))
    encrypted_index_size = index_size ^ (keystream[10] << 32 | keystream[11])
    encrypted_index_offset = new_index_offset ^ (keystream[0] << 32 | keystream[1])
    encrypted_flag_byte = (1 if pak._pak_info.index_encrypted else 0) ^ keystream[3] & 255
    output_pak.parent.mkdir(parents=True, exist_ok=True)
    with output_pak.open('wb') as f:
        f.write(bytes(pak._file_content[:orig_index_offset]))
        f.write(stored)
        f.write(encrypted_index)
        if version >= 7:
            key_unk1 = struct.pack('<8I', *keystream[7:][:8])
            unk1_plain = pak._pak_info.unk1 if pak._pak_info.unk1 else b'\x00' * 32
            f.write(bytes((a ^ b for a, b in zip(unk1_plain, key_unk1))))
        if version >= 8:
            f.write(pak._pak_info.packed_key if pak._pak_info.packed_key else b'\x00' * 256)
            f.write(pak._pak_info.packed_iv if pak._pak_info.packed_iv else b'\x00' * 256)
            f.write(pak._pak_info.packed_index_hash if pak._pak_info.packed_index_hash else b'\x00' * 256)
        if version >= 9:
            f.write(struct.pack('<I', (pak._pak_info.stem_hash or 0) ^ keystream[8]))
            f.write(struct.pack('<I', (pak._pak_info.unk2 or 0) ^ keystream[9]))
        if version >= 12:
            f.write(pak._pak_info.content_org_hash if pak._pak_info.content_org_hash else b'\x00' * 20)
        f.write(struct.pack('<B', encrypted_flag_byte))
        f.write(struct.pack('<I', encrypted_magic))
        f.write(struct.pack('<I', version))
        if version >= 6:
            f.write(encrypted_index_hash)
        else:
            f.write(b'\x00' * 20)
        f.write(struct.pack('<Q', encrypted_index_size))
        f.write(struct.pack('<Q', encrypted_index_offset))
    console.print(f'[green]✓ Dynamic payload rebuilt:[/green] {len(new_plain):,} plain bytes → {len(stored):,} stored bytes, {len(new_blocks)} block(s)')


# =============================================================================
# ALVSIA PAK PHYSICAL DELETE / COMPACT ENGINE
# Adopted from runtime-proven pak_compact_tools1.py test
# =============================================================================

def _pakdel_norm_path(value: str) -> str:
    return str(value).replace('\\', '/').strip().lstrip('/')


def _pakdel_pack_string(value: str) -> bytes:
    if not value:
        return struct.pack('<i', 0)
    raw = value.encode('utf-8') + b'\x00'
    return struct.pack('<i', len(raw)) + raw


def _pakdel_encrypt_index(pak, plain_index: bytes) -> bytes:
    version = pak._pak_info.version
    if version > 7 and pak._pak_info.index_encrypted:
        if AES is None or pad is None:
            raise RuntimeError('pycryptodome belum tersedia. Install: pip install pycryptodome')
        key = PakCrypto.rsa_extract(pak._pak_info.packed_key, RSA_MOD_1)
        iv = PakCrypto.rsa_extract(pak._pak_info.packed_iv, RSA_MOD_1)
        if len(key) != 32 or len(iv) < 16:
            raise RuntimeError('Invalid AES index key/IV.')
        return AES.new(key, MODE_CBC, iv[:16]).encrypt(pad(plain_index, AES.block_size))
    if pak._pak_info.index_encrypted:
        return bytes((b ^ SIMPLE1_DECRYPT_KEY for b in plain_index))
    return plain_index


def _pakdel_write_footer(pak, fp, *, index_hash: bytes, index_size: int,
                         index_offset: int) -> None:
    keystream = PakCrypto.zuc_keystream()
    version = pak._pak_info.version
    encrypted_magic = pak._pak_info.magic ^ keystream[2]
    key_stream_hash = struct.pack('<5I', *keystream[4:][:5])
    encrypted_index_hash = bytes((a ^ b for a, b in zip(index_hash, key_stream_hash)))
    encrypted_index_size = index_size ^ (keystream[10] << 32 | keystream[11])
    encrypted_index_offset = index_offset ^ (keystream[0] << 32 | keystream[1])
    encrypted_flag_byte = (1 if pak._pak_info.index_encrypted else 0) ^ (keystream[3] & 255)

    if version >= 7:
        key_unk1 = struct.pack('<8I', *keystream[7:][:8])
        unk1_plain = pak._pak_info.unk1 if pak._pak_info.unk1 else b'\x00' * 32
        fp.write(bytes((a ^ b for a, b in zip(unk1_plain, key_unk1))))
    if version >= 8:
        fp.write(pak._pak_info.packed_key if pak._pak_info.packed_key else b'\x00' * 256)
        fp.write(pak._pak_info.packed_iv if pak._pak_info.packed_iv else b'\x00' * 256)
        fp.write(pak._pak_info.packed_index_hash if pak._pak_info.packed_index_hash else b'\x00' * 256)
    if version >= 9:
        fp.write(struct.pack('<I', (pak._pak_info.stem_hash or 0) ^ keystream[8]))
        fp.write(struct.pack('<I', (pak._pak_info.unk2 or 0) ^ keystream[9]))
    if version >= 12:
        fp.write(pak._pak_info.content_org_hash if pak._pak_info.content_org_hash else b'\x00' * 20)
    fp.write(struct.pack('<B', encrypted_flag_byte))
    fp.write(struct.pack('<I', encrypted_magic))
    fp.write(struct.pack('<I', version))
    fp.write(encrypted_index_hash if version >= 6 else b'\x00' * 20)
    fp.write(struct.pack('<Q', encrypted_index_size))
    fp.write(struct.pack('<Q', encrypted_index_offset))



def _compact_entry_stored_bytes(pak, entry) -> bytes:
    """Return the exact stored bytes belonging to an entry."""
    if entry.size <= 0:
        return b""
    enc_method = entry.encryption_method if entry.encrypted else 0
    stored_size = PakCrypto.align_encrypted_content_size(entry.size, enc_method)
    start = entry.offset
    end = start + stored_size
    if start < 0 or end > pak._pak_info.index_offset:
        raise ValueError(
            f"Entry payload range outside data region: offset={start}, stored={stored_size}, "
            f"index_offset={pak._pak_info.index_offset}"
        )
    return bytes(pak._file_content[start:end])


def _compact_entry_record(entry, new_offset: int) -> dict:
    """Clone an index entry while relocating absolute data/block offsets."""
    delta = new_offset - entry.offset
    blocks = [(b.start + delta, b.end + delta) for b in entry.compressed_blocks]
    return {
        "content_hash": entry.content_hash,
        "offset": new_offset,
        "uncompressed_size": entry.uncompressed_size,
        "compression_method": entry.compression_method,
        "size": entry.size,
        "unk1": entry.unk1,
        "unk2": entry.unk2,
        "compressed_blocks": blocks,
        "compression_block_size": entry.compression_block_size,
        "encrypted": bool(entry.encrypted),
        "encryption_method": entry.encryption_method if entry.encrypted else 0,
        "index_new_sep": entry.index_new_sep,
    }


def _compact_serialize_entry(item: dict, version: int) -> bytes:
    out = bytearray()
    out.extend(item["content_hash"])
    if version <= 1:
        out.extend(struct.pack("<Q", 0))
    out.extend(struct.pack("<Q", item["offset"]))
    out.extend(struct.pack("<Q", item["uncompressed_size"]))
    out.extend(struct.pack("<I", item["compression_method"] & CM_MASK))
    out.extend(struct.pack("<Q", item["size"]))
    if version >= 5:
        out.extend(struct.pack("<B", item["unk1"]))
        out.extend(item["unk2"] if item["unk2"] else b"\x00" * 20)
    if item["compression_method"] != CM_NONE and version >= 3:
        out.extend(struct.pack("<I", len(item["compressed_blocks"])))
        for start, end in item["compressed_blocks"]:
            out.extend(struct.pack("<Q", start))
            out.extend(struct.pack("<Q", end))
    if version >= 4:
        out.extend(struct.pack("<I", item["compression_block_size"]))
        out.extend(struct.pack("<B", 1 if item["encrypted"] else 0))
    if version >= 12:
        out.extend(struct.pack("<I", item["encryption_method"]))
        out.extend(struct.pack("<I", item["index_new_sep"]))
    return bytes(out)


def _compact_parse_raw_directory_map(pak):
    raw_index = bytes(
        pak._file_content[
            pak._pak_info.index_offset:
            pak._pak_info.index_offset + pak._pak_info.index_size
        ]
    )
    plain_index = (
        PakCrypto.decrypt_index(raw_index, pak._pak_info)
        if pak._pak_info.index_encrypted else raw_index
    )

    r = PakReader(plain_index)
    mount = r.string()
    file_count = r.u4()
    raw_entries = [TencentPakEntry(r, pak._pak_info.version) for _ in range(file_count)]

    dirs = []
    dir_count = r.u8()
    for _ in range(dir_count):
        raw_dir = r.string()
        n = r.u8()
        entries = []
        for _ in range(n):
            name = r.string()
            raw_ref = r.i4()
            mapped = ~raw_ref
            entries.append((name, raw_ref, mapped))
        dirs.append((raw_dir, entries))

    tail = bytes(plain_index[r._cursor:])
    return mount, raw_entries, dirs, tail


def compact_rebuild_pak(pak_path: Path, output_pak: Path,
                        delete_targets: list[str] | None = None,
                        empty_all: bool = False,
                        authorization_operation: str | None = None) -> dict:
    """Physically compact a PAK.

    delete_targets:
      remove selected visible paths and their unreferenced payloads.
    empty_all:
      remove every visible path, raw entry and payload.

    Surviving payload bytes are copied byte-for-byte; no decrypt/recompress occurs.
    Absolute payload and compressed-block offsets are relocated in the rebuilt index.
    """
    if authorization_operation is None:
        _alvsia_require_operation(('pak.repack', 'pak.repack_single'))
    else:
        allowed_compact_callers = {
            'pak.repack',
            'pak.repack_single',
            'pak.delete_entry',
            'pak.delete_all',
        }
        operation_id = str(authorization_operation)
        if operation_id not in allowed_compact_callers:
            raise RuntimeError('Invalid compact rebuild authorization operation')
        _alvsia_require_operation((operation_id,))
    # gmalg optional — pure ZUC fallback in zuc_keystream()
    if SHA1 is None:
        raise RuntimeError("Dependency pycryptodome belum tersedia.")

    pak_path = Path(pak_path)
    output_pak = Path(output_pak)
    if pak_path.resolve() == output_pak.resolve():
        raise ValueError("Output tidak boleh sama dengan source PAK.")

    source_sha_before = hashlib.sha256(pak_path.read_bytes()).hexdigest()
    pak = TencentPakFile(pak_path)
    before_paths = sorted(pak.list_existing_paths())
    before_set = set(before_paths)

    wanted = set()
    if delete_targets:
        wanted = {_pakdel_norm_path(x) for x in delete_targets if _pakdel_norm_path(x)}
    if empty_all:
        wanted = set(before_paths)

    if not empty_all:
        if not wanted:
            raise ValueError("Tidak ada target delete.")
        missing = sorted(wanted - before_set)
        if missing:
            raise ValueError("Target tidak ditemukan: " + ", ".join(missing))

    mount, raw_entries, raw_dirs, tail = _compact_parse_raw_directory_map(pak)

    # Build surviving directory references and determine which original raw entries
    # are still referenced after deletion.
    kept_dirs = []
    kept_raw_indices = set()
    removed_paths = []

    for raw_dir, entries in raw_dirs:
        kept = []
        for name, raw_ref, mapped in entries:
            internal = _pakdel_norm_path(
                ((raw_dir.rstrip("/") + "/") if raw_dir else "") + name
            )
            if internal in wanted:
                removed_paths.append(internal)
                continue
            if not (0 <= mapped < len(raw_entries)):
                raise ValueError(f"Invalid raw entry ref {raw_ref} for {internal}")
            kept.append((name, mapped))
            kept_raw_indices.add(mapped)
        if kept:
            kept_dirs.append((raw_dir, kept))

    if set(removed_paths) != wanted:
        unresolved = sorted(wanted - set(removed_paths))
        if unresolved:
            raise RuntimeError(
                "Target parser tidak ditemukan pada raw directory map: "
                + ", ".join(unresolved)
            )

    # Preserve original raw-entry ordering among survivors.
    survivor_old_indices = [i for i in range(len(raw_entries)) if i in kept_raw_indices]

    # Physically pack surviving payloads from byte 0 onward.
    new_data = bytearray()
    new_records = []
    old_to_new_index = {}

    for old_idx in survivor_old_indices:
        entry = raw_entries[old_idx]
        new_idx = len(new_records)
        old_to_new_index[old_idx] = new_idx

        new_offset = len(new_data)
        stored = _compact_entry_stored_bytes(pak, entry)
        new_data.extend(stored)
        new_records.append(_compact_entry_record(entry, new_offset))

    # Rebuild index from scratch.
    new_index = bytearray()
    new_index.extend(_pakdel_pack_string(mount))
    new_index.extend(struct.pack("<I", len(new_records)))
    for rec in new_records:
        new_index.extend(_compact_serialize_entry(rec, pak._pak_info.version))

    rebuilt_dirs = []
    for raw_dir, entries in kept_dirs:
        out_entries = []
        for name, old_idx in entries:
            if old_idx not in old_to_new_index:
                raise RuntimeError(f"Surviving path references removed raw entry: {raw_dir}/{name}")
            new_idx = old_to_new_index[old_idx]
            out_entries.append((name, ~new_idx))
        if out_entries:
            rebuilt_dirs.append((raw_dir, out_entries))

    new_index.extend(struct.pack("<Q", len(rebuilt_dirs)))
    for raw_dir, entries in rebuilt_dirs:
        new_index.extend(_pakdel_pack_string(raw_dir))
        new_index.extend(struct.pack("<Q", len(entries)))
        for name, raw_ref in entries:
            new_index.extend(_pakdel_pack_string(name))
            new_index.extend(struct.pack("<i", raw_ref))

    # Preserve any unknown trailer bytes that belonged to the plaintext index.
    new_index.extend(tail)

    plain_index = bytes(new_index)
    index_hash = SHA1.new(plain_index).digest()
    encrypted_index = _pakdel_encrypt_index(pak, plain_index)
    new_index_offset = len(new_data)

    output_pak.parent.mkdir(parents=True, exist_ok=True)
    with output_pak.open("wb") as f:
        f.write(new_data)
        f.write(encrypted_index)
        _pakdel_write_footer(
            pak, f,
            index_hash=index_hash,
            index_size=len(encrypted_index),
            index_offset=new_index_offset,
        )

    # Strong parser-side verification.
    outpak = TencentPakFile(output_pak)
    after_paths = sorted(outpak.list_existing_paths())
    after_set = set(after_paths)
    expected_after = before_set - wanted

    targets_absent = not (wanted & after_set)
    untouched_preserved = after_set == expected_after
    raw_expected = len(survivor_old_indices)
    raw_count_ok = len(outpak._files) == raw_expected

    old_size = pak_path.stat().st_size
    new_size = output_pak.stat().st_size
    size_reduced = new_size < old_size if wanted else new_size <= old_size

    source_sha_after = hashlib.sha256(pak_path.read_bytes()).hexdigest()
    source_untouched = source_sha_before == source_sha_after

    ok = (
        targets_absent
        and untouched_preserved
        and raw_count_ok
        and size_reduced
        and source_untouched
    )

    return {
        "ok": ok,
        "mode": "compact-empty" if empty_all else "compact-delete",
        "source": str(pak_path),
        "output": str(output_pak),
        "deleted": sorted(wanted),
        "visible_before": len(before_paths),
        "visible_after": len(after_paths),
        "raw_entries_before": len(raw_entries),
        "raw_entries_after": len(outpak._files),
        "expected_raw_entries_after": raw_expected,
        "target_absent": targets_absent,
        "untouched_paths_preserved": untouched_preserved,
        "directory_index_valid": True,
        "raw_entry_table_valid": raw_count_ok,
        "pak_reopen": True,
        "source_untouched": source_untouched,
        "old_file_size": old_size,
        "new_file_size": new_size,
        "bytes_removed": old_size - new_size,
        "size_reduced": size_reduced,
        "new_index_offset": outpak._pak_info.index_offset,
        "new_index_size": outpak._pak_info.index_size,
        "sha256": hashlib.sha256(output_pak.read_bytes()).hexdigest(),
    }


def delete_pak_entries(pak_path: Path, output_pak: Path, targets: list[str]) -> dict:
    """Public PakCore API: physical/multi delete + compact rebuild."""
    _alvsia_require_operation(('pak.delete_entry',))
    return compact_rebuild_pak(pak_path, output_pak, delete_targets=targets, empty_all=False, authorization_operation='pak.delete_entry')


def delete_all_from_pak(pak_path: Path, output_pak: Path) -> dict:
    """Public PakCore API: remove every entry/payload and keep a valid compact PAK."""
    _alvsia_require_operation(('pak.delete_all',))
    return compact_rebuild_pak(pak_path, output_pak, empty_all=True, authorization_operation='pak.delete_all')



# =============================================================================
# ALVSIA PUBLIC API — non-interactive (APK / CLI)
# =============================================================================

def run_pak_integrity_audit(pak_path, out_json=None):
    """Read-only structural audit and per-entry payload fingerprints for Tencent PAK."""
    _alvsia_require_operation(('pak.diagnostics', 'pak.unpack'))
    pak_path = Path(pak_path)
    pak = TencentPakFile(pak_path)
    file_size = len(pak._file_content)
    index_start = int(pak._pak_info.index_offset)
    index_end = index_start + int(pak._pak_info.index_size)
    report = {
        'ok': True,
        'file': pak_path.name,
        'file_size': file_size,
        'file_sha256': hashlib.sha256(pak._file_content).hexdigest(),
        'pak_version': int(pak._pak_info.version),
        'index_offset': index_start,
        'index_size': int(pak._pak_info.index_size),
        'index_end': index_end,
        'entry_count': len(pak._files),
        'referenced_path_count': 0,
        'entries': [],
        'invalid_ranges': [],
        'overlaps': [],
        'duplicate_content_hashes': [],
        'unreferenced_entries': [],
        'parse_stats': getattr(pak, '_index_parse_stats', {}),
    }
    if index_start < 0 or index_end < index_start or index_end > file_size:
        report['invalid_ranges'].append({
            'kind': 'index', 'start': index_start, 'end': index_end,
            'reason': 'index range outside file'
        })
    referenced = {}
    for directory, files in (getattr(pak, '_index', {}) or {}).items():
        for name, entry in files.items():
            referenced[id(entry)] = str(directory / name).replace('\\', '/')
    report['referenced_path_count'] = len(referenced)
    ranges = []
    hashes = {}
    for idx, entry in enumerate(pak._files):
        internal = referenced.get(id(entry))
        if internal is None:
            report['unreferenced_entries'].append(idx)
            internal = ''
        entry_ranges = []
        if entry.compression_method == CM_NONE:
            stored_len = PakCrypto.align_encrypted_content_size(
                int(entry.size), int(entry.encryption_method)
            ) if entry.encrypted else int(entry.size)
            entry_ranges.append((int(entry.offset), int(entry.offset) + stored_len))
        else:
            for block_no, block in enumerate(entry.compressed_blocks):
                entry_ranges.append((int(block.start), int(block.end)))
        valid_ranges = []
        for range_no, (start, end) in enumerate(entry_ranges):
            if start < 0 or end < start or end > index_start:
                report['invalid_ranges'].append({
                    'entry': idx, 'path': internal, 'block': range_no,
                    'start': start, 'end': end,
                    'reason': 'payload range outside data region'
                })
            else:
                valid_ranges.append((start, end))
                if end > start:
                    ranges.append((start, end, idx, internal, range_no))
        payload_digest = hashlib.sha256()
        for start, end in valid_ranges:
            payload_digest.update(pak._file_content[start:end])
        slot_meta = '|'.join((
            str(idx), internal, str(int(entry.offset)),
            str(int(entry.size)), str(int(entry.uncompressed_size)),
            str(int(entry.compression_method)), str(int(entry.encryption_method)),
            str(bool(entry.encrypted)), payload_digest.hexdigest()
        )).encode('utf-8')
        fingerprint = hashlib.sha256(slot_meta).hexdigest()
        content_hash = bytes(entry.content_hash).hex()
        if content_hash:
            hashes.setdefault(content_hash, []).append(idx)
        report['entries'].append({
            'index': idx, 'path': internal,
            'offset': int(entry.offset), 'stored_size': int(entry.size),
            'uncompressed_size': int(entry.uncompressed_size),
            'compression_method': int(entry.compression_method),
            'encryption_method': int(entry.encryption_method),
            'encrypted': bool(entry.encrypted),
            'block_count': len(entry.compressed_blocks),
            'content_hash': content_hash,
            'payload_sha256': payload_digest.hexdigest(),
            'slot_fingerprint_sha256': fingerprint,
            'ranges': [{'start': a, 'end': b} for a, b in valid_ranges],
        })
    for content_hash, indices in hashes.items():
        if len(indices) > 1:
            report['duplicate_content_hashes'].append({
                'content_hash': content_hash, 'entries': indices
            })
    ranges.sort(key=lambda item: (item[0], item[1]))
    overlap_limit = 10000
    active = []
    for current in ranges:
        start, end, idx, path, block_no = current
        active = [item for item in active if item[1] > start]
        for other in active:
            if other[2] != idx:
                report['overlaps'].append({
                    'entry_a': other[2], 'path_a': other[3], 'block_a': other[4],
                    'entry_b': idx, 'path_b': path, 'block_b': block_no,
                    'overlap_start': max(start, other[0]),
                    'overlap_end': min(end, other[1]),
                    'note': 'Shared/overlapping payload ranges require format-aware review'
                })
                if len(report['overlaps']) >= overlap_limit:
                    break
        active.append(current)
        if len(report['overlaps']) >= overlap_limit:
            break
    report['overlaps_truncated'] = len(report['overlaps']) >= overlap_limit
    report['ok'] = not report['invalid_ranges']
    report['warnings'] = ['overlapping payload ranges detected'] if report['overlaps'] else []
    if out_json:
        target = Path(out_json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, sort_keys=True), encoding='utf-8')
        report['out'] = str(target)
    return report


def run_pak_unpack(pak_path, out_dir, authorization_operation='pak.unpack'):
    """Full unpack PAK/OBB-as-pak to out_dir. Returns dict status."""
    _alvsia_require_operation((authorization_operation, 'pak.unpack'))
    pak_path = Path(pak_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pak = TencentPakFile(pak_path)
    # Prefer dump if available
    if hasattr(pak, 'dump'):
        stats = pak.dump(out_dir)
        if not isinstance(stats, dict):
            return {
                'ok': False,
                'error': 'PAK extractor did not return verifiable extraction statistics',
                'out': str(out_dir),
            }
        expected = int(stats.get('expected_files', 0))
        written = int(stats.get('written_files', 0))
        skipped = int(stats.get('skipped_files', 0))
        actual_on_disk = sum(1 for p in out_dir.rglob('*') if p.is_file())
        stats["on_disk"] = actual_on_disk
        if expected <= 0:
            return {
                'ok': False,
                'error': 'PAK index contains no extractable file entries',
                'stats': stats,
                'out': str(out_dir),
            }
        if (
            not stats.get('ok')
            or skipped > 0
            or written != expected
            or actual_on_disk != expected
        ):
            return {
                'ok': False,
                'error': (
                    f'incomplete PAK extraction: expected={expected}, '
                    f'written={written}, on_disk={actual_on_disk}, skipped={skipped}'
                ),
                'stats': stats,
                'out': str(out_dir),
            }
        return {
            'ok': True,
            'files': actual_on_disk,
            'stats': stats,
            'out': str(out_dir),
        }
    elif hasattr(pak, 'extract_all'):
        # Legacy providers may not return statistics. Do not report success
        # unless a non-empty index and exact on-disk file count can be verified.
        index = getattr(pak, '_index', {}) or {}
        expected = sum(len(items) for items in index.values())
        if expected <= 0:
            return {'ok': False, 'error': 'PAK index contains no extractable file entries', 'out': str(out_dir)}
        pak.extract_all(out_dir)
        actual = sum(1 for p in out_dir.rglob('*') if p.is_file())
        if actual != expected:
            return {
                'ok': False,
                'error': f'incomplete legacy PAK extraction: expected={expected}, on_disk={actual}',
                'out': str(out_dir),
            }
        return {'ok': True, 'files': actual, 'out': str(out_dir)}
    else:
        # Manual compatibility path: any failed entry or count mismatch is fatal.
        n = 0
        failures = []
        index = getattr(pak, '_index', {}) or {}
        expected = sum(len(items) for items in index.values())
        if expected <= 0:
            return {'ok': False, 'error': 'PAK index contains no extractable file entries', 'out': str(out_dir)}
        for dir_path, files in index.items():
            cur = out_dir / str(dir_path)
            try:
                cur.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                failures.append({'path': str(dir_path), 'error': str(e)[:300]})
                continue
            for name, entry in files.items():
                try:
                    pak._write_to_disk(cur / name, entry)
                    n += 1
                except Exception as e:
                    failures.append({'path': str(PurePath(dir_path) / name), 'error': str(e)[:300]})
        actual = sum(1 for p in out_dir.rglob('*') if p.is_file())
        if failures or n != expected or actual != expected:
            return {
                'ok': False,
                'error': f'incomplete manual PAK extraction: expected={expected}, written={n}, on_disk={actual}, failures={len(failures)}',
                'failures': failures[:100],
                'out': str(out_dir),
            }
        return {'ok': True, 'files': actual, 'out': str(out_dir)}


def run_pak_repack(pak_path, modified_dir, output_pak, authorization_operation='pak.repack'):
    """Smart repack: inject all files under modified_dir into a new PAK."""
    _alvsia_require_operation((authorization_operation, 'pak.repack', 'pak.repack_single'))
    pak_path = Path(pak_path)
    modified_dir = Path(modified_dir)
    output_pak = Path(output_pak)
    output_pak.parent.mkdir(parents=True, exist_ok=True)
    if not modified_dir.is_dir():
        return {'ok': False, 'error': 'modified_dir missing'}
    pak = TencentPakFile(pak_path)
    plan = []
    for f in modified_dir.rglob('*'):
        if not f.is_file():
            continue
        rel = f.relative_to(modified_dir).as_posix()
        plan.append({
            'src_path': str(f),
            'internal_path': rel,
            'comp_method': CM_NONE,
            'enc_method': 0,
            'encrypted': False,
            'block_size': 65536,
            'comp_level': 19,
        })
    if not plan:
        return {'ok': False, 'error': 'no files under modified_dir'}
    try:
        pak.inject_files(plan, output_pak)
        return {'ok': True, 'out': str(output_pak), 'injected': len(plan)}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def run_pak_delete_entries(pak_path, output_pak, targets):
    """Physical delete selected paths + compact."""
    return delete_pak_entries(Path(pak_path), Path(output_pak), list(targets))


def run_pak_delete_all(pak_path, output_pak):
    return delete_all_from_pak(Path(pak_path), Path(output_pak))


def run_clear_tree(path):
    """Delete work/out tree safely."""
    p = Path(path)
    if not p.exists():
        return {'ok': True, 'cleared': 0}
    n = 0
    import shutil
    if p.is_file():
        p.unlink()
        return {'ok': True, 'cleared': 1}
    for child in list(p.iterdir()):
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            try:
                child.unlink()
            except Exception:
                pass
        n += 1
    return {'ok': True, 'cleared': n}


def run_pak_list(pak_path, out_txt=None):
    """List all visible paths; optional save to out_txt."""
    _alvsia_require_operation(('pak.unpack', 'pak.list'))
    pak = TencentPakFile(Path(pak_path))
    paths = pak.list_existing_paths() if hasattr(pak, 'list_existing_paths') else []
    if not paths and getattr(pak, '_index', None):
        for d, files in pak._index.items():
            for name in files:
                paths.append((str(d).rstrip('/') + '/' + name).lstrip('/'))
    text = '\n'.join(sorted(set(paths)))
    if out_txt:
        Path(out_txt).parent.mkdir(parents=True, exist_ok=True)
        Path(out_txt).write_text(text, encoding='utf-8')
    return {'ok': True, 'count': len(paths), 'paths': paths[:50], 'out': str(out_txt) if out_txt else None}


def run_pak_info(pak_path, out_txt=None):
    _alvsia_require_operation(('pak.unpack',))
    pak_path = Path(pak_path)
    pak = TencentPakFile(pak_path)
    info = getattr(pak, '_pak_info', None)
    lines = [
        f'file={pak_path}',
        f'size={pak_path.stat().st_size}',
        f'sha256={hashlib.sha256(pak_path.read_bytes()).hexdigest()}',
    ]
    if info is not None:
        for attr in ('version', 'magic', 'index_offset', 'index_size', 'index_encrypted'):
            if hasattr(info, attr):
                lines.append(f'{attr}={getattr(info, attr)}')
    paths = []
    try:
        paths = pak.list_existing_paths()
        lines.append(f'entries={len(paths)}')
    except Exception:
        pass
    text = '\n'.join(lines)
    if out_txt:
        Path(out_txt).parent.mkdir(parents=True, exist_ok=True)
        Path(out_txt).write_text(text, encoding='utf-8')
    return {'ok': True, 'info': text, 'out': str(out_txt) if out_txt else None}


def run_file_simple1_crypt(path, output, encrypt=True):
    """Whole-file SIMPLE1 XOR (signature-style lock/unlock)."""
    _alvsia_require_operation(('pak.repack', 'pak.unpack'))
    path = Path(path)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = path.read_bytes()
    out = bytes((b ^ SIMPLE1_DECRYPT_KEY for b in data))
    output.write_bytes(out)
    return {'ok': True, 'out': str(output), 'bytes': len(out), 'mode': 'encrypt' if encrypt else 'decrypt'}


def run_pak_smart_repack(pak_path, modified_dir, output_pak):
    """Match files under modified_dir to existing PAK paths and inject."""
    _alvsia_require_operation(('pak.repack', 'pak.repack_single'))
    pak_path = Path(pak_path)
    modified_dir = Path(modified_dir)
    output_pak = Path(output_pak)
    pak = TencentPakFile(pak_path)
    scan = _alvsia_pak_scan_repack(pak, modified_dir)
    plan = []
    for src, internal in scan['matched']:
        plan.append({
            'src_path': str(src),
            'internal_path': internal,
            'comp_method': CM_NONE,
            'enc_method': 0,
            'encrypted': False,
            'block_size': 65536,
            'comp_level': 19,
        })
    if not plan:
        return {
            'ok': False,
            'error': 'no matched paths',
            'unknown': [str(u[0]) for u in scan.get('unknown', [])][:20],
        }
    try:
        pak.inject_files(plan, output_pak)
        return {
            'ok': True,
            'out': str(output_pak),
            'injected': len(plan),
            'unknown': len(scan.get('unknown', [])),
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def _alvsia_core_active_proof_status():
    try:
        proof = _ALVSIA_CORE_ACTIVE_PROOF
        return str(proof.get('operation_id', '')) if isinstance(proof, dict) else ''
    except Exception:
        return ''
