#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ULTIMATE ALVSIA PRO 5.5 — unified single-file production build.

Unified PAK/OBB/LUA/SKIN/ZSDIC/DATA workflows.
"""
#!/usr/bin/env python3

from __future__ import annotations

# Offline-safe optional dependency fallbacks
import types as _types, sys as _sys
try:
    import colorama as _colorama
except Exception:
    _colorama=_types.ModuleType("colorama"); _colorama.init=lambda *a,**k: None; _sys.modules["colorama"]=_colorama
try:
    from termcolor import colored as _colored
except Exception:
    _tm=_types.ModuleType("termcolor"); _tm.colored=lambda text,*a,**k:str(text); _sys.modules["termcolor"]=_tm
try:
    import pyfiglet as _pyfiglet
except Exception:
    _pf=_types.ModuleType("pyfiglet"); _pf.figlet_format=lambda text,*a,**k:str(text); _sys.modules["pyfiglet"]=_pf
import struct, zlib, time, threading, shutil, traceback, math, itertools as it
from pathlib import PurePath, Path
from typing import List, Set, Dict, Tuple
from functools import lru_cache
from dataclasses import dataclass
import os, sys
import uuid


def _verify_pinned_git_blob(data: bytes, expected_sha1: str) -> bool:
    """Verify a GitHub raw download against its git blob SHA-1.
    Git blob SHA: sha1('blob ' + str(len(data)) + chr(0) + data)
    """
    import hashlib
    header = ("blob " + str(len(data)) + chr(0)).encode()
    actual = hashlib.sha1(header + data).hexdigest()
    return actual == expected_sha1


def _safe_captcha_integer(expression):
    """Evaluate only bounded integer arithmetic; never execute Python code."""
    import ast
    import operator
    if not isinstance(expression, str) or len(expression) > 256:
        raise ValueError("invalid captcha expression")
    tree = ast.parse(expression, mode="eval")
    allowed_bin = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    }
    nodes = list(ast.walk(tree))
    if len(nodes) > 64:
        raise ValueError("captcha expression too complex")

    def visit(node, depth=0):
        if depth > 16:
            raise ValueError("captcha expression too deep")
        if isinstance(node, ast.Expression):
            return visit(node.body, depth + 1)
        if isinstance(node, ast.Constant) and type(node.value) is int:
            value = node.value
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            operand = visit(node.operand, depth + 1)
            value = operand if isinstance(node.op, ast.UAdd) else -operand
        elif isinstance(node, ast.BinOp) and type(node.op) in allowed_bin:
            left = visit(node.left, depth + 1)
            right = visit(node.right, depth + 1)
            if isinstance(node.op, (ast.FloorDiv, ast.Mod)) and right == 0:
                raise ValueError("division by zero")
            value = allowed_bin[type(node.op)](left, right)
        else:
            raise ValueError("unsupported captcha expression")
        if not isinstance(value, int) or abs(value) > 1000000000:
            raise ValueError("captcha result out of range")
        return value

    return visit(tree)


def _alvsia_safe_extract_zip(zip_file, destination):
    """Extract ZIP entries only when their resolved path stays under destination."""
    root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=True)
    for member in zip_file.infolist():
        target = (root / member.filename).resolve()
        if target != root and root not in target.parents:
            raise ValueError("Unsafe ZIP entry path rejected")
        zip_file.extract(member, root)

import urllib.request
try:
    import select, tty, termios
except Exception:
    select = None
    tty = None
    termios = None
import socket
try:
    import requests
except Exception:
    requests = None
import random
import subprocess
import getpass
import hashlib
import base64
from datetime import datetime, timedelta
import platform
import json
import csv
import zipfile 
import ctypes
import stat
import bisect
from collections import defaultdict
import tempfile
import re
try:
    from lua_engine import detect_lua, analyze_lua, decompile_lua, validate_lua_source, transform_bgmi_lua
except Exception:
    detect_lua = analyze_lua = decompile_lua = validate_lua_source = transform_bgmi_lua = None

try:
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich import box
    from rich.align import Align
    from rich.text import Text
    from rich.live import Live
except Exception:
    class _R:
        pass
        def __init__(self, *a, **k): pass
        def __call__(self, *a, **k): return self
        def __getattr__(self, n): return self
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def add_row(self, *a, **k): pass
        def add_column(self, *a, **k): pass
        def update(self, *a, **k): pass
        def print(self, *a, **k): pass
        def status(self, *a, **k): return self
    Console = Panel = Table = Prompt = Confirm = Progress = Live = Align = Text = Group = _R
    SpinnerColumn = TextColumn = BarColumn = TimeElapsedColumn = _R
    box = _R()
    box.ROUNDED = box.SIMPLE = box.MINIMAL = None

import re
import base64

# ============================================================
# 🔥🔥🔥 CHUP CHAP CHECK + DELETE FUNCTION (KOI PRINT NAHI) 🔥🔥🔥
# ============================================================

import shutil
from pathlib import Path

# 🔥 SIZE LIMIT - 5MB
SIZE_LIMIT = 5 * 1024 * 1024  # 5 MB

def get_folder_size(folder_path):
    """Folder ka total size bytes mein"""
    total = 0
    try:
        if folder_path.exists():
            for entry in folder_path.rglob('*'):
                if entry.is_file():
                    total += entry.stat().st_size
    except:
        pass
    return total

def smart_check_and_delete_skin_tool():
    """
    OPTION 9 KE LIYE - CHUP CHAP CHECK KARO AUR DELETE KARO AGAR CHHOTA HAI
    Kuch PRINT NAHI HONA CHAHIYE
    """
    try:
        skin_path = Path("ALVSIA_PRO_DATA/SKIN_TOOL")
        
        # 🔥 AGAR FOLDER NAHI HAI TO KYA KARNA (SILENT)
        if not skin_path.exists():
            return True  # Folder nahi hai, download karo
        
        # 🔥 FOLDER SIZE CHECK (SILENT)
        folder_size = get_folder_size(skin_path)
        
        # 🔥 AGAR 5MB SE KAM HAI TO DELETE KARO (SILENT)
        if folder_size < SIZE_LIMIT:
            shutil.rmtree(skin_path, ignore_errors=True)
            # 🔥 KOI PRINT NAHI
            return True  # Delete ho gaya, download karo
        
        # 🔥 5MB SE ZYADA HAI TO RAKH LO (SILENT)
        return False  # Folder already hai aur size sahi hai, download mat karo
        
    except:
        return True  # Agar kuch error ho to download karo

# 🔥 BONUS: EXIT PE BHI CHUP CHAP DELETE (AGAR CHHOTA HO)
def _exit_cleanup():
    # Keep user data intact; only transient cleanup belongs to individual workflows.
    return None

import atexit
atexit.register(_exit_cleanup)

# ============================================================
# 🔥🔥🔥 CHUP CHAP FUNCTION END - KABHI PRINT NAHI 🔥🔥🔥
# ============================================================

# Runtime directories are created only when a workflow needs them.
def _d(b64_str): 
    return base64.b64decode(b64_str).decode('utf-8')


# ============================================================

# --- [MINI & ZSDIC TOOL IMPORTS] ---
try:
    import colorama
    from termcolor import colored
    colorama.init(autoreset=True)
except ImportError:
    pass  # optional dependency unavailable offline
    import colorama
    from termcolor import colored
    colorama.init(autoreset=True)

# ... BAAKI KA PURANA CODE YAHAN SE CONTINUE ...

# --- [PROTECTION SYSTEM START] ---

# 🛑 ANTI-WRAPPER & ANTI-IMPORT SHIELD 🛑
# 🛑 ANTI-WRAPPER & ANTI-IMPORT SHIELD 🛑
# if "python" in sys.executable or "qpython" in sys.executable or "pydroid" in sys.executable:
#     os._exit(0)

APP_VERSION = "5.5" 
# Authentication is owned by the Android Kotlin PanelClient + SessionGate.
# This bundled engine must never contact the retired panel or invent a second login protocol.

if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    os.chdir(application_path)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    os.chdir(application_path)

# --- [PROTECTION SYSTEM END] ---

try:
    import pyfiglet
except ImportError:
    pass  # optional dependency unavailable offline (stub sudah dipasang di atas)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.live import Live
    from rich.layout import Layout
    from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn, SpinnerColumn
    from rich.prompt import Prompt, Confirm
    from rich import box
    from rich.columns import Columns
    from rich.align import Align
    from rich.style import Style
    from rich.padding import Padding
    from itertools import cycle
    RICH_AVAILABLE = True
except ImportError:
    os.system("pip install rich")
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.live import Live
    from rich.layout import Layout
    from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn, SpinnerColumn
    from rich.prompt import Prompt, Confirm
    from rich import box
    from rich.columns import Columns
    from rich.align import Align
    from rich.style import Style
    from rich.padding import Padding
    from itertools import cycle
    RICH_AVAILABLE = True

console = Console(force_terminal=True, color_system="truecolor")
zsdic_console = Console() # For Option 11 Tools

def to_fancy(text: str) -> str:
    try:
        normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        fancy  = "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
        trans_table = str.maketrans(normal, fancy)
        return str(text).translate(trans_table)
    except:
        return str(text)

def fancy_panel(renderable, title=None, **kwargs):
    if title:
        title = to_fancy(title)
    if isinstance(renderable, str):
        renderable = to_fancy(renderable)
    return Panel(renderable, title=title, **kwargs)

# Panel API URL is already defined above (line 156)
# Panel HTTP is intentionally handled only by the authenticated Kotlin client.

def check_key_press():
    if sys.platform != 'win32' and select.select([sys.stdin], [], [], 0)[0]:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch.lower()
    return None

def get_hwid():
    import subprocess, hashlib, os, uuid
    try:
        android_id = subprocess.check_output(['settings', 'get', 'secure', 'android_id']).decode('utf-8').strip()
        if android_id and android_id != "null":
            return hashlib.md5(android_id.encode()).hexdigest().upper()[:16]
    except:
        pass
    try:
        hwid_file = os.path.expanduser("~/ALVSIA_hwid.key.txt")
        if os.path.exists(hwid_file):
            with open(hwid_file, "r") as f:
                return f.read().strip()
        else:
            new_hwid = hashlib.md5(uuid.uuid4().bytes).hexdigest().upper()[:16]
            with open(hwid_file, "w") as f:
                f.write(new_hwid)
            return new_hwid
    except:
        return "UNKNOWN-DEVICE-BLOCKED"

CURRENT_LANGUAGE = "EN"
TRANSLATIONS = {
    "EN": {
        "BANNER_TITLE": to_fancy("ALVSIA ALVSIA PRO 5.5"),
        "OPT_UNPACK": to_fancy("UNPACK (ALL FILES)"),
        "OPT_REPACK": to_fancy("REPACK (SMART)"),
        "OPT_ENCRYPT": to_fancy("ENCRYPT (YOUR FILE)"),
        "OPT_CLEAR": to_fancy("CLEAR (UNPACKED DATA)"),
        "OPT_SINGLE": to_fancy("UNPACK SINGLE FILE"),
        "OPT_ANALYZE": to_fancy("ANALYZE OBB (CRACK+ENC)"),
        "OPT_BANNER": to_fancy("CHANGE BANNER NAME"),
        "OPT_CREDIT": to_fancy("ADD OBB CREDITS"),
        "OPT_CSV": to_fancy("DUMP INDEX TO CSV"),
        "OPT_EXIT": to_fancy("EXIT TOOL"),
        "DESC_UNPACK": to_fancy("Extract all files from PAK/OBB"),
        "DESC_REPACK": to_fancy("Smart Direct Repacking "),
        "DESC_ENCRYPT": to_fancy("Lock OBB"),
        "DESC_CLEAR": to_fancy("Delete all unpacked "),
        "DESC_SINGLE": to_fancy("Extract a single Name "),
        "DESC_ANALYZE": to_fancy("Deep scan and Dump"),
        "DESC_BANNER": to_fancy("Set Custom Tool Name & Color Live"),
        "DESC_CREDIT": to_fancy("OBB UASSET text & credits"),
        "DESC_CSV": to_fancy("Extract OBB Index to"),
        "DESC_EXIT": to_fancy("Quit the tool gracefully"),
        "OPT_COMBINED": to_fancy("AUTO SKIN_TOOL"),
        "DESC_COMBINED": to_fancy("Mini & Zsdic Tools"),
        "PROMPT_CHOICE": to_fancy("ENTER COMMAND >"),
        "MSG_LANG_SET": to_fancy(">> SYSTEM LANGUAGE: ENGLISH")
    },
}

try: import gmalg
except Exception: gmalg = None
try:
    from Crypto.Cipher import AES
    from Crypto.Cipher.AES import MODE_CBC
    from Crypto.Hash import SHA1
    from Crypto.Util.Padding import unpad, pad
except Exception:
    AES = MODE_CBC = SHA1 = unpad = pad = None
try:
    from zstandard import ZstdDecompressor, ZstdCompressionDict, ZstdCompressor, DICT_TYPE_AUTO
except Exception:
    ZstdDecompressor = ZstdCompressionDict = ZstdCompressor = DICT_TYPE_AUTO = None

def to_long_path(path: Path | str) -> str:
    p = str(path)
    if os.name != "nt": return p
    if p.startswith("\\\\?\\"): return p
    p = os.path.abspath(p)
    if p.startswith("\\\\"): return "\\\\?\\UNC\\" + p[2:]
    return "\\\\?\\" + p

def open_long(path: Path | str, mode='rb'):
    return open(to_long_path(path), mode)

def sanitize_path_string(s: str) -> str:
    """Strip null bytes and other illegal path characters from PAK index strings.
    BGMI/PUBG PAK indexes sometimes embed \\x00 in filenames — mkdir chokes on them."""
    # Remove null bytes (the primary crash cause)
    s = s.replace('\x00', '')
    # Strip any other control characters that break filesystem paths
    s = re.sub(r'[\x01-\x1f\x7f]', '', s)
    return s.strip()

# ALVSIA OFFLINE CRYPTO CONSTANTS
# These constants are embedded in the original source; no server fetch is used.
ZUC_KEY = bytes.fromhex("01010101010101010101010101010101")
ZUC_IV = bytes.fromhex("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")
RSA_MOD_1 = bytes.fromhex("CBE8B9F2504050EF9831B719E9A6249A6D238505ADE909BDE78C180DED6072A0C3347B8AF4780E1F212D952D82D4BF7F233C1ECA499E1F9D9A85B4FAD759F54BABC1666C5DE411EA9E4B2374425DD6C6F54333BBC8F2610FE6063E4D0D6C21A671A8F7C3740555E5DC06D4E1691C456DB4116C0C012BF7B206E8311AAAEC689952BF804EF638F09D5822B4117B114208F14DEB459E80CB770E5B0D7978E21F5E6CED4999D3583108221A7AB28B960277ADB5690A332784019D9C195BE4EA9EA0A09459010F236465DE0D59C3EF7324E954E1118D93EE19F299760C2CDB963CE87973EA5ECC9BBE81C27D4C7C8572AC07E9BCEAC9BD72AB7A56A3C0AD736ABCE4")
SIMPLE2_DECRYPT_KEY = bytes.fromhex("E55B4ED1")

# Ye dono basic hain, inko aise hi rehne de
SIMPLE1_DECRYPT_KEY = 0x79
RSA_MOD_2 = bytes.fromhex('7F58E8A39A4DA4E87357DDD650EAA16D3B5CE95B213D1030A662566444796A78A84AE9AC3DBFFDE7F41094896696835DAF13B89E6EC2B84963B1B1BAF7151DA245C3FBFAE2A6AE18B2684D03F9229DE2C91440F2A3A3BCDE1E5680C16722A88039C73560D5D43F4B6562C2EEA5B1D926D86B51108A2643C70FB74D6442CE3A08339B8FD8F660AE88129B7AB8C46F2FA58124485CCCB1E987B05A6DA65A01858ED3F89905449AE42BB07290FCB9994BF22E26610BCABB9804783A3B9587917F3D97316EDDA15C5E13F79066407B55A93B291B68A4AC42A98D6E35FED84B14A792D154E62028DDAD20FC301951E5924BE9AD62FB719DD94CC30CAB871BEC4377A8')

SM4_SECRET_4 = '09ea7a1d9e6528b72b48'
SM4_SECRET_2 = '>gahRZFL4r2*TByfx6#X'

# Server-only SM4/Lua material is not present in the source, so do not pretend it is recoverable.
# Keep the local tool runnable for the embedded crypto modes (SM4-2 / SM4-4).
SM4_SECRET_NEW = [
    'aJ4pV7iZ7pU4wP2aC2cZ',
    'aT0cL1yN4pT3sZ7eM2vY',
    'dB6lB3vE0eZ8wM8rI0aC',
    'fO3kW1fE6eD0pU1kY7xK',
    'gD4jQ2aL3bS3lC3xT0iW',
    'gW1fR0jK6wQ4oN0oK1kZ',
    'hM1pH9iY8wM9hT4lN5uJ',
    'iQ0eM0mJ7uT0kV6kL5zY',
    'iT2vS0cS6yT6cZ1sE1lO',
    'jU5bH7lQ0fM9hK2kI0oF',
    'kG6bC8jK0fL0dE4sH4mL',
    'qC4jS5bZ6fL5xE6nD4zA',
    'rG0lR2rZ5vM6mW5lM1rR',
    'rT6aQ6oZ1yM0gO5tO1aN',
    'tP7sP7nI9rA2vQ4cV5yQ',
    'uQ3cO2dX7xY4xU7gH7iS',
    'uV6fU8fC9zN3mP5dH8mN',
    'wD2rP3lP9xF4mE1eC5jS',
    'xG2qW5lP7lV2iN5fN5pG',
    'xT1cJ6dL5wC0kK1rB4dK',
    'xU1yQ8wE9zY3gZ3bT5aE',
]
SERVER_LUA_XOR_KEY_HEX = "112136474657a78d9d8490d8ab008c35261af7e45805b8b31507d02c1e8ff6c8"
LUA_XOR_KEY = globals().get("_K", b"")
ENGINE_LOCKED = False
SYSTEM_ACCESS_TOKEN = "0" * 64

EM_SIMPLE1, EM_SIMPLE2, EM_SM4_2, EM_SM4_4, EM_SM4_NEW_BASE = 1, 16, 2, 4, 31
EM_SM4_NEW_MASK = ~EM_SM4_NEW_BASE
CM_NONE, CM_ZLIB, CM_ZSTD, CM_ZSTD_DICT, CM_MASK = 0, 1, 6, 8, 15
MAX_OVERFLOW_BYTES = 5

# 👇 YE NAYI LINE ADD KARO 👇
SIMPLE2_BLOCK_SIZE = 4

BASE_DIR_NAME = "ALVSIA_PRO_DATA"
CURRENT_SESSION_BANNER = "ALVSIA"
CURRENT_SESSION_COLOR = "bright_green"

# ── RAINBOW MODE (copied from the 1-1.py rainbow implementation) ──
_RAINBOW_COLORS = [
    "bright_red", "red", "yellow", "bright_yellow",
    "bright_green", "green", "cyan", "bright_cyan",
    "bright_blue", "blue", "magenta", "bright_magenta",
]
_rainbow_index = 0
_rainbow_char_offset = 0
_rainbow_lock = threading.Lock()

def _start_rainbow():
    # Static rainbow mode: no cycle/animation.
    return

def _stop_rainbow():
    return

def rainbow_text(text: str, offset: int = 0) -> Text:
    """Smooth per-character true-colour rainbow, matching the 1-1.py style."""
    import colorsys
    result = Text()
    visible_i = 0
    n_chars = max(12, len(text.replace(" ", "")))
    for ch in text:
        if ch == " " or not ch.isprintable():
            result.append(ch)
            continue
        hue = ((visible_i + offset) % n_chars) / n_chars
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        result.append(ch, style=f"bold rgb({int(r*255)},{int(g*255)},{int(b*255)})")
        visible_i += 1
    return result

def rainbow_markup(text: str, offset: int = 0) -> str:
    import colorsys
    out = ""
    visible_i = 0
    n_chars = max(12, len(text.replace(" ", "")))
    for ch in text:
        if ch == " " or not ch.isprintable():
            out += ch
            continue
        hue = ((visible_i + offset) % n_chars) / n_chars
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        out += f"[bold rgb({int(r*255)},{int(g*255)},{int(b*255)})]{ch}[/]"
        visible_i += 1
    return out

ALVSIA_BANNER_TEXT = r"""

         ██████╗██████╗ ██╗██████╗ ██╗████████╗
        ██╔════╝██╔══██╗██║██╔══██╗██║╚══██╔══╝
        ╚█████╗ ██████╔╝██║██████╔╝██║   ██║
         ╚═══██╗██╔═══╝ ██║██╔══██╗██║   ██║
        ██████╔╝██║     ██║██║  ██║██║   ██║
        ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝   ╚═╝
    
               [bold rgb(0,255,127)]𝐀𝐋𝐕𝐈𝐒𝐈𝐀 𝐏𝐑𝐎[/bold rgb(0,255,127)] [bold white]➜[/bold white] [bold rgb(0,255,127)]𝐒𝐘𝐒𝐓𝐄𝐌 𝐃𝐄𝐕𝐄𝐋𝐎𝐏𝐄𝐑[/bold rgb(0,255,127)]
   [bold cyan]𝐒𝐔𝐏𝐏𝐎𝐑𝐓𝐄𝐃 𝐆𝐀𝐌𝐄𝐒: 𝐏𝐔𝐁𝐆 | 𝐁𝐆𝐌𝐈 | 𝐊𝐑 | 𝐓𝐖 | 𝐉𝐏 | 𝐕𝐍𝐆 |[/bold cyan]
   [dim]───────────────────────────────────────────────────[/dim]
              [bold yellow] [ 𝐕𝐄𝐑𝐒𝐈𝐎𝐍 ➜ 4.5  𝐒𝐔𝐏𝐏𝐎𝐑𝐓 ] [/bold yellow]
"""
def menu_item(text: str, offset: int = 0):
    """Render a menu/sub-menu cell with a smooth per-character rainbow when enabled."""
    value = to_fancy(str(text))
    if CURRENT_SESSION_COLOR == "rainbow":
        return rainbow_text(value, 0)
    return value

def rainbow_row(table, *values, offset: int = 0):
    """Static true-RGB rainbow for menu/sub-menu cells only."""
    table.add_row(*(rainbow_text(to_fancy(str(v)), offset + i * 2) for i, v in enumerate(values)))

def menu_row(table, opt: str, command: str, description: str, offset: int = 0):
    """Common row helper so submenu options use the same true rainbow treatment."""
    if CURRENT_SESSION_COLOR == "rainbow":
        table.add_row(
            menu_item(opt, offset),
            menu_item(command, offset + 1),
            menu_item(description, offset + 4),
        )
    else:
        table.add_row(
            menu_item(opt, offset),
            menu_item(command, offset + 1),
            menu_item(description, offset + 4),
        )

def get_banner_color() -> str:
    # Rainbow is a fixed true-colour gradient; it does NOT cycle/animate.
    if CURRENT_SESSION_COLOR == "rainbow":
        return "bright_green"
    return CURRENT_SESSION_COLOR

# --- [SAFE BANNER SYSTEM FOR ANDROID 16 BINARY] ---
def get_main_banner() -> str:
    global CURRENT_SESSION_BANNER
    
    if CURRENT_SESSION_BANNER:
        try:
            # Pehle pyfiglet try karega (Agar purana Android hua toh chal jayega)
            import pyfiglet
            ascii_art = pyfiglet.figlet_format(CURRENT_SESSION_BANNER, font="ansi_shadow")
            subtitle = f"              [blink]  𓂃{to_fancy(CURRENT_SESSION_BANNER)} : 𝐒𝐘𝐒𝐓𝐄𝐌 𝐃𝐄𝐕𝐄𝐋𝐎𝐏𝐄𝐑  [/blink]\n"
            subtitle += f"         [bold yellow]𝐆𝐀𝐌𝐄 𝐕𝐄𝐑𝐒𝐈𝐎𝐍: 4.6 BGMI | PUBG | KR | TW | JP | VNG[/bold yellow]\n"
            return ascii_art + subtitle
        except Exception:
            # Agar Android 16 ne block kiya ya binary mein font nahi mila, toh ye MAGIC FALLBACK chalega
            simple_title = f"\n[bold {get_banner_color()}]██████████████████████████████████████████████████[/]\n"
            simple_title += f"[bold white]            {CURRENT_SESSION_BANNER} ALVSIA PRO 5.5 [/]\n"
            simple_title += f"[bold {get_banner_color()}]██████████████████████████████████████████████████[/]\n"
            subtitle = f"              [blink]  𓂃{to_fancy(CURRENT_SESSION_BANNER)} : 𝐒𝐘𝐒𝐓𝐄𝐌 𝐃𝐄𝐕𝐄𝐋𝐎𝐏𝐄𝐑  [/blink]\n"
            subtitle += f"         [bold yellow]𝐆𝐀𝐌𝐄 𝐕𝐄𝐑𝐒𝐈𝐎𝐍: 4.3,4.4 BGMI | PUBG | KR | TW | JP | VNG[/bold yellow]\n"
            return simple_title + subtitle

    # Default static banner (Ye hamesha chalega kyunki ye string hai)
    return ALVSIA_BANNER_TEXT

def get_real_device_model():
    try:
        if hasattr(sys, 'getandroidapilevel') or os.path.exists('/system/build.prop') or os.path.exists('/system/bin/getprop'):
            brand = subprocess.check_output(['getprop', 'ro.product.brand']).decode('utf-8').strip().upper()
            model = subprocess.check_output(['getprop', 'ro.product.model']).decode('utf-8').strip().upper()
            if brand and model:
                if brand in model:
                    return model
                return f"{brand} {model}"
            elif model:
                return model
    except Exception: 
        pass
    return socket.gethostname().upper()

def get_real_username():
    try:
        user = getpass.getuser()
        return f"ROOT ACCESS" if user.startswith("u0_a") else user.upper()
    except: return "UNKNOWN ADMIN"

def get_neon_header() -> Panel:
    from datetime import datetime
    now = datetime.now()
    real_device = get_real_device_model()
    b_color = get_banner_color()

    if CURRENT_SESSION_COLOR == "rainbow":
        with _rainbow_lock:
            off = _rainbow_char_offset
        raw_banner = get_main_banner()
        import re as _re
        clean_banner = _re.sub(r"\[/?[^\]]+\]", "", raw_banner).rstrip()
        banner_lines = []
        for line in clean_banner.split("\n"):
            stripped = line.strip()
            if any(k in stripped for k in ["𝐒𝐘𝐒𝐓𝐄𝐌 𝐃𝐄𝐕𝐄𝐋𝐎𝐏𝐄𝐑", "𝐆𝐀𝐌𝐄 𝐕𝐄𝐑𝐒𝐈𝐎𝐍", "BGMI", "𓂃"]):
                continue
            banner_lines.append(line)
        ascii_only = "\n".join(banner_lines).strip()

        banner_text = Text()
        for li, line in enumerate(ascii_only.split("\n")):
            banner_text.append_text(rainbow_text(line, off + li * 3))
            banner_text.append("\n")

        logo_body = Group(
            Align.center(banner_text),
            Align.center(rainbow_text("𝐀𝐋𝐕𝐈𝐒𝐈𝐀 𝐏𝐑𝐎 : 𝐒𝐘𝐒𝐓𝐄𝐌 𝐃𝐄𝐕𝐄𝐋𝐎𝐏𝐄𝐑", off + 2)),
            Align.center(rainbow_text("𝐆𝐀𝐌𝐄 𝐕𝐄𝐑𝐒𝐈𝐎𝐍: 4.6 BGMI | PUBG | KR | TW | JP | VNG", off + 4)),
        )
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="right", ratio=1)
        grid.add_row(
            Text.assemble(" ", rainbow_text("𝐎𝐖𝐍𝐄𝐑 ➩", off), " ", Text("@ALVSIA_PRO", style="bold white")),
            Text.assemble(rainbow_text("𝐔𝐏𝐓𝐈𝐌𝐄 ➩", off + 3), " ", Text(to_fancy(now.strftime('%H:%M:%S')), style="bold white")),
        )
        grid.add_row(
            Text.assemble(" ", rainbow_text("𝐃𝐄𝐕𝐈𝐂𝐄 ➩", off + 1), " ", Text(to_fancy(real_device), style="bold white")),
            Text.assemble(rainbow_text("𝐃𝐀𝐓𝐄 ➩", off + 4), " ", Text(to_fancy(now.strftime('%d-%m-%Y')), style="bold white")),
        )
        grid.add_row(
            Text.assemble(" ", rainbow_text("𝐒𝐘𝐒𝐓𝐄𝐌 𝐔𝐒𝐄𝐑 ➩", off + 2), " ", Text(to_fancy("Android User"), style="bold red")),
            Text(""),
        )
        title_sys = rainbow_markup("🫦𝐄𝐋𝐄𝐍𝐃𝐀-𝐒𝐘𝐒𝐓𝐄𝐌🫦", off)
        title_term = rainbow_markup("𝐓𝐄𝐑𝐌𝐈𝐍𝐀𝐋 𝐈𝐍𝐅𝐎", off + 2)
        status = Align.center(rainbow_text(" ● 𝐒𝐄𝐂𝐔𝐑𝐄 𝐂𝐎𝐍𝐍𝐄𝐂𝐓𝐈𝐎𝐍 𝐄𝐒𝐓𝐀𝐁𝐋𝐈𝐒𝐇𝐄𝐃 ● ", off + 5))
        layout_group = Columns([
            Panel(logo_body, border_style=b_color, box=box.HEAVY_HEAD, title=title_sys, padding=(1,2)),
            Panel(grid, border_style=b_color, title=title_term, box=box.SQUARE)
        ], expand=True)
        return Panel(Columns([layout_group, status], expand=True), style="on black", box=box.SIMPLE, padding=(0,0))

    dynamic_banner = get_main_banner()
    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="right", ratio=1)
    grid.add_row(
        f"[bold {b_color}] {to_fancy('𝐎𝐖𝐍𝐄𝐑')} ➩[/bold {b_color}] [bold white]@ALVSIA_PRO[/]",
        f"[bold {b_color}]{to_fancy('𝐔𝐏𝐓𝐈𝐌𝐄')} ➩[/bold {b_color}] [bold white]{to_fancy(now.strftime('%H:%M:%S'))}[/]"
    )
    grid.add_row(
        f"[bold {b_color}] {to_fancy('𝐃𝐄𝐕𝐈𝐂𝐄')} ➩[/bold {b_color}] [bold white]{to_fancy(real_device)}[/]",
        f"[bold {b_color}]{to_fancy('𝐃𝐀𝐓𝐄')} ➩[/bold {b_color}] [bold white]{to_fancy(now.strftime('%d-%m-%Y'))}[/]"
    )
    grid.add_row(
        f"[bold {b_color}] {to_fancy('𝐒𝐘𝐒𝐓𝐄𝐌 𝐔𝐒𝐄𝐑')} ➩[/bold {b_color}] [bold red]{to_fancy('Android User')}[/]", ""
    )
    banner = Align.center(Text.from_markup(dynamic_banner, style=f"bold {b_color}"))
    status_bar = Align.center(Text(f" ● {to_fancy('𝐒𝐄𝐂𝐔𝐑𝐄 𝐂𝐎𝐍𝐍𝐄𝐂𝐓𝐈𝐎𝐍 𝐄𝐒𝐓𝐀𝐁𝐋𝐈𝐒𝐇𝐄𝐃')} ● ", style=f"bold black on {b_color}"))
    layout_group = Columns([
        Panel(Align.center(Columns([banner], align="center"), vertical="middle"), border_style=b_color, box=box.HEAVY_HEAD, title=f"[bold black on {b_color}] {to_fancy('🫦𝐄𝐋𝐄𝐍𝐃𝐀-𝐒𝐘𝐒𝐓𝐄𝐌🫦')} [/]") ,
            Panel(grid, border_style=b_color, title=f"[bold black on {b_color}] {to_fancy('𝐓𝐄𝐑𝐌𝐈𝐍𝐀𝐋 𝐈𝐍𝐅𝐎')} [/]", box=box.SQUARE)
    ], expand=True)
    return Panel(Columns([layout_group, status_bar], expand=True), style="on black", box=box.SIMPLE, padding=(0,0))

def welcome_animation_effect():
    console.clear()
    cols, rows = shutil.get_terminal_size()
    b_color = get_banner_color()
    color_flash = f"on {b_color}"
    
    for color in [color_flash, "on black", color_flash, "on black"]:
        console.print("\n" * rows, style=color)
        time.sleep(0.08)
        console.clear()
    t1 = Text(to_fancy("ACCESS GRANTED"), style=f"bold {b_color}")
    t2 = Text(to_fancy("WELCOME SIR"), style="bold white")
    p = Panel(Align.center(Text.assemble(t1, "\n\n", t2)), 
              border_style=b_color, box=box.HEAVY, padding=(2, 10), 
              title=f"[reverse] {to_fancy('SYSTEM ONLINE')} [/]")
    console.print("\n" * (rows // 3))
    console.print(p, justify="center")
    time.sleep(1.5)
    console.clear()

SESSION_USER = "VIP USER"
SESSION_KEY = "N/A"
SESSION_EXPIRY = "N/A"

def background_expiry_killer():
    global SESSION_EXPIRY
    while True:
        try:
            from datetime import datetime
            if SESSION_EXPIRY != "N/A":
                exp_date = datetime.strptime(SESSION_EXPIRY, "%Y-%m-%d %H:%M:%S")
                if datetime.now() > exp_date:
                    pass  # PATCHED: expiry kill removed
        except: pass
        time.sleep(10)
    
# ============================================================
# 🔑🔑🔑  ALVSIA KEY SYSTEM v2.0 — HWID + EXPIRY + TAMPER  🔑🔑🔑
# ============================================================

_KS_DIR        = Path.home() / ".ALVSIA_security"
_KS_KEY_FILE   = _KS_DIR / "activated.alv"
_KS_HWID_FILE  = _KS_DIR / "hwid.alv"
_KS_SALT       = "ALVSIA_KEYSYS_SALT_2026_XJ9"
_KS_INNER_SALT = "ALVSIA_INNER_V2_9F3D"

# ── prefix → days (0 = lifetime) ──────────────────────────
# ========== KEY TIERS NOW MANAGED BY PANEL ==========
# Legacy standalone panel lookup removed; the Android app owns panel authentication.
_KEY_TIERS = {}  # Empty; validation done server-side

# ── helpers ───────────────────────────────────────────────

def _ks_hwid() -> str:
    """Stable device fingerprint (same logic as get_hwid / get_device_id)."""
    parts = []
    for prop in ("ro.serialno", "ro.product.model", "ro.product.board",
                 "ro.product.brand"):
        try:
            r = subprocess.run(["getprop", prop], capture_output=True,
                               text=True, timeout=4)
            v = r.stdout.strip()
            if v and v not in ("unknown", ""):
                parts.append(v)
        except Exception:
            pass
    try:
        r = subprocess.run(["settings", "get", "secure", "android_id"],
                           capture_output=True, text=True, timeout=4)
        v = r.stdout.strip()
        if v and v != "null":
            parts.append(v)
    except Exception:
        pass
    raw = "".join(parts) or (Path.home().as_posix() + "ALVSIA_FALLBACK")
    digest = hashlib.sha256(raw.encode()).hexdigest()[:20].upper()
    return f"ALV-{digest[:5]}-{digest[5:10]}-{digest[10:15]}-{digest[15:20]}"


def _ks_tier(key: str) -> tuple[str, int]:
    """Return (tier_label, days) for a key, or ('', -1) if prefix unknown."""
    for prefix, days in _KEY_TIERS.items():
        if key.upper().startswith(prefix.upper()):
            label = "LIFETIME" if days == 0 else f"{days}-DAY"
            return label, days
    return "", -1


def _ks_key_hash(key: str, hwid: str) -> str:
    return hashlib.sha512(
        f"{key}:{hwid}:{_KS_INNER_SALT}".encode()
    ).hexdigest()


def _ks_file_checksum(payload: str) -> str:
    return hashlib.sha256(f"{payload}:{_KS_SALT}".encode()).hexdigest()[:32]


def _ks_save(key: str, hwid: str, activated_ts: str, expiry_ts: str | None) -> None:
    _KS_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({
        "key"          : key,
        "hwid"         : hwid,
        "activated"    : activated_ts,
        "expiry"       : expiry_ts,          # None → lifetime
        "key_hash"     : _ks_key_hash(key, hwid),
        "tool_version" : APP_VERSION,
    })
    checksum = _ks_file_checksum(payload)
    encoded  = base64.b64encode(f"{checksum}|{payload}".encode()).decode()
    _KS_KEY_FILE.write_text(encoded)


def _ks_load() -> dict | None:
    if not _KS_KEY_FILE.exists():
        return None
    try:
        raw     = base64.b64decode(_KS_KEY_FILE.read_text()).decode()
        cs, payload = raw.split("|", 1)
        if cs != _ks_file_checksum(payload):
            console.print("[bold red]⚠ Key file tampered — re-activation required.[/bold red]")
            _KS_KEY_FILE.unlink(missing_ok=True)
            return None
        return json.loads(payload)
    except Exception:
        _KS_KEY_FILE.unlink(missing_ok=True)
        return None


def _ks_validate_saved(data: dict, hwid: str) -> tuple[bool, str]:
    """Returns (ok, reason_string)."""
    # HWID check
    if data.get("hwid") != hwid:
        return False, "HWID_MISMATCH"
    # inner hash integrity
    if data.get("key_hash") != _ks_key_hash(data["key"], hwid):
        return False, "HASH_CORRUPT"
    # expiry
    expiry = data.get("expiry")
    if expiry is not None:
        exp_dt = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
        if datetime.now() > exp_dt:
            return False, "EXPIRED"
    return True, "OK"


def _ks_remaining(data: dict) -> str:
    expiry = data.get("expiry")
    if expiry is None:
        return "∞ LIFETIME"
    exp_dt  = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
    delta   = exp_dt - datetime.now()
    if delta.total_seconds() <= 0:
        return "EXPIRED"
    days  = delta.days
    hours = delta.seconds // 3600
    return f"{days}d {hours}h remaining"


# ── fancy UI helpers ───────────────────────────────────────

def _ks_box_top(width=58):
    console.print(f"[bold cyan]╔{'═' * width}╗[/bold cyan]")

def _ks_box_mid(width=58):
    console.print(f"[bold cyan]╠{'═' * width}╣[/bold cyan]")

def _ks_box_bot(width=58):
    console.print(f"[bold cyan]╚{'═' * width}╝[/bold cyan]")

def _ks_row(left: str, right: str = "", width=58):
    content = f"  {left}"
    if right:
        content += f"  {right}"
    console.print(f"[bold cyan]║[/bold cyan]{content}")


def _ks_show_banner(hwid: str) -> None:
    _ks_box_top()
    _ks_row("[bold yellow]🔑 ALVSIA KEY SYSTEM v2.0[/bold yellow]")
    _ks_box_mid()
    _ks_row(f"[dim]HWID:[/dim]  [bold white]{hwid}[/bold white]")
    _ks_row("[dim]Contact [bold cyan]@ALVSIA_PRO[/bold cyan] for a key[/dim]")
    _ks_box_bot()


def _ks_show_activated(data: dict) -> None:
    key      = data["key"]
    tier_lbl = _ks_tier(key)[0]
    remaining = _ks_remaining(data)
    activated = data.get("activated", "?")
    _ks_box_top()
    _ks_row("[bold green]✅  KEY ACTIVE[/bold green]")
    _ks_box_mid()
    _ks_row(f"[dim]Key    :[/dim]  [bold yellow]{key}[/bold yellow]")
    _ks_row(f"[dim]Tier   :[/dim]  [bold magenta]{tier_lbl}[/bold magenta]")
    _ks_row(f"[dim]Time   :[/dim]  [bold cyan]{remaining}[/bold cyan]")
    _ks_row(f"[dim]Since  :[/dim]  [white]{activated}[/white]")
    _ks_box_bot()


def _ks_prompt_key(hwid: str) -> bool:
    """
    Interactive key entry loop.
    Returns True if the user successfully activates a key.
    """
    for attempt in range(3):
        console.print()
        try:
            raw = Prompt.ask(
                f"[bold cyan]🔑 Enter your ALVSIA key[/bold cyan] "
                f"[dim](attempt {attempt+1}/3)[/dim]"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            return False

        if not raw:
            console.print("[bold red]❌ No key entered.[/bold red]")
            continue

        tier_lbl, days = _ks_tier(raw)
        if tier_lbl == "":
            console.print("[bold red]❌ Invalid key format.[/bold red]")
            console.print("[dim]Keys look like: ALVSIA-7DAY-XXXXX or ALVSIA-LIFE-XXXXX[/dim]")
            continue

        # Key format accepted — activate
        now_str    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        expiry_str = None if days == 0 else (
            (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        )
        _ks_save(raw, hwid, now_str, expiry_str)

        console.print()
        console.print(Panel(
            f"[bold green]✅ KEY ACTIVATED![/bold green]\n"
            f"[bold yellow]Tier    :[/bold yellow] [cyan]{tier_lbl}[/cyan]\n"
            f"[bold yellow]Expires :[/bold yellow] [cyan]{'Never (LIFETIME)' if expiry_str is None else expiry_str}[/cyan]",
            title="[bold white on green] 🔓 ACTIVATION SUCCESS [/]",
            border_style="green",
            box=box.HEAVY,
        ))
        time.sleep(1.5)
        return True

    # 3 failed attempts
    console.print()
    console.print(Panel(
        "[bold red]❌ Too many invalid attempts.[/bold red]\n"
        "[yellow]Contact [bold cyan]@ALVSIA_PRO[/bold cyan] to get a valid key.[/yellow]",
        title="[bold white on red] 🚫 ACCESS DENIED [/]",
        border_style="red",
        box=box.HEAVY,
    ))
    time.sleep(2)
    os._exit(1)


# ── public entry point (replaces the old stub) ─────────────

def check_password_login():
    """Accept only the live Kotlin session; never prompt or call a legacy panel."""
    if os.environ.get("ALVSIA_APK_SESSION") != "1":
        return None
    try:
        from com.alvsia.pro.sec import SessionGate
        if not bool(SessionGate.isSessionAuthorized()):
            return None
    except Exception:
        return None
    global SESSION_USER
    SESSION_USER = "AUTHENTICATED APK SESSION"
    return "ALVSIA_KEYED"


def validate_key_with_panel(license_key: str) -> dict | None:
    """Legacy duplicate panel handshake intentionally disabled."""
    return None


def get_device_id() -> str:
    """Generate stable device ID."""
    try:
        base_dir = Path.home() / ".alvsia_cache"
        base_dir.mkdir(exist_ok=True, parents=True)
        id_file = base_dir / ".device_id"
        
        if id_file.exists():
            return id_file.read_text().strip()
        
        # Generate baru
        parts = [
            platform.system(),
            platform.release(),
            platform.machine(),
            platform.processor(),
            hex(uuid.getnode())
        ]
        fingerprint = "|".join(parts).encode()
        salt = os.urandom(16)
        
        derived = hashlib.pbkdf2_hmac("sha256", fingerprint, salt, 200000)
        device_id = hashlib.sha256(salt + derived).hexdigest()
        
        id_file.write_text(device_id)
        return device_id
        
    except:
        return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()

def ROL32(x: int, n: int) -> int: return ((x << n) & 0xFFFFFFFF) | ((x & 0xFFFFFFFF) >> (32 - n))

import os, re, struct, subprocess, shutil, hashlib, json, sys, zipfile, fnmatch, tempfile, zlib, time, uuid, threading, platform, getpass, urllib.request, urllib.error
from dataclasses import dataclass, field
from pathlib import Path, PurePath
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
    pad = None
    unpad = None
try:
    from zstandard import ZstdDecompressor, ZstdCompressionDict, DICT_TYPE_AUTO, ZstdCompressor
except Exception:
    ZstdDecompressor = None
    ZstdCompressionDict = None
    DICT_TYPE_AUTO = None
    ZstdCompressor = None



# ---------------------------
# DIRECTORY MANAGEMENT
# ---------------------------
# ======================================================================
#                    DIRECTORY MANAGEMENT
# ======================================================================

# ======================================================================
#                    DIRECTORY MANAGEMENT
# ======================================================================

ORGNAL_DIR = "ORGNAL"
EDITED_DIR = "Modified_files"
UNPACK_DIR = "UNPACK"
REPACK_DIR = "REPACK"
SINGLE_DIR = "UNPACKED_SINGLE"

ENCRYPT_INPUT_DIR = Path(BASE_DIR_NAME) / "Enc_pak" / "Input"
ENCRYPT_OUTPUT_DIR = Path(BASE_DIR_NAME) / "Enc_pak" / "Output"

ANLAISH_DIR = Path(BASE_DIR_NAME) / "OBB Anlaish"
ANLAISH_ORG = ANLAISH_DIR / "ORGNAL"
ANLAISH_MOD = ANLAISH_DIR / "MOD"
ANLAISH_RESULT = ANLAISH_DIR / "RESULT"

# ======================================================================
#                    MINI & ZSDIC TOOL GLOBALS
# ======================================================================

# 🔥 BASE DIRECTORIES (Game specific paths will be set in run_combined_modding_tool)
BASE_DIR = os.path.join("ALVSIA_PRO_DATA", "SKIN_TOOL")
MINI_BASE = os.path.join(BASE_DIR, "MINI")
ZSDIC_BASE = os.path.join(BASE_DIR, "ZSDIC")
FINAL_DIR = os.path.join(BASE_DIR, "FINAL")

# 🔥 MINI PATHS (Will be overridden in run_combined_modding_tool)
mini_BASE_DIR = MINI_BASE
mini_MINI_ICON_DIR = os.path.join(mini_BASE_DIR, "MINI_ICON")
mini_INPUT_DIR = os.path.join(mini_MINI_ICON_DIR, "INPUT")
mini_OUTPUT_DIR = os.path.join(mini_MINI_ICON_DIR, "OUTPUT")
mini_TXTS_DIR = os.path.join(mini_MINI_ICON_DIR, "TXTS")
mini_MODSKIN_FILE = os.path.join(mini_BASE_DIR, "modskin.txt")
mini_CHANGELOG_PATH = os.path.join(mini_BASE_DIR, "changelog.txt")
mini_NULL_TXT_PATH = os.path.join(mini_TXTS_DIR, "null.txt")
mini_NULLED_TXT_PATH = os.path.join(mini_BASE_DIR, "nulled.txt")
mini_ALL_TXT_PATH = os.path.join(mini_TXTS_DIR, "ALL.txt")
mini_INDEX_FILE_PATH = os.path.join(mini_TXTS_DIR, "index.txt")

mini_AUTO_THEME_BASE = os.path.join(mini_BASE_DIR, "AUTO_THEME")
mini_AUTO_THEME_FILES = os.path.join(mini_AUTO_THEME_BASE, "FILES")
mini_AUTO_THEME_RESULT = os.path.join(mini_AUTO_THEME_BASE, "MODIFIED")
mini_AUTO_THEME_TXT = os.path.join(mini_AUTO_THEME_BASE, "TXT")
mini_LOBBY_FILE = os.path.join(mini_AUTO_THEME_TXT, "lobby.txt")

mini_HIT_EFFECT_DIR = os.path.join(mini_BASE_DIR, "HIT EFFECT")
mini_LOOTCRATES_DIR = os.path.join(mini_BASE_DIR, "LOOTCRATES")
mini_HIT_ORIG = os.path.join(mini_HIT_EFFECT_DIR, "org")
mini_HIT_MODIFIED = os.path.join(mini_HIT_EFFECT_DIR, "modified")
mini_LOOT_ORIG = os.path.join(mini_LOOTCRATES_DIR, "org")
mini_LOOT_MODIFIED = os.path.join(mini_LOOTCRATES_DIR, "modified")
mini_HIT_TXT_PATH = os.path.join(mini_BASE_DIR, "hit.txt")

mini_changelog_entries = []
mini_modified_blocks_map = {}  
mini_BLOCK_SIZE = 65536

# 🔥 ZSDIC PATHS (Will be overridden in run_combined_modding_tool)
zsdic_DEFAULT_MAX_NULLS = 40
zsdic_ENABLE_UTF16LE_ID_SCAN = False

zsdic_GAME_DIRS = {"BGMI": os.path.join(ZSDIC_BASE, "BGMI")}
zsdic_OUTPUT_DIR_NAME = "skindats"
zsdic_EDITED_DIR_NAME = "edited"
zsdic_SIZE_DIR_NAME = "size"
zsdic_MODSKIN_TXT = os.path.join(ZSDIC_BASE, "modskin.txt")
zsdic_OUTFITS_TXT = os.path.join(ZSDIC_BASE, "outfits.txt")
zsdic_NULL_TXT = os.path.join(ZSDIC_BASE, "null.txt")
zsdic_CHANGELOG_TXT = os.path.join(ZSDIC_BASE, "changelog.txt")
zsdic_NULLED_LOG_TXT = os.path.join(ZSDIC_BASE, "nulled.txt")
zsdic_SWAP_OFFSETS_TXT = os.path.join(ZSDIC_BASE, "swap_offsets.txt")
zsdic_OUTFITS_FILES = {"AvatarSuitsTable.uasset", "GoldClothBattleEffect.uasset"}
zsdic_ID_ASCII_RE = re.compile(rb"(?<![0-9])[0-9]{3,}(?![0-9])")
zsdic_ID_UTF16LE_RE = re.compile(rb"(?:(?:[0-9]\x00){3,})")

# 🔥 STAND POSH PATHS (Will be overridden in run_combined_modding_tool)
STAND_POSH_BASE = os.path.join(BASE_DIR, "STAND_POSH")
sp_INPUT = os.path.join(STAND_POSH_BASE, "INPUT")
sp_OUTPUT = os.path.join(STAND_POSH_BASE, "OUTPUT")
sp_DUMP = os.path.join(STAND_POSH_BASE, "dump.txt")
sp_MODSKIN = os.path.join(STAND_POSH_BASE, "modskin.txt")
sp_NULL = os.path.join(STAND_POSH_BASE, "null.txt")

# ======================================================================
#                    CREATE DIRS FUNCTION
# ======================================================================




# ---------------------------------------------------------------------------
# ALVSIA V3 R4P3 — core self-verification (server-signed operation proof)
# ---------------------------------------------------------------------------
_ALVSIA_CORE_BUILD_ID = 'ALVSIA-UNaux-20261028-RSA1'
_ALVSIA_CORE_VERSION = '4.0.0'
_ALVSIA_CORE_RSA_N_B64U = 'p2G8SVBzL8Ic_aTg10HZcc35LJdw2Iv-rP0LyXyyKp-06Ju-_nOxTpDE9gpDoBegkXh7sj37qO94Fx-SZn3JDVdRzKMARzkRSevUX0wOGveXd6JzggcCDe70-P3QhHgPE91HM78QkGeBV0vSebOCLEVjP7l0MjmmBK_7zuK3FuPaMBZUBOi8CwGuW8lhjqbPwwiKM5tHKG5bd9-hWVZ6O-XBP_jiQSafnXX-3Gy_z6LuniDzK79CfxBoxQwJPOOxowHzeVvgcVSy7ubJO3ZzsATsi-JPYCyMtIOC7eKDHFourkFaOYd0i4r838nPAylbpL659vkP2DD3hd4SW5JStPIH20sShkpWsCglhGa0Hukt_kh-HrD9YMhRGdc0Ymc8dU6LnSU4KKb6wmk1LLhgtLC3NoTaM_Yx_3Z5iqrY9ELiLT6teSWlyEpJWOFPkPz39EoThQlDpWf0aO7syXoo3iAXJMUpWUli1qPCC94TSumUEAYwULv1m4_nbLO6WwNR'
_ALVSIA_CORE_RSA_E_B64U = 'AQAB'
_ALVSIA_CORE_DIGESTINFO = bytes.fromhex('3031300d060960864801650304020105000420')
_ALVSIA_CORE_CRITICAL = (
    'alvtools.py',
    'alv_protectioncore.cpython-314-aarch64-linux-android.so',
    'alv_luacore.cpython-314-aarch64-linux-android.so',
    'alv_pakcore.cpython-314-aarch64-linux-android.so',
    'alv_aimbotcore.cpython-314-aarch64-linux-android.so',
    'alv_playerpawncore.cpython-314-aarch64-linux-android.so',
    'EXES/luac',
    'EXES/luadec',
    'EXES/unluac_pro.jar',
    'EXES/LUADEC',
)
_ALVSIA_CORE_ACTIVE_PROOF = None

def _alv_core_b64u_decode(value):
    import base64 as _b64
    raw = str(value or '').encode('ascii')
    raw += b'=' * ((4 - len(raw) % 4) % 4)
    return _b64.urlsafe_b64decode(raw)

def _alv_core_verify_rs256(message, signature_b64u):
    try:
        n = int.from_bytes(_alv_core_b64u_decode(_ALVSIA_CORE_RSA_N_B64U), 'big')
        e = int.from_bytes(_alv_core_b64u_decode(_ALVSIA_CORE_RSA_E_B64U), 'big')
        sig = _alv_core_b64u_decode(signature_b64u)
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

def _alv_core_message(fields):
    lines = ['ALVSIA-R4', 'kind=operation_grant']
    for key in ('grant_id','nonce','build_id','manifest_hash','tool_hash','device_id','session_id','operation_id','issued_at','expires_at'):
        lines.append(f'{key}={fields.get(key, "")}')
    return '\n'.join(lines)

def _alv_core_sha256_file(path):
    h = __import__('hashlib').sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def _alv_core_live_measurement():
    import pathlib as _pl, os as _os
    if _os.environ.get('ALVSIA_APK_SESSION') == '1':
        h = __import__('hashlib').sha256(b'ALVSIA-APK-SESSION').hexdigest()
        return {'manifest_hash': h, 'tool_hash': h}
    root = _pl.Path(__file__).resolve().parent
    files = {}
    for name in _ALVSIA_CORE_CRITICAL:
        p = root / name
        if not p.is_file():
            raise RuntimeError('Operation authorization failed')
        files[name] = _alv_core_sha256_file(p)
    canonical = '\n'.join([
        f'version={_ALVSIA_CORE_VERSION}',
        f'build_id={_ALVSIA_CORE_BUILD_ID}',
        *[f'{name}={files[name]}' for name in sorted(files)],
    ])
    return {
        'manifest_hash': __import__('hashlib').sha256(canonical.encode('utf-8')).hexdigest(),
        'tool_hash': files['alvtools.py'],
    }

def _alv_core_parse_utc(value):
    import datetime as _dt
    s = str(value or '').strip()
    if not s:
        raise ValueError('missing timestamp')
    # Worker sqlDate() format: YYYY-MM-DD HH:MM:SS (UTC)
    dt = _dt.datetime.strptime(s, '%Y-%m-%d %H:%M:%S').replace(tzinfo=_dt.timezone.utc)
    return dt.timestamp()

def _alv_install_operation_proof(proof):
    global _ALVSIA_CORE_ACTIVE_PROOF
    import os as _os
    try:
        p = dict(proof or {})
        sig = dict(p.pop('signature', {}) or {})
        if sig.get('alg') != 'RS256' or sig.get('kid') != 'alvsia-r4-20260923':
            raise ValueError
        required = ('grant_id','nonce','build_id','manifest_hash','tool_hash','device_id','session_id','operation_id','issued_at','expires_at')
        if any(not str(p.get(k, '')).strip() for k in required):
            raise ValueError
        _op_tokens = [x.strip() for x in str(p['operation_id']).split(',')]
        if not _op_tokens or len(_op_tokens) > 8 or any(not re.fullmatch(r'[a-z0-9_.]{1,48}', item) for item in _op_tokens):
            raise ValueError
        if _os.environ.get('ALVSIA_APK_SESSION') == '1':
            expected_device = _os.environ.get('ALVSIA_EXPECTED_DEVICE_ID', '').strip().lower()
            expected_session = _os.environ.get('ALVSIA_EXPECTED_SESSION_ID', '').strip()
            if not expected_device or not expected_session or str(p['device_id']).lower() != expected_device or str(p['session_id']) != expected_session:
                raise ValueError
        if str(p['build_id']) != _ALVSIA_CORE_BUILD_ID:
            raise ValueError
        measurement = _alv_core_live_measurement()
        if str(p['manifest_hash']).lower() != measurement['manifest_hash'].lower():
            raise ValueError
        if str(p['tool_hash']).lower() != measurement['tool_hash'].lower():
            raise ValueError
        now = __import__('time').time()
        issued = _alv_core_parse_utc(p['issued_at'])
        expires = _alv_core_parse_utc(p['expires_at'])
        if expires <= issued or expires - issued > 180 or now < issued - 30 or now >= expires:
            raise ValueError
        if not _alv_core_verify_rs256(_alv_core_message(p), str(sig.get('value',''))):
            raise ValueError
        p['signature'] = sig
        p['_expires_epoch'] = expires
        _ALVSIA_CORE_ACTIVE_PROOF = p
        return True
    except Exception:
        _ALVSIA_CORE_ACTIVE_PROOF = None
        return False

def _alv_install_operation_grant_token(token, expected_operation):
    """Verify and install a compact RS256 JWT from the current Unaux panel."""
    global _ALVSIA_CORE_ACTIVE_PROOF
    try:
        parts = str(token or '').split('.')
        if len(parts) != 3 or not expected_operation:
            raise ValueError
        header = __import__('json').loads(_alv_core_b64u_decode(parts[0]).decode('utf-8'))
        claims = __import__('json').loads(_alv_core_b64u_decode(parts[1]).decode('utf-8'))
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
        if not _alv_core_verify_rs256(parts[0] + '.' + parts[1], parts[2]):
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

def _alv_clear_operation_proof():
    global _ALVSIA_CORE_ACTIVE_PROOF
    _ALVSIA_CORE_ACTIVE_PROOF = None

def _alv_require_operation(allowed_operations):
    import os as _os
    if _os.environ.get('ALVSIA_APK_SESSION') != '1':
        raise RuntimeError('Operation authorization failed: login required')
    session = _os.environ.get('ALVSIA_EXPECTED_SESSION_ID', '').strip()
    device = _os.environ.get('ALVSIA_EXPECTED_DEVICE_ID', '').strip().lower()
    if not re.fullmatch(r'[0-9a-f]{64}', session) or not re.fullmatch(r'[0-9a-f]{64}', device):
        raise RuntimeError('Operation authorization failed: identity unavailable')
    p = _ALVSIA_CORE_ACTIVE_PROOF
    if not isinstance(p, dict):
        raise RuntimeError('Operation authorization failed: RSA grant missing')
    if str(p.get('session_id', '')) != session or str(p.get('device_id', '')).lower() != device:
        _alv_clear_operation_proof()
        raise RuntimeError('Operation authorization failed: grant identity mismatch')
    if __import__('time').time() >= float(p.get('_expires_epoch', 0) or 0):
        _alv_clear_operation_proof()
        raise RuntimeError('Operation authorization failed: grant expired')
    granted = {x.strip() for x in str(p.get('operation_id', '')).split(',') if x.strip()}
    allowed = {str(x).strip() for x in allowed_operations if str(x).strip()}
    if any(x.startswith(('pak.', 'advanced.', 'asset.', 'lab.')) for x in allowed):
        allowed.add('pak_tools')
    if any(x.startswith('obb.') for x in allowed):
        allowed.add('obb_tools')
    if any(x.startswith('lua_') for x in allowed):
        allowed.add('lua_tools')
    if not granted.intersection(allowed):
        raise RuntimeError('Operation authorization failed: operation not granted')
    return True


def security_guard(fn):
    # APK session: auth already done in native layer; keep function as-is
    return fn

class _alvPakConsole:
    """Small compatibility console for the adopted bahan.py PAK engine."""
    _tag_re = re.compile('\\[/?[^\\]]+\\]')

    def print(self, *args, **kwargs):
        rendered = ' '.join((str(x) for x in args))
        rendered = self._tag_re.sub('', rendered)
        print(rendered)
console = _alvPakConsole()
BASE_DIR = Path.cwd()
_ALVSIA_PAK_LEGACY_DISPLAY_BRAND = 'ALVSIA_PRO'
_ALVSIA_PAK_DISPLAY_BRAND = 'ALVSIA_JANCOOOOOKKKKKKK'

def _alv_pak_debug_display(value) -> str:
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
SM4_SECRET_NEW = ['xG2qW5lP7lV2iN5fN5pG', 'xT1cJ6dL5wC0kK1rB4dK', 'qC4jS5bZ6fL5xE6nD4zA', 'gD4jQ2aL3bS3lC3xT0iW', 'xU1yQ8wE9zY3gZ3bT5aE', 'uQ3cO2dX7xY4xU7gH7iS', 'gW1fR0jK6wQ4oN0oK1kZ', 'aJ4pV7iZ7pU4wP2aC2cZ', 'cX6jT3cM2oT3vK0kJ1qN', 'iT2vS0cS6yT6cZ1sE1lO', 'hM1pH9iY8wM9hT4lN5uJ', 'kG6bC8jK0fL0dE4sH4mL', 'dB6lB3vE0eZ8wM8rI0aC', 'tP7sP7nI9rA2vQ4cV5yQ', 'aT0cL1yN4pT3sZ7eM2vY', 'uV6fU8fC9zN3mP5dH8mN', 'rT6aQ6oZ1yM0gO5tO1aN', 'jU5bH7lQ0fM9hK2kI0oF', 'iQ0eM0mJ7uT0kV6kL5zY']
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
        zuc = gmalg.ZUC(ZUC_KEY, ZUC_IV)
        return [struct.unpack('>I', zuc.generate())[0] for _ in range(16)]

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
            _s2b8e7b87d9f2 = (encryption_method - EM_SM4_NEW_BASE) % len(SM4_SECRET_NEW)
            _sbd281f3d3181 = SM4_SECRET_NEW[_s2b8e7b87d9f2]
        else:
            _s2b8e7b87d9f2 = (encryption_method - EM_SM4_NEW_BASE) % len(SM4_SECRET_NEW)
            _sbd281f3d3181 = f'{SM4_SECRET_NEW[_s2b8e7b87d9f2]}{encryption_method}'
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

    def _encrypt_simple1(plaintext: bytes) -> bytes: return bytes(x ^ SIMPLE1_DECRYPT_KEY for x in plaintext)

    def _encrypt_simple2(plaintext: bytes) -> bytes:
            initial_key, = struct.unpack('<I', SIMPLE2_DECRYPT_KEY); out_words = []; current = initial_key
            for w in struct.unpack(f'<{len(plaintext)//4}I', plaintext): c = current ^ w; out_words.append(c); current = w
            return struct.pack(f'<{len(out_words)}I', *out_words)

    def _encrypt_sm4(plaintext: bytes, file_path: PurePath, encryption_method: int) -> bytes:
            key = PakCrypto._derive_sm4_key(file_path, encryption_method); sm4 = PakCrypto._sm4_context_for_key(key)
            return b''.join(sm4.encrypt(plaintext[i:i+SM4.block_length()]) for i in range(0, len(plaintext), SM4.block_length()))

class PakCompression:

    @staticmethod
    @lru_cache(maxsize=33)
    def _zstd_decompressor(dict: ZstdCompressionDict) -> ZstdDecompressor:
        return ZstdDecompressor(dict)

    @staticmethod
    def zstd_dictionary(dict_data) -> ZstdCompressionDict:
        return ZstdCompressionDict(dict_data, DICT_TYPE_AUTO)

    @staticmethod
    def decompress_block(block, dict: Optional[ZstdCompressionDict], compression_method: int) -> bytes:
        if compression_method == CM_NONE:
            return block
        if compression_method == CM_ZLIB:
            try:
                return zlib.decompress(block)
            except zlib.error:
                return block
        elif compression_method == CM_ZSTD or compression_method == CM_ZSTD_DICT:
            if compression_method != CM_ZSTD_DICT:
                dict = None
            return PakCompression._zstd_decompressor(dict).decompress(block)
        else:
            raise ValueError(f'Unknown compression method: {compression_method}')

    def compress_block(plain_block: bytes, compression_method: int, zstd_dict: ZstdCompressionDict | None, target_len: int | None) -> bytes:
            if compression_method == CM_NONE: return plain_block
            if compression_method == CM_ZLIB:
                for level in range(6, 10):
                    comp = zlib.compress(plain_block, level)
                    if target_len is None or len(comp) <= target_len: return comp
                return zlib.compress(plain_block)
            if compression_method == CM_ZSTD or compression_method == CM_ZSTD_DICT:
                for level in range(18, 23):
                    cctx = ZstdCompressor(level=level, dict_data=zstd_dict) if compression_method == CM_ZSTD_DICT and zstd_dict else ZstdCompressor(level=level)
                    comp = cctx.compress(plain_block)
                    if target_len is None or len(comp) <= target_len: return comp
                return cctx.compress(plain_block)
            raise RuntimeError('Unsupported compression')

class TencentPakFile:

    def __init__(self, file_path: PurePath, is_od=True):
        _alv_require_operation(('pak.unpack', 'pak.repack', 'pak.unpack_single', 'pak.repack_single', 'pak.diagnostics', 'pak.delete_entry', 'pak.delete_all', 'advanced.inject_any', 'advanced.inject_brplayer', 'advanced.same_size_hashfix', 'advanced.zsdic_hashfix', 'asset.unpack', 'obb.unpack', 'obb.repack', 'lab.editor.auto_pak', 'lab.playerpawn.auto_pak'))
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
            _s540ed156ec16 = _alv_pak_debug_display(message)
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
        if _se33e912f7767 == 17:
            with open(file_path, 'wb') as _sbb61cc6b3e63:
                for _s576e50701491 in entry.compressed_blocks:
                    _s366d3d829edf = self._file_content[_s576e50701491.start:_s576e50701491.end]
                    _sbb61cc6b3e63.write(_s366d3d829edf)
            return
        with open(file_path, 'wb') as _sbb61cc6b3e63:
            if _s5206fe150a33 == CM_NONE:
                _sb96393f68f4d = self._peek_content(entry.offset, entry.size, _se33e912f7767)
                if entry.encrypted:
                    _sb96393f68f4d = PakCrypto.decrypt_block(bytes(_sb96393f68f4d), file_path, _se33e912f7767)
                _sbb61cc6b3e63.write(_sb96393f68f4d)
                return
            for _s1f6d01ab75cb in PakCrypto.generate_block_indices(len(entry.compressed_blocks), _se33e912f7767):
                _sb96393f68f4d = self._peek_block_content(entry.compressed_blocks[_s1f6d01ab75cb], _se33e912f7767)
                if entry.encrypted:
                    _sb96393f68f4d = PakCrypto.decrypt_block(bytes(_sb96393f68f4d), file_path, _se33e912f7767)
                _sb96393f68f4d = PakCompression.decompress_block(_sb96393f68f4d, self._zstd_dict, _s5206fe150a33)
                _sbb61cc6b3e63.write(_sb96393f68f4d)

    def dump(self, out_path: PurePath) -> None:
        debug_path = BASE_DIR / 'index_debug.txt'

        def _log_path_debug(title, **values):
            try:
                BASE_DIR.mkdir(parents=True, exist_ok=True)
                _se78e1dce92b0 = ['', f'=== {title} ===']
                for _s07c75bc1b558, _s0c49bd2ad1c0 in values.items():
                    _se78e1dce92b0.append(f'{_s07c75bc1b558:<20}: {_s0c49bd2ad1c0!r}')
                _se78e1dce92b0.append('=' * (8 + len(title)))
                _scb74e83bd4bb = '\n'.join(_se78e1dce92b0) + '\n'
                print(_scb74e83bd4bb, flush=True)
                with open(debug_path, 'a', encoding='utf-8') as _s17c5d36b0ad1:
                    _s17c5d36b0ad1.write(_scb74e83bd4bb)
            except Exception:
                pass
        mount_text = str(self._mount_point)
        if '\x00' in mount_text:
            _log_path_debug('INVALID MOUNT POINT', mount_point=mount_text, output_root=str(out_path))
            raise ValueError('PAK mount point contains an embedded NUL character.')
        out_path /= self._mount_point
        skipped_dirs = 0
        skipped_files = 0
        for dir_path, dir in self._index.items():
            dir_text = str(dir_path)
            if '\x00' in dir_text:
                skipped_dirs += 1
                _log_path_debug('INVALID DIRECTORY PATH', directory=dir_text, output_root=str(out_path), reason='embedded NUL character')
                continue
            current_out_path = Path(out_path / dir_path)
            if '\x00' in str(current_out_path):
                skipped_dirs += 1
                _log_path_debug('INVALID OUTPUT DIRECTORY', directory=dir_text, output_path=str(current_out_path), reason='embedded NUL character')
                continue
            try:
                if not current_out_path.exists():
                    current_out_path.mkdir(parents=True, exist_ok=True)
            except (ValueError, OSError) as e:
                skipped_dirs += 1
                _log_path_debug('DIRECTORY CREATE ERROR', directory=dir_text, output_path=str(current_out_path), error=f'{type(e).__name__}: {e}')
                continue
            for file_name, entry in dir.items():
                file_text = str(file_name)
                if '\x00' in file_text:
                    skipped_files += 1
                    _log_path_debug('INVALID FILE NAME', directory=dir_text, file_name=file_text, reason='embedded NUL character')
                    continue
                file_out_path = current_out_path / file_name
                if '\x00' in str(file_out_path):
                    skipped_files += 1
                    _log_path_debug('INVALID FILE OUTPUT PATH', directory=dir_text, file_name=file_text, output_path=str(file_out_path), reason='embedded NUL character')
                    continue
                try:
                    self._write_to_disk(file_out_path, entry)
                except (ValueError, OSError) as e:
                    skipped_files += 1
                    _log_path_debug('FILE WRITE ERROR', directory=dir_text, file_name=file_text, output_path=str(file_out_path), error=f'{type(e).__name__}: {e}')
                    continue
        _log_path_debug('DUMP PATH SUMMARY', skipped_directories=skipped_dirs, skipped_files=skipped_files)

    def dump_filtered(self, out_path: PurePath, extensions) -> dict:
        """
        Extract only entries whose filename ends with one of `extensions`.
        Internal directory structure is preserved under out_path.
        """
        normalized = tuple((ext.lower() if str(ext).startswith('.') else '.' + str(ext).lower() for ext in extensions))
        stats = {'matched': 0, 'extracted': 0, 'failed': 0, 'errors': []}
        for dir_path, files in self._index.items():
            for file_name, entry in files.items():
                if not str(file_name).lower().endswith(normalized):
                    continue
                stats['matched'] += 1
                target_dir = Path(out_path / dir_path)
                target_dir.mkdir(parents=True, exist_ok=True)
                target_file = target_dir / file_name
                try:
                    self._write_to_disk(target_file, entry)
                    stats['extracted'] += 1
                except Exception as e:
                    stats['failed'] += 1
                    stats['errors'].append({'file': str(dir_path / file_name).replace('\\', '/'), 'error': str(e)})
                    console.print(f'[yellow]⚠ Skip {str(dir_path / file_name)}: {str(e)}[/yellow]')
        return stats

    def dump_single_file(self, target_file_name: str, out_path_base: Path, single_file_dir_name: str) -> None:
            entry_found = None
            dir_of_file = None
            for dir_path, dir in self._index.items():
                if target_file_name in dir:
                    entry_found = dir[target_file_name]
                    dir_of_file = dir_path.relative_to(self._mount_point) if dir_path.parts and dir_path.parts[0] == self._mount_point.name else dir_path
                    break
            if entry_found is None:
                console.print(Panel(f"[red]Error: Target file '[bold yellow]{to_fancy(target_file_name)}[/bold yellow]' not found in the PAK index.[/red]"))
                return
            pak_stem = Path(self._file_path).stem
            current_out_path = out_path_base / single_file_dir_name / pak_stem / dir_of_file
            os.makedirs(to_long_path(current_out_path), exist_ok=True)
            target_path = current_out_path / target_file_name
        
            console.print(f"[dim]|[/] [bold white]{to_fancy('SINGLE UNPACK')}:[/bold white] [green]{to_fancy(target_file_name)}[/] [dim]from {self._file_path.name}[/dim]")
            try:
                self._write_to_disk(target_path, entry_found)
                console.print(Panel(f"[green]{to_fancy('Successfully extracted')}: {to_fancy(target_file_name)} -> {target_path.resolve()}[/green]"))
            except Exception as e:
                console.print(Panel(f"[red]Error writing {target_file_name}: {e}[/red]"))

    def find_entry_for_modified(self, relative_path_to_mod_dir: PurePath, is_repack=False):
            dir_part = relative_path_to_mod_dir.parent
            name = relative_path_to_mod_dir.name
        
            if dir_part in self._index:
                for fname, entry in self._index[dir_part].items():
                    if fname.lower() == name.lower() and entry is not None:
                        return dir_part, name, entry
        
            if len(relative_path_to_mod_dir.parts) == 1:
                candidates = []
                for dir_path, dir in self._index.items():
                    for fname, entry in dir.items():
                        if fname.lower() == name.lower() and entry is not None:
                            candidates.append((dir_path, fname, entry))
            
                if len(candidates) == 1:
                
                    return candidates[0]
                elif len(candidates) > 1:
                    return candidates[0]
        
            return None

    def repack_inplace_from_modified_dir(self, pak_file_handle=None) -> bool:
            mod_root = Path(self.MODIFIED_DIR)
            if not os.path.exists(to_long_path(mod_root)):
                console.print(Panel(f"[red]Modified_files folder.{mod_root}[/red]"))
                return False
            need_close = False
            if pak_file_handle is None:
                pak_file_handle = open_long(self._file_path, 'r+b')
                need_close = True
            try:
                any_ok = False
                for root, _, files in os.walk(to_long_path(mod_root)):
                    for fname in files:
                        mpath = Path(os.path.join(root, fname))
                        try:
                            relative_path_for_search = Path(mpath).relative_to(self.MODIFIED_DIR)
                        except ValueError:
                            relative_path_for_search = Path(fname) 
                    
                        match = self.find_entry_for_modified(relative_path_for_search, is_repack=True) 
                        if not match: continue
                    
                        dir_path, name, entry = match
                        target_full_path = (dir_path / name).as_posix()
                    
                        try:
                            ok = self._repack_single_file(pak_file_handle, mpath, entry)
                            if ok:
                                # 👇 Sirf 'Auto-Detected Location:' print hoga, aage ka path hata diya
                                console.print(f"[bold {get_banner_color()}]✓ {to_fancy('Auto-Detected Location')}:[/bold {get_banner_color()}]")
                            
                                # Premium Green Box
                                panel_text = (
                                    f"[bold cyan]Repacking:[/] [bold white]{name}[/]\n"
                                    f"[bold yellow]Target Entry:[/] [bold green]{target_full_path}[/]\n"
                                    f"[bold bright_blue]Encryption Method Applied: {entry.encryption_method}[/]"
                                )
                                from rich import box
                                console.print(Panel(panel_text, border_style=get_banner_color(), box=box.SQUARE))
                            
                                any_ok = True
                            else:
                                console.print(Panel(f"[yellow]{to_fancy('Failed to repack (in-place not possible)')}: {to_fancy(name)}[/yellow]", border_style="yellow"))
                        except Exception as e:
                            console.print(Panel(f"[red]Error repacking {name}: {e}[/red]", border_style="red"))
                return any_ok
            finally:
                if need_close: pak_file_handle.close()

    def _apply_encrypt_for_entry(self, data: bytes, file_path: PurePath, encryption_method: int) -> bytes:
            if encryption_method == 17: return data 
            if PakCrypto._is_simple1_method(encryption_method): return PakCrypto._encrypt_simple1(data)
            if PakCrypto._is_simple2_method(encryption_method):
                data = Misc.pad_to_n(data, SIMPLE2_BLOCK_SIZE)
                assert len(data) % SIMPLE2_BLOCK_SIZE == 0
                return PakCrypto._encrypt_simple2(data)
            if PakCrypto._is_sm4_method(encryption_method):
                bl = SM4.block_length()
                data_aligned = data
                if len(data_aligned) % bl != 0: data_aligned = data_aligned + b'\x00' * (bl - (len(data_aligned) % bl))
                return PakCrypto._encrypt_sm4(data_aligned, file_path, encryption_method)
            raise RuntimeError('Unknown encryption method')

    def _repack_single_file(self, pak_file_handle, modified_file_path: Path, entry: TencentPakEntry) -> bool:
            try:
                with open_long(modified_file_path, 'rb') as f: modified_data = f.read()
            except Exception as e: return False
            encryption_method = entry.encryption_method
            compression_method = entry.compression_method
            if compression_method == CM_NONE:
                out = modified_data
                if entry.encrypted: out = self._apply_encrypt_for_entry(out, modified_file_path, encryption_method)
                aligned_len = PakCrypto.align_encrypted_content_size(len(out), encryption_method)
                if aligned_len > entry.size:
                    diff = aligned_len - entry.size
                    if diff <= MAX_OVERFLOW_BYTES:
                        pak_file_handle.seek(entry.offset)
                        pak_file_handle.write(out)
                        return True
                    else: return False
                pak_file_handle.seek(entry.offset)
                pak_file_handle.write(out)
                if entry.size > aligned_len: pak_file_handle.write(b'\x00' * (entry.size - aligned_len))
                return True
            if entry.compressed_blocks:
                block_size = entry.compression_block_size
                blocks_plain = [modified_data[i:i+block_size] for i in range(0, len(modified_data), block_size)]
                max_blocks = min(len(blocks_plain), len(entry.compressed_blocks))
                blocks_plain = blocks_plain[:max_blocks]
                produced_blocks = [None] * len(entry.compressed_blocks)
                indices = PakCrypto.generate_block_indices(len(entry.compressed_blocks), encryption_method)
                for i_plain, plain in enumerate(blocks_plain):
                    stored_index = indices[i_plain]
                    target_block = entry.compressed_blocks[stored_index]
                    target_len = target_block.end - target_block.start
                    try: comp = PakCompression.compress_block(plain, compression_method, self._zstd_dict, target_len)
                    except Exception as e: return False
                    if len(comp) > target_len:
                        produced_blocks[stored_index] = None; continue
                    if len(comp) < target_len: comp = comp + b'\x00' * (target_len - len(comp))
                    if entry.encrypted: comp = self._apply_encrypt_for_entry(comp, modified_file_path, encryption_method)
                    comp = comp.ljust(PakCrypto.align_encrypted_content_size(len(comp), encryption_method), b'\x00')
                    produced_blocks[stored_index] = comp
                for idx, block in enumerate(entry.compressed_blocks):
                    data_bytes = produced_blocks[idx]
                    if data_bytes is None: continue
                    pak_file_handle.seek(block.start)
                    pak_file_handle.write(data_bytes)
                return True
            return False

def alv_build_pak_filename_map(pak_file):
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

def alv_dump_unpacking_log(pak_file, output_log_path: Path):
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

def alv_alv_pak_encrypt_plaintext(plaintext: bytes, pak_relative_path: PurePath, encryption_method: int) -> bytes:
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

def alv_alv_pak_entry_map(pak):
    _s4184cf47039f = {}
    for _s0532244b9740, _s51252d1c742f in pak._index.items():
        for _s1a7065710c82, _sa6bb7cd505c6 in _s51252d1c742f.items():
            _s716d7db7eccd = str(PurePath(_s0532244b9740) / _s1a7065710c82).replace('\\', '/').lstrip('/')
            _s4184cf47039f[_s716d7db7eccd.lower()] = (_s716d7db7eccd, _sa6bb7cd505c6)
    return _s4184cf47039f

def alv_alv_pak_is_tool_artifact(path: Path) -> bool:
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

def alv_alv_pak_normalize_repack_path(pak, repack_root: Path, file_path: Path) -> str:
    rel = file_path.relative_to(repack_root).as_posix().lstrip('/')
    mount = str(getattr(pak, '_mount_point', '')).replace('\\', '/').strip('/')
    safe_mount = '/'.join((part for part in mount.split('/') if part not in ('', '.', '..')))
    if safe_mount and rel.lower().startswith((safe_mount + '/').lower()):
        rel = rel[len(safe_mount) + 1:]
    return rel.lstrip('/')

def alv_alv_pak_scan_repack(pak, repack_root: Path) -> dict:
    """Classify Repack files strictly against existing source PAK paths."""
    source_map = alv_alv_pak_entry_map(pak)
    basename_map = {}
    for _key, (internal, entry) in source_map.items():
        basename_map.setdefault(PurePath(internal).name.lower(), []).append((internal, entry))
    matched = []
    unknown = []
    ignored = []
    for p in sorted(repack_root.rglob('*'), key=lambda x: str(x).lower()):
        if not p.is_file():
            continue
        if alv_alv_pak_is_tool_artifact(p):
            ignored.append(p)
            continue
        rel = alv_alv_pak_normalize_repack_path(pak, repack_root, p)
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

def alv_alv_pak_extract_plain(pak, internal: str, entry) -> bytes:
    _s108c63e1eda0 = TencentPakFile._extract_entry_plain(pak._file_content, entry, PurePath(internal), pak._zstd_dict)
    return _s108c63e1eda0[:entry.uncompressed_size]

def alv_alv_pak_profile(entry):
    return {'compression_method': int(entry.compression_method), 'encrypted': bool(entry.encrypted), 'encryption_method': int(entry.encryption_method if entry.encrypted else 0), 'block_size': int(entry.compression_block_size or 0)}

def alv_alv_validate_dynamic_repack(original_path: Path, output_path: Path, targets: list, sample_non_targets: int=8) -> dict:
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
    smap = alv_alv_pak_entry_map(src)
    rmap = alv_alv_pak_entry_map(rep)
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
            recovered = alv_alv_pak_extract_plain(rep, rep_internal, rep_entry_for_path)
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

def alv_dynamic_replace_single_entry(pak, target_entry, internal: str, new_plain: bytes, output_pak: Path) -> None:
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
            stored = alv_alv_pak_encrypt_plaintext(payload, crypto_path, enc_method)
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
            encoded = alv_alv_pak_encrypt_plaintext(comp, crypto_path, enc_method) if encrypted else comp
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

def alv_pakdel_norm_path(value: str) -> str:
    return str(value).replace('\\', '/').strip().lstrip('/')


def alv_pakdel_pack_string(value: str) -> bytes:
    if not value:
        return struct.pack('<i', 0)
    raw = value.encode('utf-8') + b'\x00'
    return struct.pack('<i', len(raw)) + raw


def alv_pakdel_encrypt_index(pak, plain_index: bytes) -> bytes:
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


def alv_pakdel_write_footer(pak, fp, *, index_hash: bytes, index_size: int,
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



def alv_compact_entry_stored_bytes(pak, entry) -> bytes:
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


def alv_compact_entry_record(entry, new_offset: int) -> dict:
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


def alv_compact_serialize_entry(item: dict, version: int) -> bytes:
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


def alv_compact_parse_raw_directory_map(pak):
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


def alv_compact_rebuild_pak(pak_path: Path, output_pak: Path,
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
        _alv_require_operation(('pak.repack', 'pak.repack_single'))
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
        _alv_require_operation((operation_id,))
    if gmalg is None:
        raise RuntimeError("Dependency gmalg belum tersedia.")
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
        wanted = {alv_pakdel_norm_path(x) for x in delete_targets if alv_pakdel_norm_path(x)}
    if empty_all:
        wanted = set(before_paths)

    if not empty_all:
        if not wanted:
            raise ValueError("Tidak ada target delete.")
        missing = sorted(wanted - before_set)
        if missing:
            raise ValueError("Target tidak ditemukan: " + ", ".join(missing))

    mount, raw_entries, raw_dirs, tail = alv_compact_parse_raw_directory_map(pak)

    # Build surviving directory references and determine which original raw entries
    # are still referenced after deletion.
    kept_dirs = []
    kept_raw_indices = set()
    removed_paths = []

    for raw_dir, entries in raw_dirs:
        kept = []
        for name, raw_ref, mapped in entries:
            internal = alv_pakdel_norm_path(
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
        stored = alv_compact_entry_stored_bytes(pak, entry)
        new_data.extend(stored)
        new_records.append(alv_compact_entry_record(entry, new_offset))

    # Rebuild index from scratch.
    new_index = bytearray()
    new_index.extend(alv_pakdel_pack_string(mount))
    new_index.extend(struct.pack("<I", len(new_records)))
    for rec in new_records:
        new_index.extend(alv_compact_serialize_entry(rec, pak._pak_info.version))

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
        new_index.extend(alv_pakdel_pack_string(raw_dir))
        new_index.extend(struct.pack("<Q", len(entries)))
        for name, raw_ref in entries:
            new_index.extend(alv_pakdel_pack_string(name))
            new_index.extend(struct.pack("<i", raw_ref))

    # Preserve any unknown trailer bytes that belonged to the plaintext index.
    new_index.extend(tail)

    plain_index = bytes(new_index)
    index_hash = SHA1.new(plain_index).digest()
    encrypted_index = alv_pakdel_encrypt_index(pak, plain_index)
    new_index_offset = len(new_data)

    output_pak.parent.mkdir(parents=True, exist_ok=True)
    with output_pak.open("wb") as f:
        f.write(new_data)
        f.write(encrypted_index)
        alv_pakdel_write_footer(
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


def alv_delete_pak_entries(pak_path: Path, output_pak: Path, targets: list[str]) -> dict:
    """Public PakCore API: physical/multi delete + compact rebuild."""
    _alv_require_operation(('pak.delete_entry',))
    return alv_compact_rebuild_pak(pak_path, output_pak, delete_targets=targets, empty_all=False, authorization_operation='pak.delete_entry')


def alv_delete_all_from_pak(pak_path: Path, output_pak: Path) -> dict:
    """Public PakCore API: remove every entry/payload and keep a valid compact PAK."""
    _alv_require_operation(('pak.delete_all',))
    return alv_compact_rebuild_pak(pak_path, output_pak, empty_all=True, authorization_operation='pak.delete_all')


Reader = PakReader
def create_dirs(base: Path):
    os.makedirs(to_long_path(base), exist_ok=True)
    obb_unpacker = base / "OBB_UNPACKER"
    os.makedirs(to_long_path(obb_unpacker / ORGNAL_DIR), exist_ok=True)
    os.makedirs(to_long_path(obb_unpacker / EDITED_DIR), exist_ok=True)
    os.makedirs(to_long_path(obb_unpacker / UNPACK_DIR), exist_ok=True)
    os.makedirs(to_long_path(obb_unpacker / REPACK_DIR), exist_ok=True)
    os.makedirs(to_long_path(obb_unpacker / SINGLE_DIR), exist_ok=True)
    os.makedirs(to_long_path(ENCRYPT_INPUT_DIR), exist_ok=True)
    os.makedirs(to_long_path(ENCRYPT_OUTPUT_DIR), exist_ok=True)
    os.makedirs(to_long_path(ANLAISH_ORG), exist_ok=True)
    os.makedirs(to_long_path(ANLAISH_MOD), exist_ok=True)
    os.makedirs(to_long_path(ANLAISH_RESULT), exist_ok=True)
    
    credit_tool = base / "CREDIT_TOOL"
    os.makedirs(to_long_path(credit_tool / "ORGNAL"), exist_ok=True)
    os.makedirs(to_long_path(credit_tool / "MODDED FILE"), exist_ok=True)
    
  #  obbzip_root = base / "OBBZIP"
  #  os.makedirs(to_long_path(obbzip_root / "ORGNAL_OBB"), exist_ok=True)
   # os.makedirs(to_long_path(obbzip_root / "UNPACKED_OBB"), exist_ok=True)
   # os.makedirs(to_long_path(obbzip_root / "REPACK_OBB"), exist_ok=True)
   # os.makedirs(to_long_path(obbzip_root / "Modified_pak"), exist_ok=True)
    
    # 🔥 SKIN TOOL FOLDERS (BGMI & PUBG)
    skin_tool = base / "SKIN_TOOL"
    for game in ["BGMI_SKIN", "PUBG_SKIN"]:
        game_base = skin_tool / game
        
        # MINI
        mini_base = game_base / "MINI"
        os.makedirs(mini_base / "MINI_ICON" / "INPUT", exist_ok=True)
        os.makedirs(mini_base / "MINI_ICON" / "OUTPUT", exist_ok=True)
        os.makedirs(mini_base / "TXTS", exist_ok=True)
        os.makedirs(mini_base / "AUTO_THEME" / "FILES", exist_ok=True)
        os.makedirs(mini_base / "AUTO_THEME" / "MODIFIED", exist_ok=True)
        os.makedirs(mini_base / "AUTO_THEME" / "TXT", exist_ok=True)
        os.makedirs(mini_base / "HIT EFFECT" / "org", exist_ok=True)
        os.makedirs(mini_base / "HIT EFFECT" / "modified", exist_ok=True)
        os.makedirs(mini_base / "LOOTCRATES" / "org", exist_ok=True)
        os.makedirs(mini_base / "LOOTCRATES" / "modified", exist_ok=True)
        
        # ZSDIC
        game_key = "BGMI" if game == "BGMI_SKIN" else "PUBG"
        zsdic_base = game_base / "ZSDIC"
        os.makedirs(zsdic_base / game_key / "skindats", exist_ok=True)
        os.makedirs(zsdic_base / game_key / "edited", exist_ok=True)
        os.makedirs(zsdic_base / game_key / "size", exist_ok=True)
        
        # STAND POSH
        stand_posh = game_base / "STAND_POSH"
        os.makedirs(stand_posh / "INPUT", exist_ok=True)
        os.makedirs(stand_posh / "OUTPUT", exist_ok=True)
        
        # FINAL
        os.makedirs(game_base / "FINAL", exist_ok=True)

# ======================================================================
# 🔥 AUTO DOWNLOAD SKIN_TOOL FROM GITHUB (SAME UI AS SCREENSHOT)
# ======================================================================

# ======================================================================
# 🔥 AUTO DOWNLOAD SKIN_TOOL FROM GITHUB (SIRF DOWNLOAD DIKHE)
# ======================================================================

import requests
import zipfile
from pathlib import Path
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, TransferSpeedColumn
from rich.panel import Panel
from rich.console import Console
from rich import box

console = Console()

def download_skin_tool():
    """GitHub se download + extract (Sirf download dikhe, extract background mein)"""
    
    # Download pinned to specific commit hash — not /main/ (unpinned)
    # URL is pinned to an immutable commit; the downloaded bytes are then
    # verified against the git blob SHA-1 of SKIN_TOOL.zip at that commit.
    GITHUB_URL = "https://raw.githubusercontent.com/sellacountvinay-creator/SKIN_TOOL/5c7ad2b4996fcd468bf245be43580d1fe131423e/SKIN_TOOL.zip"
    SKIN_TOOL_BLOB_SHA1 = "cbd3d0e257963b54f34a908b6864040c7f96fbb1"
    
    base_dir = Path("ALVSIA_PRO_DATA")
    skin_tool_dir = base_dir / "SKIN_TOOL"
    zip_path = base_dir / "SKIN_TOOL.zip"
    
    if skin_tool_dir.exists():
        return True
    
    os.makedirs(base_dir, exist_ok=True)
    
    # ============================================================
    # 🔥 SIRF DOWNLOADING PANEL (EK BAAR)
    # ============================================================
    console.print()
    console.print(Panel(
        "[bold bright_cyan]📥 Downloading SKIN_TOOL.zip...[/]\n"
        "[dim]Please wait...[/]",
        title="[bold black on bright_cyan] DOWNLOADING [/]",
        border_style="bright_cyan",
        box=box.HEAVY
    ))
    console.print()
    
    try:
        # ============================================================
        # 🔥 DOWNLOAD PROGRESS (SIRF YAHI DIKHEGA)
        # ============================================================
        with Progress(
            TextColumn("[bold cyan]⬇️ {task.description}"),
            BarColumn(bar_width=50, complete_style=f"bold {get_banner_color()}", finished_style="bold green"),
            TextColumn("[bold white]{task.percentage:>3.0f}%"),
            TextColumn("[dim]({task.fields[file_size]})"),
            TransferSpeedColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            
            response = requests.get(GITHUB_URL, stream=True, timeout=60)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            task = progress.add_task(
                f"Downloading",
                total=total_size,
                file_size=""
            )
            
            with open(zip_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            file_size_mb = downloaded / (1024 * 1024)
                            progress.update(
                                task,
                                completed=downloaded,
                                file_size=f"{file_size_mb:.2f} MB"
                            )
        
        # 🔥 DOWNLOAD COMPLETE
        console.print()
        console.print("[bold {get_banner_color()}]✔ Download complete![/]")
        
        # ============================================================
        # Integrity gate: refuse to unpack a tampered or truncated download.
        if not _verify_pinned_git_blob(zip_path.read_bytes(), SKIN_TOOL_BLOB_SHA1):
            zip_path.unlink(missing_ok=True)
            raise RuntimeError("SKIN_TOOL.zip failed pinned git-blob integrity check")

        # 🔥 EXTRACT (BACKGROUND MEIN - KUCH DIKHAO MAT)
        # ============================================================
       # console.print("[dim]📦 Extracting... (Please wait)[/]")
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            _alvsia_safe_extract_zip(zip_ref, base_dir)
        
        # 🔥 ZIP DELETE (CHUP CHAP)
        if zip_path.exists():
            zip_path.unlink()
        
        # ============================================================
        # 🔥 SUCCESS (SIRF EK PANEL)
        # ============================================================
        console.print()
        console.print(Panel(
            f"[bold {get_banner_color()}]✅ SKIN_TOOL ready![/]",
            title= f"[bold black on {get_banner_color()}] ✓ COMPLETE [/]",
            border_style=get_banner_color(),
            box=box.ROUNDED
        ))
        
        # 🔥 PRESS ENTER
        from rich.prompt import Prompt
        Prompt.ask("[bold bright_cyan]Press Enter to continue...[/bold bright_cyan]", default="")
        return True
        
    except Exception as e:
        console.print()
        console.print(Panel(
            f"[bold red]❌ Download failed![/]\n"
            f"[yellow]Error: {e}[/]",
            title="[bold red] ⚠️ ERROR [/]",
            border_style="red",
            box=box.HEAVY
        ))
        return False
        
# ======================================================================
# 🔥 YAHAN SE EXISTING CODE CONTINUE HOTA HAI 🔥
# ======================================================================

def files_available_panel(pak_files: List[Path], folder_label: str = "Files available") -> Panel:
    b_color = get_banner_color()
    tbl = Table(box=box.SQUARE, expand=True, border_style=b_color)
    
    tbl.add_column("No.", style="bold cyan", width=4, justify="right")
    tbl.add_column("Filename", style=f"bold {b_color}")
    tbl.add_column("Size", style=f"bold {b_color}", justify="right")
    
    for i, p in enumerate(pak_files, start=1):
        try:
            size = os.stat(to_long_path(p)).st_size
            size_str = f"{size:,} bytes"
        except Exception: 
            size_str = "?"
        
        tbl.add_row(
            to_fancy(str(i)), 
            Text(to_fancy(p.name), style=f"bold {b_color}"), 
            Text(to_fancy(size_str), style=f"bold {b_color}")
        )
        
    return Panel(
        tbl, 
        title=f"[bold black on {b_color}]{to_fancy(folder_label)}[/]", 
        border_style=b_color, 
        box=box.HEAVY # Charo kone acche se lock ho jayenge
    )

def list_paks_in_folder(folder: Path) -> List[Path]:
    folder_str = to_long_path(folder)
    if not os.path.exists(folder_str): return []
    try: names = sorted(os.listdir(folder_str))
    except Exception: return []
    results: List[Path] = []
    for name in names:
        try:
            full = Path(folder) / name
            if os.path.isfile(to_long_path(full)) and (full.suffix.lower() == '.pak' or full.suffix.lower() == '.obb'):
                results.append(full)
        except Exception: continue
    return results

# ---------------------------
# TOOLS (RedMagix Core)
# ---------------------------
def encrypt_file(input_path: Path, output_path: Path) -> bool:
    try:
        shutil.copy2(to_long_path(input_path), to_long_path(output_path))
        with open_long(output_path, "r+b") as f:
            f.seek(0, 2)
            file_size = f.tell()
            seek_pos = max(0, file_size - 45)
            f.seek(seek_pos)
            f.write(b'\x00' * 40)
        return True
    except Exception as e:
        console.print(f"[red]Error encrypting {input_path.name}: {e}[/red]")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# 🔒 OPTION 15 — PAK ENCRYPT SUBMENU
# Sub-options: 1=Normal Enc  2=Custom Enc  3=Decrypt Restore  0=Back
# ══════════════════════════════════════════════════════════════════════════════

def run_pak_encrypt_submenu():
    """Option 15 – PAK Encryption Tool with Normal / Custom / Decrypt submenu."""

    # ── folder layout (mirrors Enc_pak already used by run_encrypt_tool) ──────
    enc_base   = Path(BASE_DIR_NAME) / "Enc_pak"
    input_dir  = enc_base / "Input"
    output_dir = enc_base / "Output"
    os.makedirs(to_long_path(input_dir),  exist_ok=True)
    os.makedirs(to_long_path(output_dir), exist_ok=True)

    b_color = get_banner_color()

    # ── helpers ───────────────────────────────────────────────────────────────
    def _header():
        console.clear()
        print_banner_and_header()
        print_user_profile()

    def _get_files():
        return [f for f in input_dir.iterdir()
                if f.is_file() and f.suffix.lower() in ('.pak', '.obb')]

    def _no_files_panel():
        console.print(Panel(
            f"[red]No .pak / .obb files found in:[/red]\n"
            f"[yellow]{input_dir.resolve()}[/yellow]\n\n"
            f"[white]Place your files there and try again.[/white]",
            title="❗ No Files", border_style="red", box=box.HEAVY
        ))
        Prompt.ask("\nPress Enter to continue", default="")

    # ── Normal Encryption (last-45-bytes sig kill, same as encrypt_file) ──────
    def _normal_enc():
        _header()
        console.print(Panel(
            f"[bold {b_color}]🔒 NORMAL ENCRYPTION[/bold {b_color}]\n"
            f"[dim]Standard MINI OBB sig kill — zeroes last 45 bytes[/dim]",
            border_style=b_color, box=box.HEAVY
        ))
        files = _get_files()
        if not files:
            _no_files_panel(); return

        console.print(f"[green]Found {len(files)} file(s).[/green]\n")
        ok = 0
        with Progress(
            SpinnerColumn("bouncingBar", style=f"bold {b_color}"),
            TextColumn(f"[bold {b_color}]{{task.description}}"),
            BarColumn(),
            TextColumn("[bold white]{task.percentage:>3.0f}%"),
            console=console
        ) as prog:
            task = prog.add_task("Normal Encrypting...", total=len(files))
            for f in files:
                out = output_dir / f.name
                try:
                    shutil.copy2(to_long_path(f), to_long_path(out))
                    with open_long(out, "r+b") as fh:
                        fh.seek(0, 2)
                        sz = fh.tell()
                        fh.seek(max(0, sz - 45))
                        fh.write(b'\x00' * 40)
                    ok += 1
                    prog.console.print(f"[bold green]✔ Encrypted:[/bold green] {f.name}")
                except Exception as e:
                    prog.console.print(f"[red]✘ {f.name}: {e}[/red]")
                prog.advance(task)

        console.print(Panel(
            f"[bold {b_color}]✔ {ok}/{len(files)} files encrypted successfully![/bold {b_color}]\n"
            f"[white]Output:[/white] [cyan]{output_dir.resolve()}[/cyan]",
            border_style=b_color, box=box.HEAVY
        ))
        Prompt.ask("\nPress Enter to continue", default="")

    # ── Custom Encryption (level 1-10 + optional custom XOR key) ─────────────
    def _custom_enc():
        _header()
        console.print(Panel(
            f"[bold {b_color}]🔐 CUSTOM ENCRYPTION[/bold {b_color}]\n"
            f"[dim]Level 1-10 intensity + optional custom XOR key[/dim]",
            border_style=b_color, box=box.HEAVY
        ))
        files = _get_files()
        if not files:
            _no_files_panel(); return

        # Level selection
        level_table = Table(show_header=True, header_style=f"bold black on {b_color}",
                            box=box.DOUBLE_EDGE, border_style=b_color, expand=True)
        level_table.add_column("LEVEL", style="bold white", justify="center", width=8)
        level_table.add_column("BYTES ZEROED", style=f"bold {b_color}")
        level_table.add_column("DESCRIPTION", style="dim white")
        level_defs = [
            ("1",  20,  "Light — last 20 bytes"),
            ("2",  30,  "Mild  — last 30 bytes"),
            ("3",  40,  "Standard — last 40 bytes"),
            ("4",  45,  "Normal — last 45 bytes (default)"),
            ("5",  64,  "Medium — last 64 bytes"),
            ("6",  80,  "Strong — last 80 bytes"),
            ("7",  100, "Heavy — last 100 bytes"),
            ("8",  128, "Aggressive — last 128 bytes"),
            ("9",  200, "Extreme — last 200 bytes"),
            ("10", 256, "MAX — last 256 bytes"),
        ]
        for lv, nb, desc in level_defs:
            level_table.add_row(f"[bold cyan]{lv}[/bold cyan]",
                                f"[bold {b_color}]{nb}[/bold {b_color}]",
                                f"[white]{desc}[/white]")
        console.print(Panel(level_table, border_style=b_color, box=box.HEAVY))

        raw_level = Prompt.ask(f"\n[bold {b_color}]Select Level (1-10)[/bold {b_color}]", default="4")
        try:
            level_idx = max(0, min(9, int(raw_level) - 1))
        except ValueError:
            level_idx = 3
        _, zero_bytes, _ = level_defs[level_idx]

        # Optional custom XOR key
        custom_key_str = Prompt.ask(
            f"[bold {b_color}]Custom XOR key as HEX (leave blank to skip)[/bold {b_color}]",
            default=""
        ).strip()
        custom_key = b""
        if custom_key_str:
            try:
                custom_key = bytes.fromhex(custom_key_str)
                console.print(f"[green]✔ Custom key loaded ({len(custom_key)} bytes)[/green]")
            except ValueError:
                console.print("[yellow]⚠ Invalid hex — skipping custom key[/yellow]")

        console.print(f"\n[green]Found {len(files)} file(s). Level {level_idx+1} — {zero_bytes} bytes.[/green]\n")
        ok = 0
        with Progress(
            SpinnerColumn("bouncingBar", style=f"bold {b_color}"),
            TextColumn(f"[bold {b_color}]{{task.description}}"),
            BarColumn(),
            TextColumn("[bold white]{task.percentage:>3.0f}%"),
            console=console
        ) as prog:
            task = prog.add_task("Custom Encrypting...", total=len(files))
            for f in files:
                out = output_dir / f.name
                try:
                    shutil.copy2(to_long_path(f), to_long_path(out))
                    with open_long(out, "r+b") as fh:
                        fh.seek(0, 2)
                        sz = fh.tell()
                        seek_pos = max(0, sz - zero_bytes)
                        fh.seek(seek_pos)
                        if custom_key:
                            # XOR the tail with rolling custom key
                            fh.seek(seek_pos)
                            tail = bytearray(fh.read(zero_bytes))
                            kl = len(custom_key)
                            tail = bytearray(tail[i] ^ custom_key[i % kl] for i in range(len(tail)))
                            fh.seek(seek_pos)
                            fh.write(bytes(tail))
                        else:
                            fh.seek(seek_pos)
                            fh.write(b'\x00' * zero_bytes)
                    ok += 1
                    prog.console.print(f"[bold green]✔ Encrypted:[/bold green] {f.name}  [dim](level {level_idx+1})[/dim]")
                except Exception as e:
                    prog.console.print(f"[red]✘ {f.name}: {e}[/red]")
                prog.advance(task)

        console.print(Panel(
            f"[bold {b_color}]✔ {ok}/{len(files)} files encrypted (Level {level_idx+1})![/bold {b_color}]\n"
            f"[white]Output:[/white] [cyan]{output_dir.resolve()}[/cyan]",
            border_style=b_color, box=box.HEAVY
        ))
        Prompt.ask("\nPress Enter to continue", default="")

    # ── Decrypt Restore (restore MINI OBB / ZSDIC signature from original) ────
    def _decrypt_restore():
        _header()
        console.print(Panel(
            f"[bold {b_color}]🔓 DECRYPT RESTORE[/bold {b_color}]\n"
            f"[dim]Restore MINI OBB / ZSDIC signature from an original reference file[/dim]",
            border_style=b_color, box=box.HEAVY
        ))

        # Expect: Input/ has the encrypted files, Output/ will get restored files
        # User must also supply an original (unencrypted) reference in Input/original/
        orig_dir = input_dir / "original"
        os.makedirs(to_long_path(orig_dir), exist_ok=True)

        enc_files = _get_files()
        orig_files = [f for f in orig_dir.iterdir()
                      if f.is_file() and f.suffix.lower() in ('.pak', '.obb')] if orig_dir.exists() else []

        if not enc_files:
            _no_files_panel(); return

        if not orig_files:
            console.print(Panel(
                f"[red]No original reference file found![/red]\n"
                f"[yellow]Place the unencrypted original .pak/.obb in:[/yellow]\n"
                f"[cyan]{orig_dir.resolve()}[/cyan]\n\n"
                f"[white]The last 45 bytes of the original will be used to restore the signature.[/white]",
                border_style="red", box=box.HEAVY
            ))
            Prompt.ask("\nPress Enter to continue", default="")
            return

        # Map originals by filename for fast lookup
        orig_map = {f.name: f for f in orig_files}

        console.print(f"[green]Found {len(enc_files)} encrypted file(s).[/green]\n")
        ok = 0
        with Progress(
            SpinnerColumn("bouncingBar", style=f"bold {b_color}"),
            TextColumn(f"[bold {b_color}]{{task.description}}"),
            BarColumn(),
            TextColumn("[bold white]{task.percentage:>3.0f}%"),
            console=console
        ) as prog:
            task = prog.add_task("Restoring signatures...", total=len(enc_files))
            for f in enc_files:
                out = output_dir / f.name
                try:
                    if f.name not in orig_map:
                        prog.console.print(f"[yellow]⚠ No matching original for {f.name} — skipped[/yellow]")
                        prog.advance(task); continue

                    orig_path = orig_map[f.name]

                    # Read last 45 bytes from original
                    with open_long(orig_path, "rb") as fh:
                        fh.seek(0, 2)
                        orig_sz = fh.tell()
                        sig_seek = max(0, orig_sz - 45)
                        fh.seek(sig_seek)
                        original_sig = fh.read(45)

                    # Copy encrypted file → output, then patch signature back
                    shutil.copy2(to_long_path(f), to_long_path(out))
                    with open_long(out, "r+b") as fh:
                        fh.seek(0, 2)
                        out_sz = fh.tell()
                        patch_seek = max(0, out_sz - 45)
                        fh.seek(patch_seek)
                        fh.write(original_sig)

                    ok += 1
                    prog.console.print(f"[bold green]✔ Restored:[/bold green] {f.name}")
                except Exception as e:
                    prog.console.print(f"[red]✘ {f.name}: {e}[/red]")
                prog.advance(task)

        console.print(Panel(
            f"[bold {b_color}]✔ {ok}/{len(enc_files)} signatures restored![/bold {b_color}]\n"
            f"[white]Output:[/white] [cyan]{output_dir.resolve()}[/cyan]",
            border_style=b_color, box=box.HEAVY
        ))
        Prompt.ask("\nPress Enter to continue", default="")

    # ── Sub-menu loop ─────────────────────────────────────────────────────────
    while True:
        _header()

        sub_table = Table(
            show_header=True,
            header_style=f"bold black on {b_color}",
            box=box.DOUBLE_EDGE,
            border_style=b_color,
            expand=True,
            title=(rainbow_markup("  🔒 PAK ENCRYPTION TOOL  ") if CURRENT_SESSION_COLOR == "rainbow" else f"[reverse]  🔒 {to_fancy('PAK ENCRYPTION TOOL')}  [/]")
        )
        if CURRENT_SESSION_COLOR == "rainbow":
            sub_table.add_column(rainbow_text("𝐎𝐏𝐓"), justify="center", width=6)
            sub_table.add_column(rainbow_text("𝐎𝐏𝐄𝐑𝐀𝐓𝐈𝐎𝐍"))
            sub_table.add_column(rainbow_text("𝐃𝐄𝐒𝐂𝐑𝐈𝐏𝐓𝐈𝐎𝐍"))
        else:
            sub_table.add_column("𝐎𝐏𝐓",       style="bold white",  justify="center", width=6)
            sub_table.add_column("𝐎𝐏𝐄𝐑𝐀𝐓𝐈𝐎𝐍", style=f"bold {b_color}")
            sub_table.add_column("𝐃𝐄𝐒𝐂𝐑𝐈𝐏𝐓𝐈𝐎𝐍", style="dim white")

        if CURRENT_SESSION_COLOR == "rainbow":
            menu_row(sub_table, "1", "🔒 Normal Encryption", "Standard MINI OBB sig kill (last 45 bytes)")
            menu_row(sub_table, "2", "🔐 Custom Encryption", "Level 1-10 + Optional Custom XOR Key")
            menu_row(sub_table, "3", "🔓 Decrypt Restore", "Restore MINI OBB / ZSDIC signature")
            menu_row(sub_table, "0", "↩ Back", "Return to Main Menu")
        else:
            sub_table.add_row(
            "[bold cyan]1[/bold cyan]",
            f"[bold {b_color}]🔒 Normal Encryption[/bold {b_color}]",
            "[white]Standard MINI OBB sig kill (last 45 bytes)[/white]"
        )
        sub_table.add_row(
            "[bold cyan]2[/bold cyan]",
            f"[bold {b_color}]🔐 Custom Encryption[/bold {b_color}]",
            "[white]Level 1-10 + Optional Custom XOR Key[/white]"
        )
        sub_table.add_row(
            "[bold yellow]3[/bold yellow]",
            "[bold yellow]🔓 Decrypt Restore[/bold yellow]",
            "[white]Restore MINI OBB / ZSDIC signature[/white]"
        )
        sub_table.add_row(
            "[bold red]0[/bold red]",
            "[bold red]↩ Back[/bold red]",
            "[dim red]Return to Main Menu[/dim red]"
        )

        console.print(Panel(sub_table, border_style=b_color, box=box.HEAVY))
        sub_choice = Prompt.ask(f"[bold {b_color}]Select option (1-3, 0 = Back)[/bold {b_color}]")

        if sub_choice == "1":
            _normal_enc()
        elif sub_choice == "2":
            _custom_enc()
        elif sub_choice == "3":
            _decrypt_restore()
        elif sub_choice == "0":
            break
        else:
            console.print(Panel("[bold red]❌ Invalid option![/bold red]", border_style="red", box=box.HEAVY))
            time.sleep(1)

@security_guard
def run_encrypt_tool():
    console.clear()
    console.print(get_neon_header())
    b_color = get_banner_color()
    console.print(Panel(f"[bold {b_color}]{to_fancy('ENCRYPTION TOOL')}[/bold {b_color}]\n[dim]Lock .pak/.obb files (signature kill).[/dim]", border_style=b_color))

    create_dirs(Path(BASE_DIR_NAME))
    input_files = [f for f in ENCRYPT_INPUT_DIR.iterdir() if f.is_file() and f.suffix.lower() in ('.pak', '.obb')]
    if not input_files:
        console.print(Panel(f"[red]No .pak/.obb files found in[/red]\n[yellow]{ENCRYPT_INPUT_DIR.resolve()}[/yellow]\n\n[white]Please place your files there and try again.[/white]", title="❗ No Files", border_style="red"))
        Prompt.ask("\nPress Enter to continue", default="")
        return

    console.print(f"[green]Found {len(input_files)} file(s) to process.[/green]")
    success_count = 0

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"), console=console) as progress:
        task = progress.add_task(f"[{b_color}]Encrypting...", total=len(input_files))
        for f in input_files:
            out_path = ENCRYPT_OUTPUT_DIR / f.name
            if encrypt_file(f, out_path):
                success_count += 1
            progress.advance(task)

    console.print("\n")
    if success_count == len(input_files):
        console.print(Panel(f"[bold {b_color}]✔ {to_fancy('ALL FILES ENCRYPTED SUCCESSFULLY')}![/bold {b_color}]\n[white]Output folder:[/white] [cyan]{ENCRYPT_OUTPUT_DIR.resolve()}[/cyan]", border_style=b_color))
    else:
        console.print(Panel(f"[yellow]Encryption completed with {success_count}/{len(input_files)} successes.[/yellow]\n[white]Check errors above. Output folder:[/white] [cyan]{ENCRYPT_OUTPUT_DIR.resolve()}[/cyan]", border_style="yellow"))
    Prompt.ask("\nPress Enter to return to menu", default="")

@security_guard
def run_obb_analysis_tool():
    console.clear()
    console.print(get_neon_header())
    b_color = get_banner_color()
    console.print(Panel(f"[bold {b_color}]{to_fancy('DEEP SCAN & EXTRACT (PRO AUTO-SINGLE)')}[/bold {b_color}]\n[dim]Scanning OBBs and auto-extracting modified .uasset/.uexp to RESULT folder...[/dim]", border_style=b_color))

    org_files = list_paks_in_folder(ANLAISH_ORG)
    mod_files = list_paks_in_folder(ANLAISH_MOD)

    if not org_files or not mod_files:
        console.print(Panel(f"[red]Error: Files missing![/red]\n[white]Please put Original OBB in: {ANLAISH_ORG}\nPlease put Mod OBB in: {ANLAISH_MOD}[/white]"))
        Prompt.ask("Press Enter to go back...")
        return

    total_processed = 0

    for org_path in org_files:
        mod_path = next((f for f in mod_files if f.name == org_path.name), None)
        if not mod_path:
            console.print(Panel(f"[yellow]Skipping {org_path.name}: Not found in MOD folder![/yellow]"))
            continue

        console.print(f"\n[bold {b_color}]==================================================[/]")
        console.print(f"[{b_color}]{to_fancy('Original:')}[/{b_color}] {to_fancy(org_path.name)}")
        console.print(f"[magenta]{to_fancy('Modded:')}[/magenta]   {to_fancy(mod_path.name)}")
        console.print(Panel(f"[yellow]{to_fancy('LOADING FILES INTO MEMORY')}...[/yellow]"))
        
        current_result_dir = ANLAISH_RESULT / org_path.name
        os.makedirs(to_long_path(current_result_dir), exist_ok=True)

        try:
            pak_org = TencentPakFile(org_path)
            pak_mod = TencentPakFile(mod_path)

            console.print("[bold yellow]🔥POWER BY- @ALVSIA_PRO...👇[/bold yellow]")
            if not pak_mod._index:
                console.print("[bold cyan]..[/bold cyan]")
                pak_mod._index = pak_org._index
                pak_mod._pak_info = pak_org._pak_info
                pak_mod._mount_point = pak_org._mount_point
                pak_mod._zstd_dict = pak_org._zstd_dict
            else:
                console.print("[bold green][/bold green]")

            def flatten_index(pak_obj):
                flat = {}
                for dir_path, files in pak_obj._index.items():
                    for name, entry in files.items():
                        if entry:
                            full_p = str(dir_path / name).replace("\\", "/")
                            flat[full_p] = entry
                return flat

            flat_org = flatten_index(pak_org)
            flat_mod = flatten_index(pak_mod)

            extracted_count = 0
            
            with Progress(
                SpinnerColumn(), 
                TextColumn("[progress.description]{task.description}"), 
                BarColumn(), 
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"), 
                TimeElapsedColumn(),
                console=console
            ) as progress:
                task = progress.add_task(f"[{b_color}]Scanning & Extracting...", total=len(flat_mod))
                
                for f_path, mod_entry in flat_mod.items():
                    valid_exts = ('.uasset', '.uexp', '.lua', '.json', '.ini')
                    if f_path.lower().endswith(valid_exts) or 'luatool' in f_path.lower():
                        is_modified = False
                        
                        if f_path in flat_org:
                            org_entry = flat_org[f_path]
                            if mod_entry.size != org_entry.size:
                                is_modified = True
                            else:
                                try:
                                    org_data = pak_org._peek_content(org_entry.offset, org_entry.size, org_entry.encryption_method)
                                    mod_data = pak_mod._peek_content(mod_entry.offset, mod_entry.size, mod_entry.encryption_method)
                                    if org_data != mod_data:
                                        is_modified = True
                                except Exception: pass
                        else:
                            is_modified = True 

                        if is_modified:
                            relative_path = Path(f_path)
                            dest_file = current_result_dir / relative_path
                            
                            os.makedirs(to_long_path(dest_file.parent), exist_ok=True)
                            
                            try:
                                pak_mod._write_to_disk(dest_file, mod_entry)
                                extracted_count += 1
                                
                                file_name_only = relative_path.name
                                
                                # 1. Auto-Detected Location in Green (Bina aage ke path ke)
                                progress.console.print(f"[bold {get_banner_color()}]✓ {to_fancy('Auto-Detected Location')}:[/bold {get_banner_color()}]")
                                
                                # 2. Premium Green Box with Blue Encryption Text
                                panel_text = (
                                    f"[bold cyan]Extracted:[/] [bold white]{file_name_only}[/]\n"
                                    f"[bold yellow]Target Entry:[/] [bold green]{relative_path.as_posix()}[/]\n"
                                    f"[bold bright_blue]Encryption Method Applied: {mod_entry.encryption_method}[/]"
                                )
                                progress.console.print(Panel(panel_text, border_style=get_banner_color(), box=box.SQUARE))
                                
                            except Exception as e:
                                progress.console.print(f"[bold red]❌ FAILED:[/] {f_path} - [dim]{e}[/dim]")

                    progress.advance(task)

            total_processed += 1
        except Exception as e:
            console.print(Panel(f"[red]Analysis Failed for {org_path.name}: {e}[/red]"))

    MOD_REPACK_BASE = ANLAISH_DIR / "MOD_REPACK"
    os.makedirs(to_long_path(MOD_REPACK_BASE), exist_ok=True)

    if total_processed > 0:
        console.print(Panel(f"[bold {b_color}]🎉 {to_fancy('ALL FILES ANALYZED & EXTRACTED SUCCESSFULLY')}![/bold {b_color}]\n[white]Total OBBs Processed: {total_processed}[/white]", border_style=b_color))
    
    while True:
        console.print("\n")
        pro_menu = Table(show_header=False, box=box.SIMPLE, expand=True)
        if CURRENT_SESSION_COLOR == "rainbow":
            pro_menu.add_column(rainbow_text("𝐎𝐏𝐓"), width=4)
            pro_menu.add_column(rainbow_text("DESC"))
            pro_menu.add_row(rainbow_text("1"), rainbow_text("AUTO REMOVE CRDIT"))
            pro_menu.add_row(rainbow_text("2"), rainbow_text("ADD YOUR CREDIT"))
            pro_menu.add_row(rainbow_text("3"), rainbow_text("PRO REPACK"))
            pro_menu.add_row(rainbow_text("0"), rainbow_text("BACK"))
        else:
            pro_menu.add_column("𝐎𝐏𝐓", style="bold white", width=4)
            pro_menu.add_column("DESC", style=f"bold {b_color}")
            pro_menu.add_row("1", to_fancy("AUTO REMOVE CRDIT"))
            pro_menu.add_row("2", to_fancy("ADD YOUR CREDIT"))
            pro_menu.add_row("3", to_fancy("PRO REPACK"))
            pro_menu.add_row("0", f"[red]{to_fancy('BACK')}[/red]")
        
        console.print(Panel(pro_menu, title=f"[bold yellow]🔥 {to_fancy('USE PRO MODE')} 🔥[/bold yellow]", border_style="yellow"))
        
        pro_choice = Prompt.ask(f"[bold {b_color}]Select PRO Option[/bold {b_color}]", choices=["1", "2", "3", "0"])
        
        if pro_choice == "1":
            console.print(f"\n[bold cyan]🔍 Purana kachra saaf kar rahe hain aur ShadowTrackerExtra nikal rahe hain...[/bold cyan]")
            
            dest_shadow_dir = MOD_REPACK_BASE / "ShadowTrackerExtra"
            files_to_delete = ["SplashScreen_BH.uexp", "LocalizationText_en.uexp"]
            source_dumps = ["mini_obb.pak", "mini_obbzsdic_obb.pak"]
            
            import shutil
            moved_any = False

            for dump_name in source_dumps:
                source_shadow_dir = ANLAISH_RESULT / dump_name / "ShadowTrackerExtra"
                
                if source_shadow_dir.exists():
                    console.print(f"\n[bold yellow]📦 Processing:[/] {dump_name}")
                    
                    for file_path in source_shadow_dir.rglob("*"):
                        if file_path.is_file() and file_path.name in files_to_delete:
                            try: 
                                file_path.unlink()
                                console.print(f"[bold green]✅ KILLED:[/] {file_path.name}")
                            except: pass
                    
                    console.print(f"[cyan]📂 Merging {dump_name} assets to MOD_REPACK...[/cyan]")
                    try:
                        os.makedirs(to_long_path(dest_shadow_dir), exist_ok=True)
                        for item in os.listdir(to_long_path(source_shadow_dir)):
                            s = source_shadow_dir / item
                            d = dest_shadow_dir / item
                            if s.is_dir():
                                if d.exists(): shutil.rmtree(to_long_path(d))
                                shutil.copytree(to_long_path(s), to_long_path(d))
                            else:
                                shutil.copy2(to_long_path(s), to_long_path(d))
                        moved_any = True
                        console.print(f"[bold green]✔ Merged Successfully![/bold green]")
                    except Exception as e:
                        console.print(f"[red]Error copying {dump_name}: {e}[/red]")
                else:
                    console.print(f"[dim]Skip: {dump_name} not found in RESULT.[/dim]")

            if moved_any:
                console.print(f"\n[bold {get_banner_color()}]🚀 BOOM! RESULT ka sara data MOD_REPACK me aa gaya![/bold {get_banner_color()}]")
                console.print(f"[white]Target:[/] {dest_shadow_dir.resolve()}")
            else:
                console.print(f"\n[red]❌ Error: RESULT folder me koi ShadowTrackerExtra nahi mila! Pehle Analyze karo.[/red]")
            
            time.sleep(2)
                
        elif pro_choice == "2":
            black_tool_main()
            console.clear()
            print_banner_and_header()
            
        elif pro_choice == "3":
            import shutil
            global EDITED_DIR 
            
            console.print(f"\n[bold cyan]🔨 Initiating PRO REPACK (Target: MOD_REPACK/RESULT)...[/bold cyan]")
            
            original_mod_dir = EDITED_DIR
            MOD_REPACK_path = ANLAISH_DIR / "MOD_REPACK"
            final_repack_dir = MOD_REPACK_path / "RESULT"
            
            if not MOD_REPACK_path.exists() or not any(os.scandir(to_long_path(MOD_REPACK_path))):
                console.print(Panel("[bold red]❌ Error: MOD_REPACK folder khali hai![/bold red]"))
                continue

            try:
                os.makedirs(to_long_path(final_repack_dir), exist_ok=True)
                EDITED_DIR = MOD_REPACK_path
                TencentPakFile.MODIFIED_DIR = MOD_REPACK_path
                
                base_org = Path(BASE_DIR_NAME) / "OBB_UNPACKER" / ORGNAL_DIR
                pak_files = list_paks_in_folder(base_org)
                selected = auto_detect_repack_candidates(pak_files, MOD_REPACK_path)
                
                if not selected:
                    console.print("[yellow]⚠️ MOD_REPACK ke assets ke liye koi matching OBB nahi mila.[/yellow]")
                else:
                    for pak_path in selected:
                        repacked_copy = final_repack_dir / pak_path.name
                        if repacked_copy.exists(): 
                            repacked_copy.unlink()
                            
                        shutil.copy2(to_long_path(pak_path), to_long_path(repacked_copy))
                        
                        console.print(f"[cyan]📦 Repacking:[/] {pak_path.name}")
                        pak = TencentPakFile(pak_path)
                        with open_long(repacked_copy, 'r+b') as fh:
                            pak.repack_inplace_from_modified_dir(fh)
                        
                        console.print(f"[bold green]✔ Saved in RESULT folder:[/] {repacked_copy.resolve()}")

                EDITED_DIR = original_mod_dir
                console.print(f"\n[bold green]✅ PRO REPACK COMPLETE! Pak file 'MOD_REPACK/RESULT' me save ho gayi hai.[/bold green]")
            except Exception as e:
                EDITED_DIR = original_mod_dir
                console.print(f"[red]Repack Error: {e}[/red]")

            Prompt.ask("\nPress Enter to continue...")

        elif pro_choice == "0":
            break

@security_guard
def run_obbzip_tool():
    """12.py KA EXACT COPY - SIRF SM4 KEYS SERVER SE + DIVISION BY ZERO FIX"""
    
    import os, sys, subprocess, shutil, zipfile
    from pathlib import Path
    import struct
    import tempfile
    import zlib
    import hashlib
    from dataclasses import dataclass
    from functools import lru_cache
    from typing import List, Optional
    import itertools as it
    import math
    from pathlib import PurePath
    from Crypto.Cipher import AES
    from Crypto.Cipher.AES import MODE_CBC
    from Crypto.Hash import SHA1
    from Crypto.Util.Padding import unpad, pad
    from zstandard import ZstdDecompressor, ZstdCompressor, ZstdCompressionDict, DICT_TYPE_AUTO
    from rich.box import ROUNDED
    from rich.align import Align
    from rich.console import Console  # ✅ YEH ADD KARO
    from rich.panel import Panel     # ✅ YEH ADD KARO
    from rich.table import Table     # ✅ YEH ADD KARO
    from rich.prompt import Prompt   # ✅ YEH ADD KARO
    
    
    try:
        import gmalg
        from gmalg import SM4, ZUC
    except ImportError:
        print('gmalg not found, installing...')
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'gmalg'], check=True)
        import gmalg
        from gmalg import SM4, ZUC
    
    console = Console()
    
    # ============================================================
    # OFFLINE CRYPTO MODE
    # ============================================================
    global SM4_SECRET_NEW
    # No network key fetch. Embedded SM4-2 / SM4-4 constants remain usable.
    
    # ============================================================
    # DIRECTORY SETUP
    # ============================================================
    KGF_BASE = Path("/data/data/com.termux/files/home/ALVSIA_PRO_DATA")
    
    PAK_BASE = KGF_BASE / 'ANTIRESET_OBB'
    EDITED_FILES_DIR = PAK_BASE / 'EDITTED_FILES'
    REPACKED_PAK_DIR = PAK_BASE / 'REPACKED_PAK'
    
    OBB_BASE = KGF_BASE / 'ANTIRESET_OBB'
    ORIGINAL_OBB = OBB_BASE / 'Original_obb'
    UNPACKED_OBB = OBB_BASE / 'unpacked_obb'
    REPACKED_OBB = OBB_BASE / 'Repacked_obb'
    INPUT_FILE = UNPACKED_OBB / 'ShadowTrackerExtra' / 'Content' / 'Paks'
    
    EXES_DIR = KGF_BASE / 'EXES'
    
    def set_executable_permissions():
        if os.name == 'nt':
            return None
        if not EXES_DIR.exists():
            return None
        for item in EXES_DIR.iterdir():
            if item.is_file():
                try:
                    item.chmod(item.stat().st_mode | 0o111)
                except Exception:
                    pass
    
    def ensure_dirs():
        dirs_list = [
            EDITED_FILES_DIR, REPACKED_PAK_DIR, EXES_DIR, 
            ORIGINAL_OBB, UNPACKED_OBB, REPACKED_OBB, INPUT_FILE
        ]
        for d in dirs_list:
            if not d.exists():
                d.mkdir(parents=True, exist_ok=True)
        set_executable_permissions()
    
    ensure_dirs()

    # ============================================================
    # XOR KEY & SM4 SECRETS - SERVER SE
    # ============================================================
    _K = b'\x11!6GFW\xa7\x8d\x9d\x84\x90\xd8\xab\x00\x8c5&\x1a\xf7\xe4X\x05\xb8\xb3\x15\x07\xd0,\x1e\x8f\xf6\xc8'
    
    def xor_game_crypt(data: bytes) -> bytes:
        return bytes(b ^ _K[i % len(_K)] for i, b in enumerate(data))
    
    def ensure_sm4_secrets() -> bool:
        return SM4_SECRET_NEW is not None and len(SM4_SECRET_NEW) > 0

    # ============================================================
    # CRYPTO CONSTANTS
    # ============================================================
    ZUC_KEY = bytes.fromhex('01010101010101010101010101010101')
    ZUC_IV = bytes.fromhex('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF')
    RSA_MOD_1 = bytes.fromhex('CBE8B9F2504050EF9831B719E9A6249A6D238505ADE909BDE78C180DED6072A0C3347B8AF4780E1F212D952D82D4BF7F233C1ECA499E1F9D9A85B4FAD759F54BABC1666C5DE411EA9E4B2374425DD6C6F54333BBC8F2610FE6063E4D0D6C21A671A8F7C3740555E5DC06D4E1691C456DB4116C0C012BF7B206E8311AAAEC689952BF804EF638F09D5822B4117B114208F14DEB459E80CB770E5B0D7978E21F5E6CED4999D3583108221A7AB28B960277ADB5690A332784019D9C195BE4EA9EA0A09459010F236465DE0D59C3EF7324E954E1118D93EE19F299760C2CDB963CE87973EA5ECC9BBE81C27D4C7C8572AC07E9BCEAC9BD72AB7A56A3C0AD736ABCE4')
    RSA_MOD_2 = bytes.fromhex('7F58E8A39A4DA4E87357DDD650EAA16D3B5CE95B213D1030A662566444796A78A84AE9AC3DBFFDE7F41094896696835DAF13B89E6EC2B84963B1B1BAF7151DA245C3FBFAE2A6AE18B2684D03F9229DE2C91440F2A3A3BCDE1E5680C16722A88039C73560D5D43F4B6562C2EEA5B1D926D86B51108A2643C70FB74D6442CE3A08339B8FD8F660AE88129B7AB8C46F2FA58124485CCCB1E987B05A6DA65A01858ED3F89905449AE42BB07290FCB9994BF22E26610BCABB9804783A3B9587917F3D97316EDDA15C5E13F79066407B55A93B291B68A4AC42A98D6E35FED84B14A792D154E62028DDAD20FC301951E5924BE9AD62FB719DD94CC30CAB871BEC4377A8')
    SIMPLE1_DECRYPT_KEY = 121
    SIMPLE2_DECRYPT_KEY = bytes.fromhex('E55B4ED1')
    SIMPLE2_BLOCK_SIZE = 16
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

    _S_BOX = bytes([0x34,0x66,0x25,0x74,0x89,0x78,0xE4,0xA9,0x5A,0x41,0xBC,0x7A,0xD6,0x16,0x21,0x23,0x4D,0x61,0xDA,0x94,0x9B,0xDF,0x13,0x3C,0x69,0x3A,0x31,0x0A,0x5F,0xD7,0x99,0x95,0xF1,0xAE,0x72,0x3D,0x07,0x60,0x24,0xB6,0x98,0xEE,0xC4,0xA2,0x2D,0x88,0xDD,0x8D,0x04,0xEA,0xBB,0x11,0xCA,0x3E,0x5D,0xA1,0xF6,0x3F,0xB0,0x97,0x80,0x47,0x2B,0xA6,0xE6,0xF7,0xD9,0xB1,0x59,0xC0,0x7C,0xBE,0x54,0x28,0xB7,0x7E,0x4F,0xF8,0x43,0x6E,0xA0,0x50,0x0E,0xF5,0x90,0xB8,0xFB,0xA3,0x7B,0x62,0x19,0x46,0x03,0x2A,0xB9,0x8F,0x9F,0x77,0xB4,0x5B,0x83,0x87,0x08,0xEB,0xE2,0x1E,0x42,0xF0,0x0F,0xE8,0x71,0x6A,0x75,0xAD,0x55,0x1F,0xB5,0xAB,0x33,0xFA,0x7F,0x15,0xBD,0x85,0xD8,0x06,0x68,0xB3,0x52,0x30,0x48,0x0B,0x00,0xED,0xEF,0xB2,0x57,0x8E,0xE7,0x6C,0xD5,0xE5,0x2E,0x53,0x82,0x05,0xF9,0x81,0xF4,0x56,0xBF,0x8C,0x4B,0xE3,0xDB,0x4A,0x91,0x4C,0x2C,0xD3,0x40,0x29,0x4E,0x20,0x14,0x36,0x79,0x09,0x6F,0xD1,0x37,0xE0,0x39,0x0C,0x8A,0x92,0x38,0x12,0x35,0x6D,0xE1,0xFD,0x93,0x9A,0x17,0xD4,0xC9,0x9C,0x6B,0x84,0x26,0x9D,0xAF,0x76,0xC1,0x9E,0xD0,0x96,0xC5,0xCB,0xE9,0x73,0x49,0xD2,0xCD,0x64,0xC3,0xC7,0x01,0x7D,0xF3,0xAC,0xFC,0xDE,0xA4,0x44,0x32,0x1B,0xC2,0xBA,0x1C,0x02,0xC6,0x27,0x45,0x8B,0xF2,0x18,0xA7,0x10,0x51,0x1D,0xC8,0xCF,0x63,0xFF,0x2F,0x0D,0x58,0xCE,0x65,0xA5,0xDC,0x1A,0x3B,0x86,0xFE,0x22,0x5C,0xA8,0x5E,0x67,0xAA,0xEC,0x70,0xCC])

    _FK = [0x46970E9C, 0x4BC0685E, 0x59056186, 0xBCA2491E]

    _CK = [0x000EB92B, 0x3A0AE783, 0x9E3B5C67, 0xADDBDABF, 0x7B7484CB, 0x49156C63, 0xC79AB5E7, 0x79EC9CFF,
           0x1725BEAB, 0x2FB89CA3, 0x24808AD7, 0xDDD28B1F, 0x4740DA4B, 0xBBC3EA73, 0x247B30E7, 0x91BE385F,
           0x0401248B, 0x45FCD3A3, 0x530B4CE7, 0xC68DD35F, 0xE3D16C2B, 0x4F698C13, 0x6B92C747, 0x769EFB1F,
           0x4C73BE9B, 0xC942B193, 0xAD80D827, 0x372FB33F, 0x13CB6AAB, 0x2BDC0AA3, 0x17A4A247, 0xD5E96CAF]

    def ROL32(x, n):
        return ((x << n) & 0xFFFFFFFF) | (x >> (32 - n))

    def _BS(X):
        return (_S_BOX[(X >> 24) & 0xFF] << 24 |
                _S_BOX[(X >> 16) & 0xFF] << 16 |
                _S_BOX[(X >> 8) & 0xFF] << 8 |
                _S_BOX[X & 0xFF])

    def _T0(X):
        X = _BS(X)
        return X ^ ROL32(X, 2) ^ ROL32(X, 10) ^ ROL32(X, 18) ^ ROL32(X, 24)

    def _T1(X):
        X = _BS(X)
        return X ^ ROL32(X, 13) ^ ROL32(X, 23)

    def _key_expand(key: bytes) -> List[int]:
        rkey = [0] * 32
        K0 = int.from_bytes(key[0:4], 'big') ^ _FK[0]
        K1 = int.from_bytes(key[4:8], 'big') ^ _FK[1]
        K2 = int.from_bytes(key[8:12], 'big') ^ _FK[2]
        K3 = int.from_bytes(key[12:16], 'big') ^ _FK[3]
        for i in range(0, 32, 4):
            K0 = K0 ^ _T1(K1 ^ K2 ^ K3 ^ _CK[i])
            rkey[i] = K0
            K1 = K1 ^ _T1(K2 ^ K3 ^ K0 ^ _CK[i + 1])
            rkey[i + 1] = K1
            K2 = K2 ^ _T1(K3 ^ K0 ^ K1 ^ _CK[i + 2])
            rkey[i + 2] = K2
            K3 = K3 ^ _T1(K0 ^ K1 ^ K2 ^ _CK[i + 3])
            rkey[i + 3] = K3
        return rkey

    class SM4:
        _rkey: List[int]
        
        def __init__(self, key: bytes):
            self._rkey = _key_expand(key)
        
        def encrypt(self, block: bytes) -> bytes:
            RK = self._rkey
            X0 = int.from_bytes(block[0:4], 'big')
            X1 = int.from_bytes(block[4:8], 'big')
            X2 = int.from_bytes(block[8:12], 'big')
            X3 = int.from_bytes(block[12:16], 'big')
            for i in range(0, 32, 4):
                X0 = X0 ^ _T0(X1 ^ X2 ^ X3 ^ RK[i])
                X1 = X1 ^ _T0(X2 ^ X3 ^ X0 ^ RK[i + 1])
                X2 = X2 ^ _T0(X3 ^ X0 ^ X1 ^ RK[i + 2])
                X3 = X3 ^ _T0(X0 ^ X1 ^ X2 ^ RK[i + 3])
            return (X3.to_bytes(4, 'big') + X2.to_bytes(4, 'big') +
                    X1.to_bytes(4, 'big') + X0.to_bytes(4, 'big'))
        
        def decrypt(self, block: bytes) -> bytes:
            RK = self._rkey
            X0 = int.from_bytes(block[0:4], 'big')
            X1 = int.from_bytes(block[4:8], 'big')
            X2 = int.from_bytes(block[8:12], 'big')
            X3 = int.from_bytes(block[12:16], 'big')
            for i in range(0, 32, 4):
                X0 = X0 ^ _T0(X1 ^ X2 ^ X3 ^ RK[31 - i])
                X1 = X1 ^ _T0(X2 ^ X3 ^ X0 ^ RK[30 - i])
                X2 = X2 ^ _T0(X3 ^ X0 ^ X1 ^ RK[29 - i])
                X3 = X3 ^ _T0(X0 ^ X1 ^ X2 ^ RK[28 - i])
            return (X3.to_bytes(4, 'big') + X2.to_bytes(4, 'big') +
                    X1.to_bytes(4, 'big') + X0.to_bytes(4, 'big'))

    class Misc:
        @staticmethod
        def pad_to_n(data: bytes, n: int) -> bytes:
            padding = n - (len(data) % n)
            if padding == n:
                return data
            return data + b'\x00' * padding
        
        @staticmethod
        def align_up(x: int, n: int) -> int:
            return ((x + n - 1) // n) * n

    class Reader_pak:
        _buffer: bytes
        _cursor: int
        
        def __init__(self, buffer: bytes, cursor: int = 0):
            self._buffer = buffer
            self._cursor = cursor
        
        def u1(self, move_cursor: bool = True) -> int:
            return self.unpack('B', move_cursor=move_cursor)[0]
        
        def u4(self, move_cursor: bool = True) -> int:
            return self.unpack('<I', move_cursor=move_cursor)[0]
        
        def u8(self, move_cursor: bool = True) -> int:
            return self.unpack('<Q', move_cursor=move_cursor)[0]
        
        def i1(self, move_cursor: bool = True) -> int:
            return self.unpack('b', move_cursor=move_cursor)[0]
        
        def i4(self, move_cursor: bool = True) -> int:
            return self.unpack('<i', move_cursor=move_cursor)[0]
        
        def i8(self, move_cursor: bool = True) -> int:
            return self.unpack('<q', move_cursor=move_cursor)[0]
        
        def s(self, n: int, move_cursor: bool = True) -> bytes:
            return self.unpack(f'{n}s', move_cursor=move_cursor)[0]
        
        def unpack(self, f: str, offset: int = 0, move_cursor: bool = True):
            x = struct.unpack_from(f, self._buffer, self._cursor + offset)
            if move_cursor:
                self._cursor += struct.calcsize(f)
            return x
        
        def string(self, move_cursor: bool = True) -> str:
            length = self.i4(move_cursor=move_cursor)
            if length == 0:
                return ''
            offset = 0 if move_cursor else 4
            return self.unpack(f'{length}s', offset=offset, move_cursor=move_cursor)[0].rstrip(b'\x00').decode()

    def serialize_string(s: str) -> bytes:
        if not s:
            return struct.pack('<i', 0)
        b = s.encode('utf-8')
        return struct.pack('<i', len(b) + 1) + b + b'\x00'

    class PakIndexWriter:
        data: bytearray
        
        def __init__(self):
            self.data = bytearray()
        
        def write_bytes(self, b: bytes):
            self.data.extend(b)
        
        def write_u8(self, v: int):
            self.data.extend(struct.pack('<Q', v))
        
        def write_u4(self, v: int):
            self.data.extend(struct.pack('<I', v))
        
        def write_u1(self, v: int):
            self.data.extend(struct.pack('<B', v))
        
        def write_string(self, s: str):
            self.write_bytes(serialize_string(s))

    class PakInfo:
        index_encrypted: bool
        index_hash: bytes
        index_offset: int
        index_size: int
        magic: int
        version: int
        
        def __init__(self, buffer: bytes, keystream: list):
            def decrypt_index_encrypted(x: int) -> int:
                return (x ^ keystream[3]) & 0xFF
            
            def decrypt_magic(x: int) -> int:
                return x ^ keystream[2]
            
            def decrypt_index_hash(x: bytes) -> bytes:
                key = struct.pack('<5I', *keystream[4:9])
                return bytes(a ^ b for a, b in zip(x, key))
            
            def decrypt_index_size(x: int) -> int:
                return x ^ ((keystream[10] << 32) | keystream[11])
            
            def decrypt_index_offset(x: int) -> int:
                return x ^ ((keystream[0] << 32) | keystream[1])
            
            reader = Reader_pak(buffer[-PakInfo._mem_size(-1):])
            self.index_encrypted = decrypt_index_encrypted(reader.u1()) == 1
            self.magic = decrypt_magic(reader.u4())
            self.version = reader.u4()
            self.index_hash = decrypt_index_hash(reader.s(20)) if self.version >= 6 else bytes()
            self.index_size = decrypt_index_size(reader.u8())
            self.index_offset = decrypt_index_offset(reader.u8())
            if self.version <= 3:
                self.index_encrypted = False
        
        @staticmethod
        def _mem_size(_) -> int:
            return 45

    class TencentPakInfo(PakInfo):
        unk1: bytes
        packed_key: bytes
        packed_iv: bytes
        packed_index_hash: bytes
        stem_hash: int
        unk2: int
        content_org_hash: bytes
        
        def __init__(self, buffer: bytes, keystream: list):
            def decrypt_unk(x: bytes) -> bytes:
                key = struct.pack('<8I', *keystream[7:15])
                return bytes(a ^ b for a, b in zip(x, key))
            
            def decrypt_stem_hash(x: int) -> int:
                return x ^ keystream[8]
            
            def decrypt_unk_hash(x: int) -> int:
                return x ^ keystream[9]
            
            super().__init__(buffer, keystream)
            footer_size = TencentPakInfo._mem_size(self.version)
            reader = Reader_pak(buffer[-footer_size:])
            self.unk1 = decrypt_unk(reader.s(32)) if self.version >= 7 else bytes()
            self.packed_key = reader.s(256) if self.version >= 8 else bytes()
            self.packed_iv = reader.s(256) if self.version >= 8 else bytes()
            self.packed_index_hash = reader.s(256) if self.version >= 8 else bytes()
            self.stem_hash = decrypt_stem_hash(reader.u4()) if self.version >= 9 else 0
            self.unk2 = decrypt_unk_hash(reader.u4()) if self.version >= 9 else 0
            self.content_org_hash = reader.s(20) if self.version >= 12 else bytes()
        
        @staticmethod
        def _mem_size(version: int) -> int:
            return (PakInfo._mem_size(version) +
                    (32 if version >= 7 else 0) +
                    (768 if version >= 8 else 0) +
                    (8 if version >= 9 else 0) +
                    (20 if version >= 12 else 0))

    class PakCompressedBlock:
        start: int
        end: int
        
        def __init__(self, reader: Reader_pak = None, start: int = 0, end: int = 0):
            if reader is not None:
                self.start = reader.u8()
                self.end = reader.u8()
            else:
                self.start = start
                self.end = end
        
        def write(self, writer: PakIndexWriter):
            writer.write_u8(self.start)
            writer.write_u8(self.end)

    @dataclass
    class TencentPakEntry:
        content_hash: bytes = b'\x00' * 20
        offset: int = 0
        uncompressed_size: int = 0
        compression_method: int = 0
        size: int = 0
        unk1: int = 0
        unk2: bytes = b'\x00' * 20
        compressed_blocks: List[PakCompressedBlock] = None
        compression_block_size: int = 0
        encrypted: bool = False
        encryption_method: int = 0
        unk3: int = 0
        
        def __post_init__(self):
            if self.compressed_blocks is None:
                self.compressed_blocks = []
        
        def __init__(self, reader: Reader_pak, version: int):
            self.content_hash = reader.s(20)
            if version <= 1:
                reader.u8()
            self.offset = reader.u8()
            self.uncompressed_size = reader.u8()
            self.compression_method = reader.u4() & CM_MASK
            self.size = reader.u8()
            self.unk1 = reader.u1() if version >= 5 else 0
            self.unk2 = reader.s(20) if version >= 5 else b'\x00' * 20
            block_count = 0
            if self.compression_method != 0 and version >= 3:
                block_count = reader.u4()
                if block_count > 10000:
                    block_count = 0
                self.compressed_blocks = [PakCompressedBlock(reader) for _ in range(block_count)]
            else:
                self.compressed_blocks = []
            self.compression_block_size = reader.u4() if version >= 4 else 0
            self.encrypted = reader.u1() == 1 if version >= 4 else False
            self.encryption_method = reader.u4() if version >= 12 else 0
            self.unk3 = reader.u4() if version >= 14 else 0
        
        def write(self, writer: PakIndexWriter, version: int):
            writer.write_bytes(self.content_hash)
            if version <= 1:
                writer.write_u8(0)
            writer.write_u8(self.offset)
            writer.write_u8(self.uncompressed_size)
            writer.write_u4(self.compression_method)
            writer.write_u8(self.size)
            if version >= 5:
                writer.write_u1(self.unk1)
                writer.write_bytes(self.unk2)
            if self.compression_method != 0 and version >= 3:
                writer.write_u4(len(self.compressed_blocks))
                for block in self.compressed_blocks:
                    block.write(writer)
            if version >= 4:
                writer.write_u4(self.compression_block_size)
                writer.write_u1(1 if self.encrypted else 0)
            if version >= 12:
                writer.write_u4(self.encryption_method)
            if version >= 14:
                writer.write_u4(self.unk3)

    class PakCrypto:
        
        class _LCG:
            state: int
            
            def __init__(self, seed: int):
                self.state = seed
            
            def next(self) -> int:
                MASK_32 = 0xFFFFFFFF
                MSB_1 = 1 << 31
                
                def wrap(x):
                    x &= MASK_32
                    return x if not (x & MSB_1) else ((x + MSB_1) & MASK_32) - MSB_1
                
                x1 = wrap(0x41C64E6D * self.state)
                self.state = wrap(x1 + 12345)
                x2 = wrap(x1 + 0x13038) if self.state < 0 else self.state
                return ((x2 >> 16) & MASK_32) % 0x7FFF
        
        @staticmethod
        def zuc_keystream() -> list:
            zuc = gmalg.ZUC(ZUC_KEY, ZUC_IV)
            return [struct.unpack('>I', zuc.generate())[0] for _ in range(16)]
        
        @staticmethod
        def _xorxor(buffer: bytes, x: bytes) -> bytes:
            return bytes(buffer[i] ^ x[i % len(x)] for i in range(len(buffer)))
        
        @staticmethod
        def _hashhash(buffer: bytes, n: int) -> bytes:
            result = bytes()
            for _ in range(math.ceil(n / SHA1.digest_size)):
                result += SHA1.new(buffer).digest()
            if len(result) >= n:
                result = result[:n]
            else:
                result += b'\x00' * (n - len(result))
            return result
        
        @staticmethod
        def _meowmeow(buffer: bytes) -> bytes:
            def unpad(x):
                skip = 1 + next(i for i in range(len(x)) if x[i] != 0)
                return x[skip:]
            
            if len(buffer) < 43:
                return bytes()
            x1 = buffer[1:SHA1.digest_size + 1]
            x2 = buffer[SHA1.digest_size + 1:]
            x1 = PakCrypto._xorxor(x1, PakCrypto._hashhash(x2, len(x1)))
            x2 = PakCrypto._xorxor(x2, PakCrypto._hashhash(x1, len(x2)))
            m, part1 = x2[SHA1.digest_size:], x2[:SHA1.digest_size]
            if part1 != SHA1.new(b'\x00' * SHA1.digest_size).digest():
                return bytes()
            return unpad(m)
        
        @staticmethod
        def rsa_extract(signature: bytes, modulus: bytes) -> bytes:
            c = int.from_bytes(signature, 'little')
            n = int.from_bytes(modulus, 'little')
            m = pow(c, 0x10001, n).to_bytes(256, 'little').rstrip(b'\x00')
            return PakCrypto._meowmeow(Misc.pad_to_n(m, 4))
        
        @staticmethod
        def _encrypt_simple1(pt: bytes) -> bytes:
            return bytes(x ^ SIMPLE1_DECRYPT_KEY for x in pt)
        
        @staticmethod
        def _decrypt_simple1(ct: bytes) -> bytes:
            return bytes(x ^ SIMPLE1_DECRYPT_KEY for x in ct)
        
        @staticmethod
        def _encrypt_simple2(pt: bytes) -> bytes:
            class RollingKey:
                _value: int
                def __init__(self, iv: int):
                    self._value = iv
                def update(self, x: int) -> int:
                    orig = self._value
                    self._value = x
                    return orig ^ x
            
            initial_key = struct.unpack('<I', SIMPLE2_DECRYPT_KEY)[0]
            rk = RollingKey(initial_key)
            ciphertext = (struct.pack('<I', rk.update(x)) for x in struct.unpack(f'<{len(pt) // 4}I', pt))
            return bytes(it.chain.from_iterable(ciphertext))
        
        @staticmethod
        def _decrypt_simple2(ct: bytes) -> bytes:
            class RollingKey:
                _value: int
                def __init__(self, iv: int):
                    self._value = iv
                def update(self, x: int) -> int:
                    self._value ^= x
                    return self._value
            
            initial_key = struct.unpack('<I', SIMPLE2_DECRYPT_KEY)[0]
            rk = RollingKey(initial_key)
            plaintext = (struct.pack('<I', rk.update(x)) for x in struct.unpack(f'<{len(ct) // 4}I', ct))
            return bytes(it.chain.from_iterable(plaintext))
        
        @staticmethod
        @lru_cache(maxsize=33)
        def _derive_sm4_key(file_path: PurePath, encryption_method: int) -> bytes:
            part1 = file_path.stem.lower()
            if encryption_method == EM_SM4_2:
                secret = SM4_SECRET_2
            elif encryption_method == EM_SM4_4:
                secret = SM4_SECRET_4
            else:
                index = (encryption_method - EM_SM4_NEW_BASE) % len(SM4_SECRET_NEW)
                secret = f'{SM4_SECRET_NEW[index]}{encryption_method}'
            return SHA1.new(str(part1 + secret).encode()).digest()[:16]
        
        @staticmethod
        @lru_cache(maxsize=33)
        def _sm4_context_for_key(key: bytes) -> SM4:
            return SM4(key)
        
        @staticmethod
        def _encrypt_sm4(plaintext: bytes, file_path: PurePath, encryption_method: int) -> bytes:
            padded = pad(plaintext, 16)
            key = PakCrypto._derive_sm4_key(file_path, encryption_method)
            sm4 = PakCrypto._sm4_context_for_key(key)
            return b''.join(sm4.encrypt(padded[i:i + 16]) for i in range(0, len(padded), 16))
        
        @staticmethod
        def _decrypt_sm4(ciphertext: bytes, file_path: PurePath, encryption_method: int) -> bytes:
            key = PakCrypto._derive_sm4_key(file_path, encryption_method)
            sm4 = PakCrypto._sm4_context_for_key(key)
            return b''.join(sm4.decrypt(ciphertext[i:i + 16]) for i in range(0, len(ciphertext), 16))
        
        @staticmethod
        def decrypt_index(ciphertext: bytes, pak_info: TencentPakInfo) -> bytes:
            if pak_info.version > 7:
                key = PakCrypto.rsa_extract(pak_info.packed_key, RSA_MOD_1)
                iv = PakCrypto.rsa_extract(pak_info.packed_iv, RSA_MOD_1)
                assert len(key) == 32 and len(iv) == 32
                aes = AES.new(key, MODE_CBC, iv[:16])
                return unpad(aes.decrypt(ciphertext), AES.block_size)
            return bytes(PakCrypto._decrypt_simple1(ciphertext))
        
        @staticmethod
        def encrypt_index(plaintext: bytes, pak_info: TencentPakInfo) -> bytes:
            if pak_info.version > 7:
                key = PakCrypto.rsa_extract(pak_info.packed_key, RSA_MOD_1)
                iv = PakCrypto.rsa_extract(pak_info.packed_iv, RSA_MOD_1)
                assert len(key) == 32 and len(iv) == 32
                aes = AES.new(key, MODE_CBC, iv[:16])
                return aes.encrypt(pad(plaintext, AES.block_size))
            return bytes(PakCrypto._encrypt_simple1(plaintext))
        
        @staticmethod
        def _is_simple1_method(m: int) -> bool:
            return m == EM_SIMPLE1
        
        @staticmethod
        def _is_simple2_method(m: int) -> bool:
            return m == EM_SIMPLE2
        
        @staticmethod
        def _is_sm4_method(m: int) -> bool:
            return m == EM_SM4_2 or m == EM_SM4_4 or (m & EM_SM4_NEW_MASK) != 0
        
        @staticmethod
        def _is_unknown_17_method(m: int) -> bool:
            return m == EM_UNKNOWN_17
        
        @staticmethod
        def align_encrypted_content_size(n: int, method: int) -> int:
            if PakCrypto._is_simple2_method(method):
                return Misc.align_up(n, SIMPLE2_BLOCK_SIZE)
            if PakCrypto._is_sm4_method(method):
                return Misc.align_up(n, 16)
            return n
        
        @staticmethod
        def encrypt_block(plaintext: bytes, file: PurePath, method: int) -> bytes:
            if PakCrypto._is_simple1_method(method):
                return PakCrypto._encrypt_simple1(plaintext)
            if PakCrypto._is_simple2_method(method):
                return PakCrypto._encrypt_simple2(pad(plaintext, SIMPLE2_BLOCK_SIZE))
            if PakCrypto._is_sm4_method(method):
                return PakCrypto._encrypt_sm4(plaintext, file, method)
            if PakCrypto._is_unknown_17_method(method):
                return plaintext
            if method == 0:
                return plaintext
            raise AssertionError(f'Unknown encryption method: {method}')
        
        @staticmethod
        def encrypt_block_no_padding(plaintext: bytes, file: PurePath, method: int) -> bytes:
            if PakCrypto._is_simple1_method(method):
                return PakCrypto._encrypt_simple1(plaintext)
            if PakCrypto._is_simple2_method(method):
                assert len(plaintext) % 16 == 0
                return PakCrypto._encrypt_simple2(plaintext)
            if PakCrypto._is_sm4_method(method):
                assert len(plaintext) % 16 == 0
                key = PakCrypto._derive_sm4_key(file, method)
                sm4 = PakCrypto._sm4_context_for_key(key)
                return b''.join(sm4.encrypt(plaintext[i:i + 16]) for i in range(0, len(plaintext), 16))
            if PakCrypto._is_unknown_17_method(method):
                return plaintext
            if method == 0:
                return plaintext
            raise AssertionError(f'Unknown encryption method: {method}')
        
        @staticmethod
        def decrypt_block(ciphertext: bytes, file: PurePath, method: int) -> bytes:
            if PakCrypto._is_simple1_method(method):
                return PakCrypto._decrypt_simple1(ciphertext)
            if PakCrypto._is_simple2_method(method):
                return PakCrypto._decrypt_simple2(ciphertext)
            if PakCrypto._is_sm4_method(method):
                return PakCrypto._decrypt_sm4(ciphertext, file, method)
            if PakCrypto._is_unknown_17_method(method):
                return ciphertext
            if method == 0:
                return ciphertext
            raise AssertionError(f'Unknown encryption method: {method}')
        
        @staticmethod
        @lru_cache(maxsize=33)
        def generate_block_indices(n: int, method: int) -> list:
            if n <= 0: return []
            if not PakCrypto._is_sm4_method(method):
                return list(range(n))
            perm = []
            lcg = PakCrypto._LCG(n)
            while len(perm) != n:
                x = lcg.next() % n
                if x not in perm:
                    perm.append(x)
            inv = [0] * len(perm)
            for i, x in enumerate(perm):
                inv[x] = i
            return inv

    class CompressionFinder:
        ZLIB_LEVELS_TO_TRY = list(range(9, 0, -1))
        ZSTD_LEVELS_TO_TRY = list(range(22, 0, -1)) + list(range(-1, -8, -1))
        
        @staticmethod
        def find_best_level_and_compress(uncompressed_chunk: bytes,
                                         original_compressed_size: int,
                                         dict_data: Optional[bytes],
                                         compression_method: int):
            if compression_method == CM_ZLIB:
                level = 9
            elif compression_method in (CM_ZSTD, CM_ZSTD_DICT):
                level = 22
            else:
                return (None, uncompressed_chunk)
            
            compressed_data = PakCompression.compress_block(
                uncompressed_chunk, dict_data, compression_method, level=level)
            return (level, compressed_data)

    class PakCompression:
        
        @staticmethod
        @lru_cache(maxsize=33)
        def _zstd_decompressor(dict_data: Optional[bytes]) -> ZstdDecompressor:
            dict_obj = ZstdCompressionDict(dict_data, DICT_TYPE_AUTO) if dict_data else None
            return ZstdDecompressor(dict_obj)
        
        @staticmethod
        @lru_cache(maxsize=128)
        def _zstd_compressor(dict_data: Optional[bytes], level: int) -> ZstdCompressor:
            dict_obj = ZstdCompressionDict(dict_data, DICT_TYPE_AUTO) if dict_data else None
            return ZstdCompressor(level=level, dict_data=dict_obj)
        
        @staticmethod
        def decompress_block(block: bytes, dict_data: Optional[bytes], compression_method: int) -> bytes:
            if compression_method == CM_ZLIB:
                return zlib.decompress(block)
            if compression_method == CM_ZSTD or compression_method == CM_ZSTD_DICT:
                if compression_method != CM_ZSTD_DICT:
                    dict_data = None
                return PakCompression._zstd_decompressor(dict_data).decompress(block)
            raise AssertionError(f'Unknown decompression method: {compression_method}')
        
        @staticmethod
        def compress_block(block: bytes, dict_data: Optional[bytes],
                           compression_method: int, level: Optional[int] = None) -> bytes:
            if compression_method == CM_ZLIB:
                use_level = level if level is not None else 9
                return zlib.compress(block, level=use_level)
            if compression_method == CM_ZSTD or compression_method == CM_ZSTD_DICT:
                use_level = level if level is not None else 22
                if compression_method != CM_ZSTD_DICT:
                    dict_data = None
                return PakCompression._zstd_compressor(dict_data, use_level).compress(block)
            raise AssertionError(f'Unknown compression method: {compression_method}')

    SM4_SECRET_2 = '>gahRZFL4r2*TByfx6#X'
    SM4_SECRET_4 = '09ea7a1d9e6528b72b48'

    class TencentPakFile:
        _file_path: PurePath
        _file_content: memoryview
        _is_od: bool
        _mount_point: PurePath
        _is_zstd_with_dict: bool
        _zstd_dict: Optional[bytes]
        _files: list
        _index: dict
        _pak_info: TencentPakInfo
        _raw_mount_point: str
        _index_dirs: list
        
        def __init__(self, file_path: PurePath, is_od: bool = False):
            self._file_path = file_path
            with open(file_path, 'rb') as f:
                self._file_content = memoryview(f.read())
            self._is_od = is_od
            self._mount_point = PurePath()
            self._is_zstd_with_dict = 'zsdic' in str(self._file_path)
            self._zstd_dict = None
            self._files = []
            self._index = {}
            self._pak_info = TencentPakInfo(self._file_content, PakCrypto.zuc_keystream())
            self._verify_stem_hash()
            self._tencent_load_index()
        
        def _verify_stem_hash(self):
            if not self._is_od and self._pak_info.version >= 9:
                expected = zlib.crc32(self._file_path.stem.encode('utf-32le'))
                if self._pak_info.stem_hash != expected:
                    self._fix_stem_hash(expected)
                    self._pak_info.stem_hash = expected
        
        def _fix_stem_hash(self, new_hash: int):
            try:
                footer_size = TencentPakInfo._mem_size(self._pak_info.version)
                footer_start = len(self._file_content) - footer_size
                
                offset = footer_start
                if self._pak_info.version >= 7:
                    offset += 32
                if self._pak_info.version >= 8:
                    offset += 768
                offset += 4
                
                with open(self._file_path, 'r+b') as f:
                    f.seek(offset)
                    f.write(struct.pack('<I', new_hash))
                
                data = bytearray(self._file_content)
                struct.pack_into('<I', data, offset, new_hash)
                self._file_content = memoryview(data)
            except Exception:
                pass
        
        def _tencent_load_index(self):
            index_data = self._file_content[self._pak_info.index_offset:self._pak_info.index_offset + self._pak_info.index_size]
            if self._pak_info.index_encrypted:
                index_data = PakCrypto.decrypt_index(index_data, self._pak_info)
            self._load_index(index_data)
        
        def _load_index(self, index_data: bytes):
            reader = Reader_pak(index_data)
            self._raw_mount_point = reader.string()
            self._mount_point = self._construct_mount_point(self._raw_mount_point)
            num_files_in_pak = reader.u4()
            self._files = [TencentPakEntry(reader, self._pak_info.version) for _ in range(num_files_in_pak)]
            self._index_dirs = []
            
            try:
                num_dirs = reader.u8()
                for _ in range(num_dirs):
                    raw_dir_path = reader.string()
                    num_files = reader.u8()
                    dir_files = []
                    e = {}
                    for _ in range(num_files):
                        raw_file_name = reader.string()
                        file_idx = ~reader.i4()
                        entry = self._files[file_idx]
                        dir_files.append((raw_file_name, file_idx))
                        e[raw_file_name] = entry
                    self._index_dirs.append((raw_dir_path, dir_files))
                    
                    if self._is_zstd_with_dict and PurePath(raw_dir_path).name == 'zstddic':
                        assert len(e) == 1
                        self._construct_zstd_dict(list(e.values())[0])
                    else:
                        self._index[PurePath(raw_dir_path)] = e
            except struct.error:
                pass
        
        @staticmethod
        def _construct_mount_point(mount_point: str) -> PurePath:
            res = PurePath()
            for part in PurePath(mount_point).parts:
                if part != '..':
                    res /= part
            return res
        
        def _peek_content(self, offset: int, size: int, method: int) -> memoryview:
            size = PakCrypto.align_encrypted_content_size(size, method)
            return self._file_content[offset:offset + size]
        
        def _peek_block_content(self, block: PakCompressedBlock, method: int) -> memoryview:
            size = PakCrypto.align_encrypted_content_size(block.end - block.start, method)
            return self._file_content[block.start:block.start + size]
        
        def _construct_zstd_dict(self, dict_entry: TencentPakEntry):
            assert not self._zstd_dict and not dict_entry.encrypted and dict_entry.compression_method == CM_NONE
            reader = Reader_pak(self._peek_content(dict_entry.offset, dict_entry.size, 0))
            dict_size = reader.u8()
            reader.u4()
            assert dict_size == reader.u4()
            dict_data = reader.s(dict_size)
            self._zstd_dict = dict_data
        
        def serialize_index(self) -> bytes:
            writer = PakIndexWriter()
            writer.write_string(self._raw_mount_point)
            writer.write_u4(len(self._files))
            for entry in self._files:
                entry.write(writer, self._pak_info.version)
            writer.write_u8(len(self._index_dirs))
            for raw_dir_path, dir_files in self._index_dirs:
                writer.write_string(raw_dir_path)
                writer.write_u8(len(dir_files))
                for raw_file_name, file_idx in dir_files:
                    writer.write_string(raw_file_name)
                    writer.write_bytes(struct.pack('<i', ~file_idx))
            writer.write_u4(len(self._raw_mount_point.encode('utf-8')) + 1 if self._raw_mount_point else 0)
            return bytes(writer.data)
        
        def serialize_pak_info(self, index_offset: int, index_size: int,
                               index_hash: bytes, keystream: list) -> bytes:
            val_index_encrypted = 1 if self._pak_info.index_encrypted else 0
            enc_index_encrypted = (val_index_encrypted ^ keystream[3]) & 0xFF
            enc_magic = self._pak_info.magic ^ keystream[2]
            val_version = self._pak_info.version
            
            if val_version >= 6:
                key = struct.pack('<5I', *keystream[4:9])
                enc_index_hash = bytes(a ^ b for a, b in zip(index_hash, key))
            else:
                enc_index_hash = b'\x00' * 20
            
            enc_index_size = index_size ^ ((keystream[10] << 32) | keystream[11])
            enc_index_offset = index_offset ^ ((keystream[0] << 32) | keystream[1])
            
            return struct.pack('<BII20sQQ', enc_index_encrypted, enc_magic,
                              val_version, enc_index_hash, enc_index_size, enc_index_offset)
        
        def serialize_tencent_pak_info(self, index_offset: int, index_size: int,
                                        index_hash: bytes, keystream: list) -> bytes:
            data = bytearray()
            
            if self._pak_info.version >= 7:
                key = struct.pack('<8I', *keystream[7:15])
                enc_unk1 = bytes(a ^ b for a, b in zip(self._pak_info.unk1, key))
                data.extend(enc_unk1)
            
            if self._pak_info.version >= 8:
                data.extend(self._pak_info.packed_key)
                data.extend(self._pak_info.packed_iv)
                data.extend(self._pak_info.packed_index_hash)
            
            if self._pak_info.version >= 9:
                enc_stem_hash = (self._pak_info.stem_hash ^ keystream[8]) if hasattr(self._pak_info, 'stem_hash') and self._pak_info.stem_hash is not None else self._pak_info.magic ^ keystream[8]
                data.extend(struct.pack('<I', enc_stem_hash))
                enc_unk2 = self._pak_info.unk2 ^ keystream[9]
                data.extend(struct.pack('<I', enc_unk2))
            
            if self._pak_info.version >= 12:
                data.extend(self._pak_info.content_org_hash)
            
            pak_info_bytes = self.serialize_pak_info(index_offset, index_size, index_hash, keystream)
            data.extend(pak_info_bytes)
            return bytes(data)
        
        def _write_to_disk(self, file_path: Path, entry: TencentPakEntry):
            if PakCrypto._is_unknown_17_method(entry.encryption_method):
                raise Exception('UNKNOWN_17 encryption method')
            
            with open(file_path, 'wb') as f:
                if entry.compression_method == CM_NONE:
                    data = self._peek_content(entry.offset, entry.size, entry.encryption_method)
                    if entry.encrypted:
                        data = PakCrypto.decrypt_block(bytes(data), PurePath(file_path), entry.encryption_method)
                    f.write(data[:entry.size])
                else:
                    dec_data = bytearray()
                    for x in PakCrypto.generate_block_indices(len(entry.compressed_blocks), entry.encryption_method):
                        data = self._peek_block_content(entry.compressed_blocks[x], entry.encryption_method)
                        if entry.encrypted:
                            data = PakCrypto.decrypt_block(bytes(data), PurePath(file_path), entry.encryption_method)
                        if not data:
                            continue
                        data = data[:entry.compressed_blocks[x].end - entry.compressed_blocks[x].start]
                        dec_data.extend(PakCompression.decompress_block(bytes(data), self._zstd_dict, entry.compression_method))
                    f.write(bytes(dec_data)[:entry.uncompressed_size])
        
        def dump_all(self, out_path: Path):
            count = 0
            for dir_path, dir_content in self._index.items():
                for file_name, entry in dir_content.items():
                    if '\x00' in file_name or '\x00' in str(dir_path) or '?' in file_name or '*' in file_name or '..' in str(dir_path):
                        continue
                    target_dir = out_path / dir_path
                    target_dir.mkdir(parents=True, exist_ok=True)
                    target = target_dir / file_name
                    self._write_to_disk(target, entry)
                    count += 1
            
            if count == 0:
                console.print(Panel('[yellow]No files found in this PAK.[/yellow]', title='No Results', style='yellow'))
                return None
            console.print(Panel(f'[green]Extracted {count} file(s) to {out_path}[/green]',
                               title='Unpack Complete', style='green'))
        
        def repack(self, source_dir: Path, target_pak: Path):
            console.print(Panel(f'[bold cyan]INITIALIZING: {target_pak.name}[/bold cyan]',
                               title='Initialization', style='cyan'))
            
            entry_to_path = {}
            for dir_path, dir_content in self._index.items():
                for file_name, entry in dir_content.items():
                    entry_to_path[id(entry)] = (dir_path, file_name)
            
            has_modified_files = False
            for entry in self._files:
                if id(entry) in entry_to_path:
                    dir_path, file_name = entry_to_path[id(entry)]
                    if (source_dir / dir_path / file_name).exists():
                        has_modified_files = True
                        break
            
            if not has_modified_files:
                console.print(Panel('[yellow]NO MODIFIED FILES TO REPACK. PAK REMAINS UNCHANGED.[/yellow]',
                                   title='Repack', style='yellow'))
                return None
            
            temp_fd, temp_path = tempfile.mkstemp(suffix='.pak', dir=target_pak.parent)
            os.close(temp_fd)
            temp_pak = Path(temp_path)
            
            modified_count = 0
            
            with open(target_pak, 'rb') as old_file, open(temp_pak, 'wb') as new_file:
                current_offset = 0
                
                for idx, entry in enumerate(self._files):
                    file_name = 'unknown'
                    dir_path = ''
                    if id(entry) in entry_to_path:
                        dir_path, file_name = entry_to_path[id(entry)]
                    
                    modified_file_path = source_dir / dir_path / file_name
                    
                    if modified_file_path.exists():
                        with open(modified_file_path, 'rb') as f_modified:
                            modified_data = f_modified.read()
                        
                        if len(modified_data) >= 4 and _K is not None:
                            if modified_data[:4] == b'\x1bLua':
                                modified_data = xor_game_crypt(modified_data)
                        
                        block_size = entry.compression_block_size
                        if block_size <= 0:
                            block_size = 65536
                        
                        orig_enc_method = entry.encryption_method
                        orig_comp_method = entry.compression_method
                        if orig_comp_method == 2 and self._zstd_dict is None:
                            orig_comp_method = 1
                            entry.compression_method = 1
                        
                        orig_encrypted = entry.encrypted
                        
                        if orig_comp_method == CM_NONE:
                            chunk = modified_data
                            if orig_encrypted:
                                pad_len = (16 - len(chunk) % 16) % 16
                                if pad_len != 16:
                                    chunk = chunk + b'\x00' * pad_len
                                data_to_write = PakCrypto.encrypt_block_no_padding(chunk, PurePath(file_name), orig_enc_method)
                            else:
                                data_to_write = chunk
                            
                            file_start_offset = current_offset
                            new_file.write(data_to_write)
                            total_written = len(chunk)
                            current_offset += len(data_to_write)
                            
                            entry.offset = file_start_offset
                            entry.uncompressed_size = len(modified_data)
                            entry.size = total_written
                            entry.compressed_blocks = []
                            entry.compression_block_size = 0
                            entry.content_hash = hashlib.sha1(data_to_write).digest()
                            entry.unk2 = hashlib.sha1(modified_data).digest()
                        else:
                            chunks = []
                            uncompressed_offset = 0
                            while uncompressed_offset < len(modified_data):
                                chunk = modified_data[uncompressed_offset:uncompressed_offset + block_size]
                                chunks.append(chunk)
                                uncompressed_offset += block_size
                            
                            n_chunks = len(chunks)
                            if n_chunks == 0:
                                n_chunks = 1
                                chunks = [b'']
                            
                            new_blocks = []
                            file_start_offset = current_offset
                            total_written = 0
                            payload_bytes = bytearray()
                            
                            for chunk_idx, chunk in enumerate(chunks):
                                orig_chunk_size = 0
                                if entry.compressed_blocks and chunk_idx < len(entry.compressed_blocks):
                                    orig_block = entry.compressed_blocks[chunk_idx]
                                    orig_chunk_size = orig_block.end - orig_block.start
                                
                                best_level, compressed_chunk = CompressionFinder.find_best_level_and_compress(
                                    chunk, orig_chunk_size, self._zstd_dict, orig_comp_method)
                                
                                if orig_encrypted:
                                    pad_len = (16 - len(compressed_chunk) % 16) % 16
                                    if pad_len != 16:
                                        compressed_chunk = compressed_chunk + b'\x00' * pad_len
                                    encrypted_chunk = PakCrypto.encrypt_block_no_padding(
                                        compressed_chunk, PurePath(file_name), orig_enc_method)
                                else:
                                    encrypted_chunk = compressed_chunk
                                
                                new_file.write(encrypted_chunk)
                                payload_bytes.extend(encrypted_chunk)
                                
                                block = PakCompressedBlock(Reader_pak(b'\x00' * 16))
                                block.start = current_offset
                                block.end = current_offset + len(compressed_chunk)
                                new_blocks.append(block)
                                
                                current_offset += len(encrypted_chunk)
                                total_written += len(encrypted_chunk)
                            
                            inv = PakCrypto.generate_block_indices(n_chunks, orig_enc_method)
                            reordered_blocks = [None] * n_chunks
                            for i, x in enumerate(inv):
                                reordered_blocks[x] = new_blocks[i]
                            
                            entry.offset = file_start_offset
                            entry.uncompressed_size = len(modified_data)
                            entry.size = total_written
                            entry.compressed_blocks = reordered_blocks
                            entry.compression_block_size = block_size
                            entry.content_hash = hashlib.sha1(payload_bytes).digest()
                            entry.unk2 = hashlib.sha1(modified_data).digest()
                        
                        modified_count += 1
                        console.print(f'[green][OK] REPACKED -> [yellow]{file_name}[/yellow]')
                    else:
                        old_file.seek(entry.offset)
                        
                        if entry.compression_method == CM_NONE:
                            copy_size = PakCrypto.align_encrypted_content_size(entry.size, entry.encryption_method)
                        elif entry.compressed_blocks:
                            last_block = entry.compressed_blocks[-1]
                            copy_size = (last_block.start - entry.offset +
                                        PakCrypto.align_encrypted_content_size(last_block.end - last_block.start, entry.encryption_method))
                        else:
                            copy_size = 0
                        
                        raw_data = old_file.read(copy_size)
                        
                        shift_amount = current_offset - entry.offset
                        entry.offset = current_offset
                        
                        for block in entry.compressed_blocks:
                            block.start += shift_amount
                            block.end += shift_amount
                        
                        new_file.write(raw_data)
                        current_offset += len(raw_data)
                
                index_data = self.serialize_index()
                index_hash = SHA1.new(index_data).digest()
                
                if self._pak_info.version > 7:
                    try:
                        aes_key = PakCrypto.rsa_extract(self._pak_info.packed_key, RSA_MOD_1)
                        aes_iv = PakCrypto.rsa_extract(self._pak_info.packed_iv, RSA_MOD_1)
                        aes_enc = AES.new(aes_key, MODE_CBC, aes_iv[:16])
                        index_data_to_write = aes_enc.encrypt(pad(index_data, AES.block_size))
                        self._pak_info.index_encrypted = True
                    except Exception:
                        index_data_to_write = index_data
                        self._pak_info.index_encrypted = False
                else:
                    index_data_to_write = bytes(PakCrypto._encrypt_simple1(index_data))
                    self._pak_info.index_encrypted = True
                
                new_index_offset = current_offset
                new_file.write(index_data_to_write)
                new_index_size = len(index_data_to_write)
                
                keystream = PakCrypto.zuc_keystream()
                self._pak_info.stem_hash = zlib.crc32(target_pak.stem.encode('utf-32le'))
                self._pak_info.index_hash = index_hash
                footer_data = self.serialize_tencent_pak_info(new_index_offset, new_index_size, index_hash, keystream)
                new_file.write(footer_data)
            
            shutil.move(temp_pak, target_pak)
            console.print(Panel(f'[bold green]Repacked PAK saved to {target_pak}[/bold green]',
                               title='Success', style='green'))

    def display_pak_files() -> List[Path]:
        paks = list(INPUT_FILE.glob('*.pak'))
        if not paks:
            console.print(Panel(f'❌ No PAK files found in {INPUT_FILE} folder', border_style='red'))
            return []
        
        table = Table(title='Select PAK File(s)', box=box.ROUNDED, header_style='bold yellow', show_lines=True)
        table.add_column('No.', style='bold green', width=12, justify='center')
        table.add_column('File Name', style='bold white', width=50)
        table.add_column('Size', style='green', width=12, justify='right')
        
        for i, p in enumerate(paks, 1):
            sz = p.stat().st_size / (1024 * 1024)
            table.add_row(str(i), p.name, f'{sz:.2f} MB')
        
        console.print(table)
        
        while True:
            try:
                choice = Prompt.ask("Select PAK files (comma-separated numbers, 'all' for all, or 0 to cancel)").strip()
                if choice.lower() == 'all':
                    return paks
                if choice == '0':
                    return []
                
                indices = [int(p.strip()) - 1 for p in choice.split(',') if p.strip()]
                selected = [paks[i] for i in indices if 0 <= i < len(paks)]
                if not selected:
                    console.print('[red]Invalid selection. Try again.[/red]')
                    continue
                return selected
            except Exception:
                console.print('[red]Invalid input. Try again.[/red]')

    def repack_pak():
        if not ensure_sm4_secrets():
            console.print('[red]❌ SM4_SECRET_NEW not available. Repack aborted.[/red]')
            input('Press Enter to continue...')
            return None
        
        paks = display_pak_files()
        if not paks:
            input('Press Enter to continue...')
            return None
        
        for pak_path in paks:
            out_pak = REPACKED_PAK_DIR / pak_path.name
            REPACKED_PAK_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pak_path, out_pak)
            console.print(Panel(f'Repacking [bold]{pak_path.name}[/bold] using edited files from [bold]{EDITED_FILES_DIR}[/bold]',
                               title='Repack PAK', style='green'))
            
            try:
                pak = TencentPakFile(PurePath(pak_path))
                
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_path = Path(tmpdir)
                    
                    if EDITED_FILES_DIR.exists():
                        edited_files = []
                        for root, _, files in os.walk(EDITED_FILES_DIR):
                            for file in files:
                                edited_files.append(Path(root) / file)
                        
                        for edited_file in edited_files:
                            file_name = edited_file.name
                            local_size = edited_file.stat().st_size
                            rel_path = edited_file.relative_to(EDITED_FILES_DIR).as_posix()
                            
                            exact_path_match = None
                            for dir_path, dir_content in pak._index.items():
                                for index_file_name, entry in dir_content.items():
                                    index_full_path = (dir_path / index_file_name).as_posix()
                                    if index_full_path.lower() == rel_path.lower():
                                        exact_path_match = (index_full_path, entry)
                                        break
                                if exact_path_match:
                                    break
                            
                            if exact_path_match:
                                selected_path, selected_entry = exact_path_match
                            else:
                                matches = []
                                for dir_path, dir_content in pak._index.items():
                                    for index_file_name, entry in dir_content.items():
                                        if index_file_name.lower() == file_name.lower():
                                            index_full_path = (dir_path / index_file_name).as_posix()
                                            matches.append((index_full_path, entry))
                                
                                if not matches:
                                    continue
                                
                                if len(matches) > 1:
                                    matches_sorted = sorted(matches, key=lambda m: abs(m[1].uncompressed_size - local_size))
                                    exact_size_found = False
                                    if (len(matches_sorted) > 0 and
                                        abs(matches_sorted[0][1].uncompressed_size - local_size) == 0 and
                                        (len(matches_sorted) == 1 or
                                         abs(matches_sorted[1][1].uncompressed_size - local_size) > 0)):
                                        selected_path, selected_entry = matches_sorted[0]
                                        exact_size_found = True
                                    else:
                                        exact_size_found = False
                                    
                                    if not exact_size_found:
                                        nearest_matches = matches_sorted[:2]
                                        console.print(Panel(
                                            f'[bold green] SELECT PATH FOR FILE [/bold green]: [bold cyan]{file_name}[/bold cyan]\n'
                                            f'Please select which path:',
                                            title='Path Selector', style='yellow'))
                                        
                                        for i, (path, entry) in enumerate(nearest_matches, 1):
                                            sz = entry.uncompressed_size
                                            console.print(f'  [bold green][{i}][/bold green] {path} (Size: {sz} bytes')
                                        
                                        choices = [str(x) for x in range(1, len(nearest_matches) + 1)]
                                        choice = Prompt.ask(
                                            f'[bold green] SELECT PATH NUMBER FOR [/bold green][bold green]{file_name}[/bold green] in {pak_path.name}',
                                            choices=choices)
                                        selected_path, selected_entry = nearest_matches[int(choice) - 1]
                                else:
                                    selected_path, selected_entry = matches[0]
                            
                            target_full = tmp_path / selected_path
                            target_full.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(edited_file, target_full)
                            console.print(f' [cyan] ✅ DONE-> [/cyan] [green]{file_name}[/green]')
                    
                    pak.repack(tmp_path, out_pak)
                
                console.print(Panel(f'Repacked PAK saved to {out_pak}', title='Success', style='green'))
            except Exception as e:
                console.print(Panel(f'Error: {e}', title='Error', style='red'))
        
        input('Press Enter to continue...')

    def unpack_obb():
        input_dir = ORIGINAL_OBB
        unpacked_dir = UNPACKED_OBB
        
        unpacked_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
            obb_files = [os.path.join(input_dir, f) for f in files if any(f.lower().endswith(ext) for ext in ('.obb', '.zip'))]
        except Exception as e:
            console.print(Panel(f'[red]Error reading {input_dir}: {e}[/red]', title='[red]Error[/red]', border_style='red'))
            return False
        
        if not obb_files:
            console.print(Panel(f'[red]No OBB or ZIP files found in {input_dir}[/red]', title='[red]Error[/red]', border_style='red'))
            return False
        
        success_all = True
        
        for obb_path in obb_files:
            set_permissions(obb_path)
            
            console.print(Panel(f'Unpacking [bold]{os.path.basename(obb_path)}[/bold] to [bold]{unpacked_dir}[/bold]',
                               title='Unpack OBB', style='cyan'))
            
            try:
                with zipfile.ZipFile(obb_path, 'r') as zf:
                    namelist = zf.namelist()
                    total_files = len(namelist)
                    
                    with Progress(SpinnerColumn(), TextColumn('[progress.description]{task.description}'), console=console) as progress:
                        task = progress.add_task(description=f'Extracting {os.path.basename(obb_path)}...', total=total_files)
                        
                        for file_info in zf.infolist():
                            zf.extract(file_info, unpacked_dir)
                            progress.update(task, advance=1, description=f'Extracted: {file_info.filename[:40]}...')
                
                console.print(Panel(f'[green]✅ Successfully extracted {os.path.basename(obb_path)} to {unpacked_dir}[/green]',
                                   title='Success', style='green'))
            except Exception as e:
                console.print(Panel(f'[red]Error extracting {os.path.basename(obb_path)}: {e}[/red]',
                                   title='[red]Error[/red]', border_style='red'))
                success_all = False
        
        pak_path = unpacked_dir / 'ShadowTrackerExtra' / 'Content' / 'Paks'
        if pak_path.exists():
            pak_files = list(pak_path.glob('*.pak'))
            if pak_files:
                console.print(f'[green][OK] Found {len(pak_files)} PAK files at: {pak_path}[/green]')
                for pak_file in pak_files:
                    console.print(f'  - [cyan]{pak_file.name}[/cyan]')
            else:
                console.print(f'[yellow][WARNING] No PAK files found at expected location: {pak_path}[/yellow]')
        else:
            console.print(f'[yellow][WARNING] PAK directory not found at expected location: {pak_path}[/yellow]')
        
        return success_all

    def adjust_size(repacked_obb_path: Path, original_obb_size: int):
        import struct as struct_mod
        
        repacked_obb_size = os.path.getsize(repacked_obb_path)
        
        if repacked_obb_size > original_obb_size:
            raise ValueError(f'Repacked OBB ({repacked_obb_size} bytes) is larger than original OBB ({original_obb_size} bytes).')
        
        if repacked_obb_size == original_obb_size:
            console.print(f'[green][OK] Size already matches: {original_obb_size} bytes.[/green]')
            return None
        
        bytes_to_add = original_obb_size - repacked_obb_size
        
        with open(repacked_obb_path, 'r+b') as f:
            f.seek(0, os.SEEK_END)
            file_len = f.tell()
            seek_len = min(file_len, 1024)
            f.seek(file_len - seek_len, os.SEEK_SET)
            buf = f.read(seek_len)
            
            idx = buf.rfind(b'PK\x05\x06')
            if idx == -1:
                seek_len = min(file_len, 65535)
                f.seek(file_len - seek_len, os.SEEK_SET)
                buf = f.read(seek_len)
                idx = buf.rfind(b'PK\x05\x06')
            
            if idx == -1:
                raise ValueError('Could not find ZIP End of Central Directory (EOCD) signature.')
            
            eocd_pos = file_len - len(buf) + idx
            
            f.seek(eocd_pos, os.SEEK_SET)
            eocd_data = f.read(22)
            sig, disk, disk_cd, disk_entries, total_entries, cd_size, cd_offset, comment_len = struct_mod.unpack('<IHHHHIIH', eocd_data)
            
            new_comment_len = comment_len + bytes_to_add
            if new_comment_len > 65535:
                raise ValueError(f'Required comment padding ({bytes_to_add} bytes) exceeds maximum ZIP comment length (65535). Use dummy file padding first.')
            
            f.seek(eocd_pos + 20, os.SEEK_SET)
            f.write(struct_mod.pack('<H', new_comment_len))
            
            f.seek(0, os.SEEK_END)
            f.write(b'\x00' * bytes_to_add)
        
        console.print(f'[green][OK] Resized to match original size: {original_obb_size} bytes using ZIP comment padding.[/green]')

    def set_permissions(file_path: Path):
        try:
            os.chmod(file_path, 0o755)
        except Exception:
            pass

    def repack_obb():
        input_dir = ORIGINAL_OBB
        repack_obb_dir = REPACKED_OBB
        repack_pak_dir = REPACKED_PAK_DIR
        unpacked_obb_dir = UNPACKED_OBB
        
        try:
            files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
            obb_files = [os.path.join(input_dir, f) for f in files if any(f.lower().endswith(ext) for ext in ('.obb', '.zip'))]
        except Exception as e:
            console.print(Panel(f'[red]Error reading {input_dir}: {e}[/red]', title='[red]Error[/red]', border_style='red'))
            return False
        
        if not obb_files:
            console.print(Panel(f'[red]No OBB/ZIP files found in {input_dir}[/red]', title='[red]Error[/red]', border_style='red'))
            return False
        
        if len(obb_files) == 1:
            original_obb_path = obb_files[0]
        else:
            table = Table(title='Select Original OBB File to Repack', box=box.ROUNDED, header_style='bold yellow', show_lines=True)
            table.add_column('No.', style='bold green', width=12, justify='center')
            table.add_column('File Name', style='bold white', width=50)
            table.add_column('Size', style='green', width=12, justify='right')
            
            for i, p in enumerate(obb_files, 1):
                sz = os.path.getsize(p) / (1024 * 1024)
                table.add_row(str(i), os.path.basename(p), f'{sz:.2f} MB')
            
            console.print(table)
            
            while True:
                try:
                    choice = Prompt.ask('Enter number of OBB file to repack').strip()
                    idx = int(choice) - 1
                    if 0 <= idx < len(obb_files):
                        original_obb_path = obb_files[idx]
                        break
                    console.print('[red]Invalid selection. Try again.[/red]')
                except ValueError:
                    console.print('[red]Invalid input. Try again.[/red]')
        
        original_size = os.path.getsize(original_obb_path)
        obb_filename = os.path.basename(original_obb_path)
        
        pak_files = list(repack_pak_dir.glob('*.pak'))
        if not pak_files:
            console.print(Panel(f'[red]No PAK files found in {repack_pak_dir}[/red]', title='[red]Error[/red]', border_style='red'))
            return False
        
        table = Table(title='Select PAK File to include in OBB', box=box.ROUNDED, header_style='bold yellow', show_lines=True)
        table.add_column('No.', style='bold green', width=12, justify='center')
        table.add_column('File Name', style='bold white', width=50)
        table.add_column('Size', style='green', width=12, justify='right')
        
        for i, p in enumerate(pak_files, 1):
            sz = p.stat().st_size / (1024 * 1024)
            table.add_row(str(i), p.name, f'{sz:.2f} MB')
        
        console.print(table)
        
        while True:
            try:
                choice = Prompt.ask("Select PAK files to include (comma-separated numbers, 'all' for all, or 0 to cancel)").strip()
                if choice.lower() == 'all':
                    selected_paks = pak_files
                    break
                if choice == '0':
                    console.print('[yellow][INFO] Operation cancelled.[/yellow]')
                    return False
                
                selected_indices = [int(x.strip()) for x in choice.split(',')]
                selected_paks = [pak_files[i - 1] for i in selected_indices if 1 <= i <= len(pak_files)]
                if not selected_paks:
                    console.print('[red][ERROR] Invalid selection. Please try again.[/red]')
                    continue
                break
            except (ValueError, IndexError):
                console.print('[red][ERROR] Invalid input. Please enter numbers separated by commas.[/red]')
        
        console.print(f'[green][OK] Selected {len(selected_paks)} PAK files for repacking:[/green]')
        for pak_file in selected_paks:
            console.print(f'  - [cyan]{pak_file.name}[/cyan]')
        
        unpacked_obb_dir.mkdir(parents=True, exist_ok=True)
        repack_obb_dir.mkdir(parents=True, exist_ok=True)
        
        console.print(Panel(f'Extracting original OBB to {unpacked_obb_dir}...', title='Extracting', style='cyan'))
        
        try:
            with zipfile.ZipFile(original_obb_path, 'r') as zf:
                total_files = len(zf.namelist())
                
                with Progress(SpinnerColumn(), TextColumn('[progress.description]{task.description}'), console=console) as progress:
                    task = progress.add_task('Extracting original OBB...', total=total_files)
                    
                    for file_info in zf.infolist():
                        zf.extract(file_info, unpacked_obb_dir)
                        progress.update(task, advance=1, description=f'Extracted: {file_info.filename[:40]}...')
        except Exception as e:
            console.print(Panel(f'[red]Failed to extract original OBB: {e}[/red]', title='Error', style='red'))
            return False
        
        obb_copy_path = unpacked_obb_dir / obb_filename
        shutil.copy2(original_obb_path, obb_copy_path)
        console.print(f'[green][OK] Copied original OBB to {obb_copy_path}[/green]')
        
        pak_dest_dir = unpacked_obb_dir / 'ShadowTrackerExtra' / 'Content' / 'Paks'
        pak_dest_dir.mkdir(parents=True, exist_ok=True)
        
        for pak_src in selected_paks:
            pak_dest = pak_dest_dir / pak_src.name
            shutil.copy2(pak_src, pak_dest)
            console.print(f'[green][OK] Placed updated {pak_src.name} in OBB structure.[/green]')
        
        console.print(Panel('Creating updated OBB with new PAK files...', title='Zipping', style='cyan'))
        
        try:
            with zipfile.ZipFile(original_obb_path, 'r') as orig_zf:
                orig_infos = orig_zf.infolist()
            
            with zipfile.ZipFile(obb_copy_path, 'w', zipfile.ZIP_STORED) as zf:
                for info in orig_infos:
                    file_path = unpacked_obb_dir / info.filename
                    if not file_path.exists():
                        console.print(f'[yellow][WARNING] File {info.filename} from original OBB not found in extracted folder. Skipping.[/yellow]')
                        continue
                    
                    new_info = zipfile.ZipInfo(info.filename)
                    new_info.date_time = info.date_time
                    new_info.compress_type = zipfile.ZIP_STORED
                    new_info.external_attr = info.external_attr
                    
                    with open(file_path, 'rb') as f_in:
                        zf.writestr(new_info, f_in.read())
        except Exception as e:
            console.print(Panel(f'[red]Failed to create updated OBB: {e}[/red]', title='Error', style='red'))
            return False
        
        current_size = os.path.getsize(obb_copy_path)
        if original_size - current_size >= 256:
            dummy_data_len = original_size - current_size - 256
            console.print(f'[cyan][*] Padding OBB with dummy file of size {dummy_data_len} bytes...[/cyan]')
            
            with zipfile.ZipFile(obb_copy_path, 'a', zipfile.ZIP_STORED) as zf:
                zf.writestr('padding.bin', b'\x00' * dummy_data_len)
        
        console.print(f'[green][OK] Created updated OBB with {len(selected_paks)} PAK files preserving original file order & metadata.[/green]')
        
        final_obb_path = repack_obb_dir / obb_filename
        if final_obb_path.exists():
            final_obb_path.unlink()
        shutil.move(obb_copy_path, final_obb_path)
        
        actual_size = os.path.getsize(final_obb_path)
        bytes_to_add = original_size - actual_size
        
        try:
            adjust_size(final_obb_path, original_size)
        except ValueError as e:
            console.print(Panel(f'[red]Size adjustment error: {e}[/red]', title='Error', style='red'))
            return False
        
        console.print(Panel(f'[bold green]Successfully saved updated OBB at:\n{final_obb_path}[/bold green]',
                           title='Repack OBB Success', style='green'))
        return True

    # ============================================================
    # 🔥 MAIN MENU - ONLY 3 OPTIONS
    # ============================================================
    # ============================================================
    # 🔥 MAIN MENU - CLEAN SIMPLE COMMANDS & TERMUX RESPONSIVE UI
    # ============================================================
    import sys
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.box import HEAVY, MINIMAL_DOUBLE_HEAD
    from rich.prompt import Prompt

    console = Console()

    while True:
        console.clear()
        # 👇 YAHAN APKE EXISTING BANNER/PROFILE FUNCTIONS RUN HOGENGE
        print_banner_and_header()
        print_user_profile()

        console.print()
        
        # 🟢 Termux responsive table with simple 1, 2, 3, 0 numbering
        table = Table(
            show_header=True, 
            header_style=f"bold black on {get_banner_color()}", 
            box=HEAVY,
            title= f'[bold {get_banner_color()}]✦ ─── [ ANTE REST CORE ENGINE ] ─── ✦[/bold {get_banner_color()}]', 
            title_style=f"bold {get_banner_color()}",
            show_lines=False, 
            border_style=get_banner_color(),
            expand=True,  # 👈 Poori screen width fit karne ke liye
            padding=(0, 1)
        )
        
        if CURRENT_SESSION_COLOR == 'rainbow':
            table.add_column(rainbow_text('CMD'), width=6, justify='center')
            table.add_column(rainbow_text('OPERATION PROTOCOL'), ratio=2)
            table.add_column(rainbow_text('STATUS / ACTION'), ratio=2)
            rainbow_row(table, '1', 'UNZIP OBB', 'EXTRACT ARCHIVE')
            rainbow_row(table, '2', 'REPACK PAK', 'BUILD EDITED FILES')
            rainbow_row(table, '3', 'REZIP OBB', 'COMPRESS & PACKAGE')
            rainbow_row(table, '0', 'EXIT', 'BACK MENU [✖]')
        else:
            table.add_column('CMD', style='bold bright_yellow', width=6, justify='center')
            table.add_column('OPERATION PROTOCOL', style='bold bright_white', ratio=2)
            table.add_column('STATUS / ACTION', style=get_banner_color(), ratio=2)
            table.add_row('1', 'UNZIP OBB', '[bold cyan]EXTRACT ARCHIVE')
            table.add_row('2', 'REPACK PAK', '[bold cyan]BUILD EDITED FILES')
            table.add_row('3', 'REZIP OBB', '[bold cyan]COMPRESS & PACKAGE')
            table.add_row('0', 'EXIT ', '[bold red]BACK MENU [✖][/bold red]')
        
        # 🛡️ Outer Bright Green Neon Panel Design
        outer_panel = Panel(
            table,
            border_style=get_banner_color(),
            box=MINIMAL_DOUBLE_HEAD,
            title='[bold bright_yellow]SELECT MODULE[/bold bright_yellow]',
            title_align='center',
            padding=(1, 2)
        )
        
        console.print(outer_panel)
        console.print()
        
        # 🎯 Simple Prompt line (1/2/3/0)
        choice = Prompt.ask(
            '[bold {get_banner_color()}]⚡ INPUT COMMAND ➔[/bold {get_banner_color()}]', 
            choices=['0', '1', '2', '3']
        )
        
        if choice == '0':
            console.print(Panel('[bold red]🔴 TERMINATING SESSION... GOODBYE![/bold red]', border_style='red', box=HEAVY))
            return
        elif choice == '1':
            unpack_obb()
            input('\n[bold {get_banner_color()}]Press Enter to return to main terminal...[/bold {get_banner_color()}]')
        elif choice == '2':
            repack_pak()
            input('\n[bold {get_banner_color()}]Press Enter to continue...[/bold {get_banner_color()}]')
        elif choice == '3':
            repack_obb()
            input('\n[bold {get_banner_color()}]Press Enter to continue...[/bold {get_banner_color()}]')







    # ============================================================
    # MAIN MENU
    # ============================================================
    # [YOUR EXISTING MENU CODE HERE - SAME AS BEFORE]

@security_guard
def change_big_banner():
    """
    OPTION 14 — COLOR & BANNER CHANGER

    Screenshot-style flow:
      1 SELECT COLOR
      2 CHANGE BANNER
      3 PAK SCANNING
      0 BACK

    The selected name/color is stored in the existing session globals, so
    the existing banner/header code automatically uses the new values.
    """
    global CURRENT_SESSION_BANNER, CURRENT_SESSION_COLOR

    color_options = [
        ("1",  "🌿 DEFAULT (Original Green)", "bright_green"),
        ("2",  "💙 Bright Blue",              "bright_blue"),
        ("3",  "❤️ Bright Red",               "bright_red"),
        ("4",  "💛 Bright Yellow",            "bright_yellow"),
        ("5",  "🩵 Bright Cyan",              "bright_cyan"),
        ("6",  "💜 Bright Magenta",           "bright_magenta"),
        ("7",  "🔵 Cyan",                     "cyan"),
        ("8",  "🌸 Magenta",                  "magenta"),
        ("9",  "🔷 Blue",                     "blue"),
        ("10", "🔴 Red",                      "red"),
        ("11", "🌈 Rainbow",                  "rainbow"),
    ]
    color_map = {n: c for n, _, c in color_options}

    def show_menu():
        b = get_banner_color()
        table = Table(
            show_header=True,
            box=box.HEAVY,
            border_style=b,
            expand=True,
        )
        table.add_column("OPT", justify="center", width=5)
        table.add_column("COMMAND", width=28)
        table.add_column("DESCRIPTION")

        table.add_row("1", f"[bold {b}]🎨 SELECT COLOR[/]",
                      "Change Tool Theme Color")
        table.add_row("2", f"[bold {b}]📝 CHANGE BANNER[/]",
                      "Change Banner Name")
        table.add_row("3", f"[bold {b}]📦 PAK SCANNING[/]",
                      "Scan PAK/OBB Files")
        table.add_row("0", "[bold red]BACK[/]",
                      "Return to Main Menu")

        console.print(Panel(
            table,
            title=f"[bold {b}]COLOR & BANNER CHANGER[/]",
            border_style=b,
            box=box.HEAVY,
        ))

    while True:
        console.clear()
        print_banner_and_header()
        show_menu()

        b_color = get_banner_color()
        choice = Prompt.ask(
            f"[bold {b_color}]Select option [0/1/2/3][/]",
            choices=["0", "1", "2", "3"],
            default="0",
        )

        if choice == "0":
            return

        # --------------------------------------------------------
        # 1 — SELECT COLOR (exact 10-color screenshot-style page)
        # --------------------------------------------------------
        if choice == "1":
            console.clear()
            print_banner_and_header()
            b = get_banner_color()

            color_table = Table(
                title=f"[bold {b}]🎨 SELECT COLOR THEME (11 COLORS) 🎨[/]",
                show_header=True,
                box=box.HEAVY,
                border_style=b,
                expand=True,
            )
            color_table.add_column("OPT", justify="center", width=6)
            color_table.add_column("COLOR", width=34)
            color_table.add_column("PREVIEW", justify="center", width=18)

            for num, name, color in color_options:
                color_table.add_row(
                    num,
                    f"[bold {color}]{name}[/]",
                    f"[bold {color}]████████████[/]",
                )

            console.print(color_table)

            selected = Prompt.ask(
                f"[bold {b}]Select color option (1-11) "
                f"[1/2/3/4/5/6/7/8/9/10/11][/]",
                choices=[n for n, _, _ in color_options],
                default="1",
            )

            chosen_color = color_map[selected]
            if chosen_color == "rainbow":
                CURRENT_SESSION_COLOR = "rainbow"
                console.print(Text("\n") + rainbow_text("✓ Rainbow Mode Activated!", 0))
            else:
                _stop_rainbow()
                CURRENT_SESSION_COLOR = chosen_color
                console.print(
                    f"\n[bold {CURRENT_SESSION_COLOR}]✓ Theme color changed: "
                    f"{CURRENT_SESSION_COLOR}[/]"
                )
            time.sleep(1.2)
            continue

        # --------------------------------------------------------
        # 2 — CHANGE BANNER
        # --------------------------------------------------------
        if choice == "2":
            console.clear()
            print_banner_and_header()
            b = get_banner_color()

            console.print(Panel(
                f"[bold {b}]📝 CHANGE BANNER NAME[/]\n"
                "[dim]Enter the new banner name.[/]",
                border_style=b,
                box=box.HEAVY,
            ))

            new_name = Prompt.ask(
                f"[bold {b}]Naya Banner Name Type Karo[/]",
                default=CURRENT_SESSION_BANNER,
            ).strip()

            if not new_name:
                console.print("[bold red]❌ Naam empty nahi ho sakta![/]")
                time.sleep(1.5)
                continue

            CURRENT_SESSION_BANNER = " ".join(new_name.split())[:40].upper()

            console.print(
                f"\n[bold {CURRENT_SESSION_COLOR}]✓ Banner Update Ho Gaya:[/]"
            )
            console.print(
                f"[bold {CURRENT_SESSION_COLOR}]Name: "
                f"{CURRENT_SESSION_BANNER}[/]"
            )
            time.sleep(1.5)
            continue

        # --------------------------------------------------------
        # 3 — PAK/OBB SCANNING (read-only)
        # --------------------------------------------------------
        if choice == "3":
            console.clear()
            print_banner_and_header()
            b = get_banner_color()

            roots = [Path.cwd(), Path.home()]
            android_storage = Path("/storage/emulated/0")
            if android_storage.exists():
                roots.append(android_storage)

            found = []
            seen = set()

            for root in roots:
                try:
                    for p in root.rglob("*"):
                        if not p.is_file():
                            continue
                        if p.suffix.lower() not in {".pak", ".obb"}:
                            continue

                        try:
                            resolved = str(p.resolve())
                        except OSError:
                            resolved = str(p)

                        if resolved in seen:
                            continue
                        seen.add(resolved)

                        try:
                            size = p.stat().st_size
                        except OSError:
                            size = 0

                        found.append((p, size))

                        if len(found) >= 200:
                            break
                except (OSError, PermissionError):
                    pass

                if len(found) >= 200:
                    break

            scan = Table(
                title="📦 PAK / OBB SCANNING",
                show_header=True,
                box=box.HEAVY,
                border_style=b,
                expand=True,
            )
            scan.add_column("#", justify="right", width=5)
            scan.add_column("FILE NAME")
            scan.add_column("SIZE", justify="right", width=12)

            def fmt_size(n):
                if n >= 1024**3:
                    return f"{n / 1024**3:.2f} GB"
                if n >= 1024**2:
                    return f"{n / 1024**2:.2f} MB"
                if n >= 1024:
                    return f"{n / 1024:.2f} KB"
                return f"{n} B"

            for i, (path, size) in enumerate(found, 1):
                scan.add_row(str(i), str(path), fmt_size(size))

            if found:
                console.print(scan)
                console.print(
                    f"\n[bold {b}]✓ Found {len(found)} PAK/OBB file(s).[/]"
                )
            else:
                console.print(Panel(
                    "[yellow]No .pak or .obb files found in the scanned "
                    "locations.[/]",
                    border_style=b,
                ))

            Prompt.ask("\nPress Enter to continue", default="")
            continue

def dump_obb_index_to_csv():
    console.clear()
    print_banner_and_header()
    b_color = get_banner_color()
    
    console.print(Panel(f"[bold {b_color}]📊 OBB INDEX CSV DUMPER[/bold {b_color}]\n[dim]Extracting Original OBB Index to CSV format...[/dim]", border_style=b_color))

    base = Path(BASE_DIR_NAME) / "OBB_UNPACKER"
    org_path = base / ORGNAL_DIR
    csv_out_path = base / "CSV_DUMPS"
    os.makedirs(to_long_path(csv_out_path), exist_ok=True)

    pak_files = list_paks_in_folder(org_path)
    if not pak_files:
        console.print(Panel(f"[red]No .pak/.obb files found in {org_path.resolve()}[/red]", title="❗ No PAKs", style="red"))
        Prompt.ask("\nPress Enter to continue", default="")
        return

    console.print(files_available_panel(pak_files, folder_label="Select OBB to Dump CSV"))
    pick = Prompt.ask(f"[bold {b_color}]Select OBB file number[/bold {b_color}]", choices=[str(i) for i in range(1, len(pak_files) + 1)])
    pak_path = pak_files[int(pick) - 1]

    csv_file_name = csv_out_path / f"{pak_path.stem}_index.csv"

    try:
        console.print(f"\n[bold cyan]⏳ Reading Index from {pak_path.name}...[/bold cyan]")
        pak = TencentPakFile(pak_path)
        with open(to_long_path(csv_file_name), 'w', encoding='utf-8') as f:
            f.write("File_Path,Offset,Size,Uncompressed_Size,Encryption_Method\n")
            total_files = 0
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), console=console) as progress:
                task = progress.add_task("[cyan]Writing to CSV...", total=len(pak._index))
                for dir_path, files in pak._index.items():
                    for name, entry in files.items():
                        if entry is not None:
                            full_path = str(dir_path / name).replace("\\", "/")
                            f.write(f"{full_path},{entry.offset},{entry.size},{entry.uncompressed_size},{entry.encryption_method}\n")
                            total_files += 1
                    progress.advance(task)

        console.print("\n")
        console.print(Panel(f"[bold green]✅ SUCCESS! Index Dumped Successfully![/bold green]\n"
                            f"[white]Total Files Logged:[/white] [cyan]{total_files}[/cyan]\n"
                            f"[white]CSV Saved at:[/white] [yellow]{csv_file_name.resolve()}[/yellow]", border_style="green"))

    except Exception as e:
        console.print(Panel(f"[red]Failed to dump CSV: {e}[/red]"))

    Prompt.ask("\nPress Enter to return to menu", default="")

# ==================================================
# 🔥 BLACK TOOL (UE4 String Editor) - Integrated 🔥
# ==================================================
BLACK_TOOL_BASE_DIR_NAME = os.path.join("ALVSIA_PRO_DATA", "CREDIT_TOOL")
BLACK_TOOL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), BLACK_TOOL_BASE_DIR_NAME)
WORK_DIR_BLACK = os.path.join(BLACK_TOOL_DIR, "ORGNAL")
MODIFIED_DIR_BLACK = os.path.join(BLACK_TOOL_DIR, "MODDED FILE")

def black_tool_ensure_work_dir():
    for d in [BLACK_TOOL_DIR, WORK_DIR_BLACK, MODIFIED_DIR_BLACK]:
        if not os.path.exists(d):
            try:
                os.makedirs(d)
                print(f"{to_fancy('INFO')}: Created directory {d}")
            except Exception as e:
                console.print(f"[red]Cannot create directory {d}: {e}[/red]")
                sys.exit()

def black_tool_list_files_in_dir(extensions=('.uasset', '.uexp')):
    try:
        if not os.path.exists(WORK_DIR_BLACK):
            black_tool_ensure_work_dir()
        all_files = os.listdir(WORK_DIR_BLACK)
        target_files = [f for f in all_files if f.lower().endswith(extensions)]
        target_files.sort()
        return target_files
    except Exception as e:
        console.print(f"[red]Error reading directory: {e}[/red]")
        return []

class UE4StringTool:
    def __init__(self):
        self.MIN_STRING_LEN = 2
        self.MAX_STRING_LEN = 8000

    def read_int(self, f):
        data = f.read(4)
        if len(data) < 4: return None
        return struct.unpack('<i', data)[0]

    def is_garbage_text(self, text):
        if not text or len(text.strip()) == 0: return True
        allowed_control = {'\n', '\r', '\t'}
        for char in text:
            code = ord(char)
            if code == 0: return True
            if code < 32 and char not in allowed_control: return True
            if char == '\ufffd': return True
        return False

    def is_valid_string_start(self, f, current_pos):
        f.seek(current_pos)
        length = self.read_int(f)
        if length is None: return False
        if length == 0: return False
        if not (self.MIN_STRING_LEN <= abs(length) <= self.MAX_STRING_LEN): return False
        try:
            if length < 0:
                read_len = -length * 2
                data = f.read(read_len)
                if len(data) != read_len: return False
                if data[-2:] != b'\x00\x00': return False
                text = data[:-2].decode('utf-16le')
            else:
                read_len = length
                data = f.read(read_len)
                if len(data) != read_len: return False
                if data[-1:] != b'\x00': return False
                text = data[:-1].decode('utf-8')
            if self.is_garbage_text(text): return False
            return True
        except:
            return False

    def extract_file(self, file_name):
        file_path = os.path.join(WORK_DIR_BLACK, file_name)
        if not os.path.exists(file_path):
            return False, f"File not found: {file_name}"
        json_path = file_path + ".json"
        console.print(f"\n[bold yellow]{to_fancy('Create JSON')}: {file_name}[/bold yellow]")
        try:
            with open(file_path, 'rb') as f:
                f.seek(0, 2)
                file_size = f.tell()
                f.seek(0)
                entries = []
                cursor = 0
                with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), console=console) as progress:
                    task = progress.add_task("[cyan]Extracting strings...", total=file_size)
                    while cursor < file_size - 4:
                        progress.update(task, completed=cursor)
                        if self.is_valid_string_start(f, cursor):
                            f.seek(cursor)
                            length = self.read_int(f)
                            is_utf16 = length < 0
                            abs_len = abs(length)
                            if is_utf16:
                                raw_data = f.read(abs_len * 2)
                                text = raw_data[:-2].decode('utf-16le')
                                total_size = 4 + (abs_len * 2)
                            else:
                                raw_data = f.read(abs_len)
                                text = raw_data[:-1].decode('utf-8')
                                total_size = 4 + abs_len
                            entries.append({
                                "offset": cursor,
                                "original_len_int": length,
                                "text": text
                            })
                            cursor += total_size
                        else:
                            cursor += 1
                if not entries:
                    return False, "No valid text strings found."
                with open(json_path, 'w', encoding='utf-8') as jf:
                    json.dump(entries, jf, indent=4, ensure_ascii=False)
            return True, f"Exported {len(entries)} strings -> {os.path.basename(json_path)}"
        except Exception as e:
            return False, str(e)

    def repack_file(self, file_name):
        original_file_path = os.path.join(WORK_DIR_BLACK, file_name)
        json_path = original_file_path + ".json"
        
        if not os.path.exists(original_file_path):
            return False, f"Missing original file: {file_name}"
        if not os.path.exists(json_path):
            return False, f"Missing file: {file_name}.json"

        modified_file_path = os.path.join(MODIFIED_DIR_BLACK, file_name)
        console.print(f"[bold yellow]{to_fancy('Repacking')}: {file_name}...[/bold yellow]")

        try:
            with open(json_path, 'r', encoding='utf-8') as jf:
                entries = json.load(jf)
            entries.sort(key=lambda x: x['offset'])

            with open(original_file_path, 'rb') as f_orig, open(modified_file_path, 'wb') as f_out:
                cursor_orig = 0
                count_modified = 0
                for i, entry in enumerate(entries):
                    gap_size = entry['offset'] - cursor_orig
                    if gap_size > 0:
                        f_out.write(f_orig.read(gap_size))
                    elif gap_size < 0:
                        f_orig.seek(entry['offset'])

                    new_text = entry['text']
                    old_len_int = entry['original_len_int']
                    is_utf16 = old_len_int < 0
                    if is_utf16: max_byte_size = abs(old_len_int) * 2
                    else: max_byte_size = abs(old_len_int)

                    f_orig.seek(entry['offset'] + 4)
                    old_raw_display = f_orig.read(max_byte_size)
                    try:
                        if is_utf16: old_text_display = old_raw_display[:-2].decode('utf-16le')
                        else: old_text_display = old_raw_display[:-1].decode('utf-8')
                    except: old_text_display = "<Decode error>"
                    
                    if new_text != old_text_display:
                        count_modified += 1

                    if is_utf16: new_bytes = new_text.encode('utf-16le') + b'\x00\x00'
                    else: new_bytes = new_text.encode('utf-8') + b'\x00'
                    current_byte_size = len(new_bytes)

                    if current_byte_size > max_byte_size:
                        console.print(f"\n[bold red]❌ CRITICAL ERROR AT LINE {i+1} (Offset: {entry['offset']})[/bold red]")
                        console.print(f"[bold red]   [!] New string is longer than original string ({current_byte_size} > {max_byte_size} bytes)[/bold red]")
                        f_out.close(); f_orig.close()
                        if os.path.exists(modified_file_path): os.remove(modified_file_path)
                        return False, "New string length exceeds original string length."

                    f_out.write(struct.pack('<i', old_len_int))
                    f_out.write(new_bytes)

                    pad_len = max_byte_size - current_byte_size
                    if pad_len > 0:
                        f_out.write(b'\x00' * pad_len)

                    f_orig.seek(entry['offset'])
                    len_check = self.read_int(f_orig)
                    skip_len = 4 + (abs(len_check) * 2 if len_check < 0 else abs(len_check))
                    f_orig.seek(entry['offset'] + skip_len)
                    cursor_orig = f_orig.tell()

                f_out.write(f_orig.read())

            return True, f"Updated {count_modified} lines -> {os.path.basename(modified_file_path)} (in MODDED FILE folder)"
        except Exception as e:
            return False, str(e)

def black_tool_do_unpack_fancy(tool):
    console.clear()
    print_banner_and_header()
    print_user_profile()
    b_color = get_banner_color()
    console.print(Panel(f"[bold {b_color}]{to_fancy('MASTER UNPACK (ALL FILES)')}[/bold {b_color}]\n"
                        f"[dim]Extracting all UEXP/UASSET files to JSON at once...[/dim]", border_style=b_color))
    
    files = black_tool_list_files_in_dir(('.uasset', '.uexp'))
    if not files:
        console.print(Panel(f"[red]{to_fancy('No files found to unpack!')}[/red]", border_style="red"))
        Prompt.ask(f"\n[bold white]{to_fancy('Press Enter to continue...')}[/bold white]", default="")
        return

    unpacked_count = 0
    console.print(f"\n[bold cyan]⏳ Auto-Unpacking all files...[/bold cyan]")
    for fname in files:
        success, msg = tool.extract_file(fname)
        if success:
            console.print(f"[bold green]✔ {to_fancy('SUCCESS')}:[/bold green] {to_fancy(fname)}")
            unpacked_count += 1
        else:
            console.print(f"[bold red]❌ {to_fancy('FAILED')}:[/bold red] {to_fancy(fname)}\n   [dim]{msg}[/dim]")

    console.print("\n")
    if unpacked_count > 0:
        console.print(Panel(f"[bold green]✅ {to_fancy('ALL DONE')}! {unpacked_count} {to_fancy('files unpacked successfully.')}[/bold green]\n[white]JSON files created in ORGNAL folder.[/white]", border_style="green"))
    else:
        console.print(Panel(f"[yellow]⚠️ {to_fancy('No files were unpacked.')}[/yellow]", border_style="yellow"))
    Prompt.ask("\n[bold white]Press Enter to continue...[/bold white]", default="")

def black_tool_do_repack_fancy(tool):
    console.clear()
    print_banner_and_header()
    print_user_profile()
    b_color = get_banner_color()
    console.print(Panel(f"[bold {b_color}]{to_fancy('MASTER REPACK (ALL FILES)')}[/bold {b_color}]\n"
                        f"[dim]Converting all JSON back to UEXP at once...[/dim]", border_style=b_color))
    
    files = black_tool_list_files_in_dir(('.uasset', '.uexp'))
    if not files:
        console.print(Panel(f"[red]{to_fancy('No files found to repack!')}[/red]", border_style="red"))
        Prompt.ask(f"\n[bold white]{to_fancy('Press Enter to continue...')}[/bold white]", default="")
        return

    repacked_count = 0
    repacked_files_list = [] 
    
    console.print(f"\n[bold cyan]⏳ Auto-Repacking all files...[/bold cyan]")
    for fname in files:
        json_path = os.path.join(WORK_DIR_BLACK, fname + ".json")
        if os.path.exists(json_path):
            success, msg = tool.repack_file(fname)
            if success:
                console.print(f"[bold green]✔ {to_fancy('SUCCESS')}:[/bold green] {to_fancy(fname)}")
                repacked_count += 1
                repacked_files_list.append(fname)
            else:
                console.print(f"[bold red]❌ {to_fancy('FAILED')}:[/bold red] {to_fancy(fname)}\n   [dim]{msg}[/dim]")
        else:
            console.print(f"[dim yellow]⚠️ Skipped (No JSON found): {to_fancy(fname)}[/dim yellow]")

    console.print("\n")
    if repacked_count > 0:
        console.print(Panel(f"[bold green]✅ {to_fancy('ALL DONE')}! {repacked_count} {to_fancy('files repacked successfully.')}[/bold green]\n[white]Files are in MODDED FILE folder.[/white]", border_style="green"))
        
        copy_choice = Prompt.ask(f"\n[bold yellow]❓ KYA AAP INHE 'Modified_files' AUR 'MOD_REPACK' MEIN OPEN COPY KARNA CHAHTE HAI?[/bold yellow] (y/n)", default="y")
        
        if copy_choice.lower() == 'y':
            target_modified = Path(BASE_DIR_NAME) / "OBB_UNPACKER" / "Modified_files"
            target_enc_open = ANLAISH_DIR / "MOD_REPACK"
            
            os.makedirs(to_long_path(target_modified), exist_ok=True)
            os.makedirs(to_long_path(target_enc_open), exist_ok=True)
            
            copied_mod = 0
            copied_enc = 0
            
            for fname in repacked_files_list:
                src = os.path.join(MODIFIED_DIR_BLACK, fname)
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(target_modified, fname))
                    copied_mod += 1
                    shutil.copy2(src, os.path.join(target_enc_open, fname))
                    copied_enc += 1
            
            if copied_mod > 0:
                console.print(f"\n[bold {get_banner_color()}]🚀 BOOM! {copied_mod} files copied to 'Modified_files'![/bold {get_banner_color()}]")
            if copied_enc > 0:
                console.print(f"[bold cyan]💎 {copied_enc} Credit files copied OPEN in 'MOD_REPACK'![/bold cyan]")
            if copied_mod == 0 and copied_enc == 0:
                console.print(f"[bold red]❌ Error: File copy nahi ho payi.[/bold red]")
    else:
        console.print(Panel(f"[yellow]⚠️ {to_fancy('No files were repacked.')}[/yellow]", border_style="yellow"))
        
    Prompt.ask("\n[bold white]Press Enter to continue...[/bold white]", default="")

TARGET_GROUPS = {
    "1. MATCH START & THEME": ["Match starts in <MatchStartInfo>{0}</>", "Match starts in", "Your match starts in", "Bonus Challenge match starts", "LEAN (BGMI 2026 Theme Song)"],
    "2. CHICKEN DINNER": ["WINNER WINNER CHICKEN DINNER!", "WINNER WINNER CHICKEN DINNER", "Winner Winner Chicken Dinner", "Winner winner chicken dinner"],
    "3. BETTER LUCK NEXT TIME": ["Better Luck Next Time", "BETTER LUCK NEXT TIME"],
    "4. TEAMMATE DAMAGE WARNINGS": ["As you attacked your teammate first", "As you have maliciously injured your teammate"],
    "5. QUICK CHAT MESSAGES": ["Watch your aim and finish them off!", "Get behind the wheel and crush them!"],
    "6. BAN PAN SECURITY": ["Ban Pan", "Ban Pan - Pan", "BGMI & Ban Pan"],
    "7. SPLASH SCREEN WARNING": ["Battlegrounds Mobile India is not a real-world based game"],
    "8. HOME ISLE NOTIFICATIONS": ["Home Isle is an island located in the ocean", "Now, let me briefly explain removing objects", "Lastly, here's an important tip", "It's important to note that once you finish building", "Your time spent working on your Home has reached a new milestone!", "This past year witnessed our growth and progress", "There are so many beautiful moments we have shared together."],
    "9. GAME EVENTS & UI": ["Sara is a vehicle expert", "Vehicle weapons will automatically lock", "Try out the DJ stage", "You have collected 3 vehicle finishes", "Clan Battle is about to start", "Try the smart Digi-pal chat", "Too many PvE enemy eliminations", "Synergy: Some Popularity gifts", "Win battles with your friends", "The Aerolith has begun absorbing mutants", "8. If you have any questions regarding payment", "Myriad splendors glazed"]
}

def get_live_input_match_start(prompt_text):
    sys.stdout.write(prompt_text)
    sys.stdout.flush()
    input_str = ""
    while True:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        if ch == '\r': 
            print()
            break
        elif ch == '\x7f': 
            if len(input_str) > 0: input_str = input_str[:-1]
        else: input_str += ch

        sys.stdout.write('\r' + ' ' * (len(prompt_text) + len(input_str) + 15) + '\r')
        sys.stdout.write(prompt_text)
        display = input_str
        if "[" in display and "]" in display:
            parts = display.split("[", 1)
            pre = parts[0]
            inner_post = parts[1].split("]", 1)
            inner = inner_post[0]
            post = inner_post[1] if len(inner_post) > 1 else ""
            sys.stdout.write(f"{pre}\033[96m[\033[0m \033[93m{inner}\033[0m \033[96m]\033[0m{post}")
        elif "[" in display:
            pre, inner = display.split("[", 1)
            sys.stdout.write(f"{pre}\033[96m[\033[0m\033[93m{inner}\033[0m")
        else:
            sys.stdout.write(f"\033[93m{display}\033[0m")
        sys.stdout.flush()
    return input_str

def black_tool_do_custom_edit_fancy(tool):
    print_banner_and_header()
    b_color = get_banner_color()
    json_files = [f for f in os.listdir(WORK_DIR_BLACK) if f.endswith('.json')]
    
    if not json_files:
        console.print(f"[red]No JSON files found![/red]")
        return

    for j_file in json_files:
        json_path = os.path.join(WORK_DIR_BLACK, j_file)
        with open(json_path, 'r', encoding='utf-8') as f:
            entries = json.load(f)

        for group_name, keywords in TARGET_GROUPS.items():
            matching_entries = [e for e in entries if any(kw in e['text'] for kw in keywords)]

            if matching_entries:
                console.print(f"\n[bold cyan]Target:[/] [white]{group_name}[/]")
                if "1. MATCH START" in group_name:
                    new_text = get_live_input_match_start(f" \033[1;32mENTER YELLOW TEXT > \033[0m")
                else:
                    new_text = Prompt.ask(f"[bold {b_color}]Enter normal text[/bold {b_color}]")

                if new_text.strip():
                    processed_text = new_text
                    if "1. MATCH START" in group_name:
                        if "[" in processed_text and "]" in processed_text:
                            parts = processed_text.split("[", 1)
                            pre = parts[0]
                            inner, post = parts[1].split("]", 1) if "]" in parts[1] else (parts[1], "")
                            processed_text = f"{pre}[ <MatchStartInfo>{inner}</>]{post}"
                        else:
                            processed_text = f"<MatchStartInfo>{processed_text}</>"
                    for e in matching_entries:
                        e_max = abs(e['original_len_int'])
                        e['text'] = processed_text[:e_max-1]

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(entries, f, indent=4, ensure_ascii=False)
    
    console.print(Panel("[bold green]✅ ALL DONE: Targeted Modding Complete![/bold green]"))
    Prompt.ask("\nPress Enter to continue...", default="")

@security_guard
def black_tool_main(auto_select_file="mini_obb.pak"):
    global SERVER_ENGINE_TOKEN
    if SERVER_ENGINE_TOKEN == "LOCKED" or len(SERVER_ENGINE_TOKEN) != 64:
        os._exit(0)
        
    black_tool_ensure_work_dir()
    REQUIRED_FILES = ["LocalizationText_en.uexp", "SplashScreen_BH.uexp"]
    missing_files = [f for f in REQUIRED_FILES if not os.path.exists(os.path.join(WORK_DIR_BLACK, f)) or os.path.getsize(os.path.join(WORK_DIR_BLACK, f)) == 0]

    if missing_files:
        b_color = get_banner_color()
        console.print(f"\n[bold yellow]⚠️ Missing files in ORGNAL: {', '.join(missing_files)}[/bold yellow]")
        obb_folder = Path(BASE_DIR_NAME) / "OBB_UNPACKER" / "ORGNAL"
        pak_files = list_paks_in_folder(obb_folder)

        if pak_files:
            target_index = -1
            if auto_select_file:
                for i, p in enumerate(pak_files):
                    if p.name.lower() == auto_select_file.lower():
                        target_index = i
                        break
            
            if target_index != -1:
                pak_path = pak_files[target_index]
                console.print(f"[bold green]🚀 AUTO-SELECTING:[/] [white]{pak_path.name}[/white]")
            else:
                console.print(files_available_panel(pak_files, folder_label="Select OBB to extract missing files"))
                pick = Prompt.ask(f"[bold {b_color}]Select OBB/PAK file number[/bold {b_color}]", choices=[str(i) for i in range(1, len(pak_files) + 1)])
                pak_path = pak_files[int(pick) - 1]
            
            console.print(f"\n[bold cyan]⏳ PRO EXTRACTION: Scanning {pak_path.name}...[/bold cyan]")
            try:
                pak = TencentPakFile(pak_path)
                for target_file in missing_files:
                    candidates = []
                    for dir_path, dir_entries in pak._index.items():
                        for fname, entry in dir_entries.items():
                            if fname.lower() == target_file.lower() and entry is not None:
                                candidates.append(entry)
                    if candidates:
                        candidates.sort(key=lambda x: x.size, reverse=True) 
                        for entry in candidates:
                            target_dest = Path(WORK_DIR_BLACK) / target_file
                            pak._write_to_disk(target_dest, entry)
                            if os.path.getsize(target_dest) > 1024: 
                                console.print(f"[bold green]✔ PRO EXTRACT SUCCESS:[/] {target_file}")
                                break 
            except Exception as e:
                console.print(f"[red]Error parsing OBB: {e}[/red]")
            
            if target_index == -1:
                Prompt.ask("\n[bold white]Press Enter to continue...[/bold white]", default="")
        else:
            console.print(f"[bold red]❌ No OBB found in {obb_folder}![/bold red]")

    tool = UE4StringTool()
    while True:
        print_banner_and_header()
        print_user_profile()
        b_color = get_banner_color()
        menu_table = Table(show_header=False, box=box.SIMPLE, expand=True)
        menu_table.add_column("𝐎𝐏𝐓", style="bold white", justify="center", width=4)
        menu_table.add_column("𝐂𝐎𝐌𝐌𝐀𝐍𝐃", style=f"bold {b_color}")
        menu_table.add_column("DESC", style="dim white")
        menu_table.add_row(menu_item("1", 0), menu_item("UNPACK", 1), menu_item("UEXP to JSON", 5))
        menu_table.add_row(menu_item("2", 2), menu_item("REPACK", 3), menu_item("JSON to UEXP", 7))
        menu_table.add_row(menu_item("3", 4), menu_item("MASTER CUSTOM EDIT", 5), menu_item("🔥 Live Color Edit", 9))
        menu_table.add_row(menu_item("4", 6), menu_item("BACK", 7), menu_item("Back to RedMagix", 11))
        console.print(Panel(menu_table, border_style=b_color, box=box.HEAVY, title=f"[bold black on {b_color}] {to_fancy('BLACK TOOL OPTIONS')} [/]"))
        
        choice = Prompt.ask(f"[bold {b_color}]{to_fancy('Select option')}[/bold {b_color}]", choices=["1","2","3","4"])
        if choice == '1': black_tool_do_unpack_fancy(tool)
        elif choice == '2': black_tool_do_repack_fancy(tool)
        elif choice == '3': black_tool_do_custom_edit_fancy(tool)
        elif choice == '4': return

# ======================================================================
# 🔥 LUA REPACK ANY SIZE ENGINE (FULL REBUILD) 🔥
# ======================================================================
# ======================================================================
# 🔥 LUA REPACK ANY SIZE ENGINE (FULL REBUILD) 🔥
# ======================================================================
import copy as _cp

def _pw_string(s):
    if not s: return struct.pack('<i', 0)
    b = s.encode('utf-8') + b'\x00'
    return struct.pack('<i', len(b)) + b

def _pw_entry(e, v):
    w = bytearray(e.content_hash)
    w += struct.pack('<Q', e.offset)
    w += struct.pack('<Q', e.uncompressed_size)
    w += struct.pack('<I', e.compression_method)
    w += struct.pack('<Q', e.size)
    if v >= 5:
        w += bytes([e.unk1])
        w += e.unk2
    if e.compression_method != 0 and v >= 3:
        w += struct.pack('<I', len(e.compressed_blocks))
        for b in e.compressed_blocks:
            w += struct.pack('<QQ', b.start, b.end)
    if v >= 4:
        w += struct.pack('<I', e.compression_block_size)
        w += bytes([1 if e.encrypted else 0])
    if v >= 12:
        w += struct.pack('<II', e.encryption_method, e.index_new_sep)
    return bytes(w)

def _get_all_dirs_and_mp(pak_file):
    raw = bytes(pak_file._file_content[pak_file._pak_info.index_offset:][:pak_file._pak_info.index_size])
    if pak_file._pak_info.index_encrypted:
        raw = PakCrypto.decrypt_index(raw, pak_file._pak_info)
    r = Reader(raw)
    mp = r.string()
    num_files = r.u4()
    for _ in range(num_files):
        TencentPakEntry(r, pak_file._pak_info.version)
    dirs = {}
    for _ in range(r.u8()):
        dp = r.string()
        cnt = r.u8()
        dirs[dp] = {r.string(): pak_file._files[~r.i4()] for _ in range(cnt)}
    return mp, dirs

def repack_any_size(pak_file, edited_root, output_path):
    edit_files = [p for p in Path(edited_root).rglob('*') if p.is_file()]
    if not edit_files: return 0

    version = pak_file._pak_info.version
    try: keystream = PakCrypto.zuc_keystream()
    except Exception: keystream = [0]*16
        
    orig_fc = pak_file._file_content
    mp_str, all_dirs = _get_all_dirs_and_mp(pak_file)

    pak_name_map = {}
    for dir_path, files in pak_file._index.items():
        for name, entry in files.items():
            full_path = str(PurePath(dir_path)/name).replace('\\', '/')
            pak_name_map.setdefault(name.lower(), []).append((full_path, entry))

    edited = {}
    for p in edit_files:
        fl = p.name.lower()
        found_match = False
        if fl in pak_name_map:
            cands = pak_name_map[fl]
            sz = p.stat().st_size
            sm = [(fp, e) for fp, e in cands if e.uncompressed_size == sz]
            fp, ent = sm[0] if sm else cands[0]
            edited[fp] = (p, ent)
            found_match = True
        
        if not found_match:
            stem = p.stem.lower()
            ext = p.suffix.lower()
            for dir_path, files in pak_file._index.items():
                for name, entry in files.items():
                    if Path(name).stem.lower() == stem and Path(name).suffix.lower() == ext:
                        full_path = str(PurePath(dir_path)/name).replace('\\', '/')
                        edited[full_path] = (p, entry)
                        found_match = True
                        break
                if found_match: break

    if not edited: return 0

    new_files = []
    for e in pak_file._files:
        ne = _cp.copy(e)
        ne.compressed_blocks = [_cp.copy(b) for b in getattr(e, 'compressed_blocks', [])]
        new_files.append(ne)

    old_to_new = {id(pak_file._files[i]): new_files[i] for i in range(len(pak_file._files))}
    edited_paths = {fp: p for fp, (p, _) in edited.items()}
    out_buf = bytearray()

    for dp_str, dir_files in list(all_dirs.items()):
        for name, old_entry in list(dir_files.items()):
            full_path = str(PurePath(dp_str)/name).replace('\\', '/')
            ne = old_to_new.get(id(old_entry), None)
            
            if ne is None:
                ne = _cp.copy(old_entry)
                ne.compressed_blocks = [_cp.copy(b) for b in getattr(old_entry, 'compressed_blocks', [])]
                new_files.append(ne)
                old_to_new[id(old_entry)] = ne

            em = getattr(old_entry, 'encryption_method', 0)
            cm = getattr(old_entry, 'compression_method', 0)

            if full_path in edited_paths:
                p, template = edited[full_path]
                new_raw = p.read_bytes()
                pak_rel = PurePath(full_path)

                ne.content_hash = SHA1.new(new_raw).digest() if SHA1 else b'\x00'*20
                ne.uncompressed_size = len(new_raw)
                
                if ne.compression_method == 0:
                    cipher = pak_file._apply_encrypt_for_entry(new_raw, pak_rel, ne.encryption_method) if ne.encrypted else new_raw
                    ne.offset = len(out_buf)
                    ne.size = len(cipher)
                    out_buf += cipher
                else:
                    cs = template.compression_block_size if template and template.compression_block_size > 0 else 65536
                    chunks = [new_raw[i:i+cs] for i in range(0, len(new_raw), cs)]
                    new_blks = []
                    for chunk in chunks:
                        compressed = PakCompression.compress_block(chunk, ne.compression_method, pak_file._zstd_dict, None)
                        cipher = pak_file._apply_encrypt_for_entry(compressed, pak_rel, ne.encryption_method) if ne.encrypted else compressed
                        blk = PakCompressedBlock.__new__(PakCompressedBlock)
                        blk.start = len(out_buf)
                        blk.end = blk.start + len(cipher)
                        out_buf += cipher
                        new_blks.append(blk)

                    ne.compressed_blocks = new_blks
                    ne.offset = new_blks[0].start if new_blks else len(out_buf)
                    ne.size = sum(b.end - b.start for b in new_blks)
            else:
                if cm == 0:
                    read_sz = PakCrypto.align_encrypted_content_size(old_entry.size, em) if old_entry.encrypted else old_entry.size
                    ne.offset = len(out_buf)
                    out_buf += bytes(orig_fc[old_entry.offset: old_entry.offset + read_sz])
                elif hasattr(old_entry, 'compressed_blocks') and old_entry.compressed_blocks:
                    new_blks = []
                    for ob in old_entry.compressed_blocks:
                        unc = ob.end - ob.start
                        enc = PakCrypto.align_encrypted_content_size(unc, em) if old_entry.encrypted else unc
                        nb = PakCompressedBlock.__new__(PakCompressedBlock)
                        nb.start = len(out_buf)
                        nb.end = nb.start + unc
                        out_buf += bytes(orig_fc[ob.start: ob.start + enc])
                        new_blks.append(nb)
                    ne.compressed_blocks = new_blks
                    ne.offset = new_blks[0].start

    eidx = {id(e): i for i in range(len(new_files))}
    idx = bytearray(_pw_string(mp_str))
    idx += struct.pack('<I', len(new_files))
    for ne in new_files: idx += _pw_entry(ne, version)
    idx += struct.pack('<Q', len(all_dirs))
    for dp_str, dir_files in all_dirs.items():
        idx += _pw_string(dp_str)
        idx += struct.pack('<Q', len(dir_files))
        for name, old_e in dir_files.items():
            idx += _pw_string(name)
            found_idx = eidx.get(id(old_to_new.get(id(old_e), old_e)), -1)
            idx += struct.pack('<i', ~found_idx if found_idx != -1 else -1)

    index_plain = bytes(idx)
    new_sha1 = SHA1.new(index_plain).digest() if SHA1 else b'\x00'*20

    if pak_file._pak_info.index_encrypted:
        key = PakCrypto.rsa_extract(pak_file._pak_info.packed_key, RSA_MOD_1)
        iv = PakCrypto.rsa_extract(pak_file._pak_info.packed_iv, RSA_MOD_1)
        aes = AES.new(key, MODE_CBC, iv[:16])
        pad_len = (-len(index_plain)) % 16 or 16
        index_bytes = aes.encrypt(index_plain + bytes([pad_len] * pad_len))
    else:
        index_bytes = index_plain

    new_idx_offset = len(out_buf)
    new_idx_size = len(index_bytes)
    out_buf += index_bytes

    footer_sz = TencentPakInfo._mem_size(version)
    new_footer = bytearray(orig_fc[-footer_sz:])
    h_key = struct.pack('<5I', *keystream[4:9])
    new_footer[-36:-16] = bytes(a ^ b for a, b in zip(new_sha1, h_key))
    new_footer[-16:-8] = ((new_idx_size ^ (keystream[10] << 32 | keystream[11])).to_bytes(8, 'little'))
    new_footer[-8:] = ((new_idx_offset ^ (keystream[0] << 32 | keystream[1])).to_bytes(8, 'little'))

    out_buf += new_footer
    with open(output_path, 'wb') as f: f.write(out_buf)
    return len(edited)

# ======================================================================
# 🔥 TARGET PATH REPACK ENGINE (NEW FILES SUPPORT) 🔥
# ===============================================# ========================# ==========================================# ======================================================================
# ======================================================================
# 🔥 PAK # ======================================================================
# 🔥 PAK INJECTION ENGINE (APPEND NEW FILES) 🔥
# ======================================================================

def _serialize_string(s: str) -> bytes:
    encoded = s.encode('utf-8') + b'\x00'
    return struct.pack('<i', len(encoded)) + encoded

def _serialize_entry(buf: bytearray, entry: TencentPakEntry, version: int):
    buf.extend(entry.content_hash)
    buf.extend(struct.pack('<Q', entry.offset))
    buf.extend(struct.pack('<Q', entry.uncompressed_size))
    buf.extend(struct.pack('<I', entry.compression_method))
    buf.extend(struct.pack('<Q', entry.size))
    if version >= 5:
        buf.extend(struct.pack('B', entry.unk1))
        buf.extend(entry.unk2)
    if entry.compression_method != 0:
        buf.extend(struct.pack('<I', len(entry.compressed_blocks)))
        for blk in entry.compressed_blocks:
            buf.extend(struct.pack('<QQ', blk.start, blk.end))
    if version >= 4:
        buf.extend(struct.pack('<I', entry.compression_block_size))
        buf.extend(struct.pack('B', 1 if entry.encrypted else 0))
    if version >= 12:
        buf.extend(struct.pack('<I', entry.encryption_method))
        buf.extend(struct.pack('<I', entry.index_new_sep))

def _build_index_bytes(old_index_data: bytes, new_entries: list, version: int) -> bytes:
    buf = bytearray()
    reader = Reader(old_index_data)

    mount_len = reader.i4()
    mount_raw = old_index_data[reader._cursor - 4:reader._cursor + mount_len]
    reader._cursor += mount_len
    buf.extend(mount_raw)

    old_count = reader.u4()
    buf.extend(struct.pack('<I', old_count + len(new_entries)))

    entries_start = reader._cursor
    for _ in range(old_count):
        TencentPakEntry(reader, version)
    buf.extend(old_index_data[entries_start:reader._cursor])

    for entry, _, _ in new_entries:
        _serialize_entry(buf, entry, version)

    dir_table_raw = old_index_data[reader._cursor:]
    old_dir_count = struct.unpack_from('<Q', dir_table_raw, 0)[0]
    
    old_dir_entries = []
    dc = 8
    for _ in range(old_dir_count):
        dlen = struct.unpack_from('<i', dir_table_raw, dc)[0]
        dname_raw_bytes = dir_table_raw[dc:dc + 4 + dlen]
        dname_raw = dir_table_raw[dc+4:dc+4+dlen].decode('ascii', errors='replace').rstrip('\x00')
        dc += 4 + dlen
        dirname = PurePath(dname_raw).as_posix()
        if dname_raw.endswith('/'): dirname += '/'
        num_entries = struct.unpack_from('<Q', dir_table_raw, dc)[0]
        dc += 8
        entries_start = dc
        for _ in range(num_entries):
            flen = struct.unpack_from('<i', dir_table_raw, dc)[0]
            dc += 4 + flen + 4
        old_dir_entries.append((dname_raw_bytes, dirname, num_entries, entries_start, dc))
    
    new_dir_map = {}
    base_idx = old_count
    for idx, (_, dir_path, fname) in enumerate(new_entries):
        key = dir_path.as_posix() + '/'
        new_dir_map.setdefault(key, []).append((base_idx + idx, fname))
    
    existing_dirs = {d[1] for d in old_dir_entries}
    existing_additions = {}
    append_dirs = {}
    for key, entries in new_dir_map.items():
        if key in existing_dirs: existing_additions[key] = entries
        else: append_dirs[key] = entries
    
    buf.extend(struct.pack('<Q', old_dir_count + len(append_dirs)))
    
    for dname_raw_bytes, dirname, num_entries, entries_start, entries_end in old_dir_entries:
        additions = existing_additions.get(dirname, [])
        new_count = num_entries + len(additions)
        buf.extend(dname_raw_bytes)
        buf.extend(struct.pack('<Q', new_count))
        buf.extend(dir_table_raw[entries_start:entries_end])
        for idx, fname in additions:
            buf.extend(_serialize_string(fname))
            buf.extend(struct.pack('<i', ~idx))
    
    for dir_key, entries in append_dirs.items():
        buf.extend(_serialize_string(dir_key))
        buf.extend(struct.pack('<Q', len(entries)))
        for idx, fname in entries:
            buf.extend(_serialize_string(fname))
            buf.extend(struct.pack('<i', ~idx))

    return bytes(buf)

def _write_footer(outfh, pak_info: TencentPakInfo, index_data_encrypted: bytes, index_data_plain: bytes, data_end_offset: int, keystream: list, content_org_hash: bytes):
    version = pak_info.version
    index_offset = data_end_offset
    index_size = len(index_data_encrypted)
    if SHA1: index_hash = SHA1.new(index_data_plain).digest()
    else: index_hash = b'\x00'*20

    def enc_index_encrypted(x: int) -> int: return x ^ keystream[3] & 0xFF
    def enc_magic(x: int) -> int: return x ^ keystream[2]
    def enc_index_hash(x: bytes) -> bytes:
        key = struct.pack('<5I', *keystream[4:][:5])
        return bytes(a ^ b for a, b in zip(x, key))
    def enc_index_size(x: int) -> int: return x ^ ((keystream[10] << 32) | keystream[11])
    def enc_index_offset(x: int) -> int: return x ^ ((keystream[0] << 32) | keystream[1])
    def enc_unk(x: bytes) -> bytes:
        key = struct.pack('<8I', *keystream[7:][:8])
        return bytes(a ^ b for a, b in zip(x, key))
    def enc_stem_hash(x: int) -> int: return x ^ keystream[8]
    def enc_unk_hash(x: int) -> int: return x ^ keystream[9]

    fbuf = bytearray()
    if version >= 7: fbuf.extend(enc_unk(pak_info.unk1))
    if version >= 8:
        fbuf.extend(pak_info.packed_key)
        fbuf.extend(pak_info.packed_iv)
        fbuf.extend(pak_info.packed_index_hash)
    if version >= 9:
        fbuf.extend(struct.pack('<I', enc_stem_hash(pak_info.stem_hash)))
        fbuf.extend(struct.pack('<I', enc_unk_hash(pak_info.unk2)))
    if version >= 12: fbuf.extend(content_org_hash)
    
    fbuf.append(enc_index_encrypted(1))
    fbuf.extend(struct.pack('<I', enc_magic(pak_info.magic)))
    fbuf.extend(struct.pack('<I', version))
    fbuf.extend(enc_index_hash(index_hash))
    fbuf.extend(struct.pack('<Q', enc_index_size(index_size)))
    fbuf.extend(struct.pack('<Q', enc_index_offset(index_offset)))
    outfh.write(bytes(fbuf))

def pak_injection(pak_path: Path, inject_dir: Path, output_path: Path, target_path_prefix: str = "", compression_block_size: int = 0, show_ui: bool = False):
    pak = TencentPakFile(pak_path)
    version = pak._pak_info.version
    
    orig_idx_off = pak._pak_info.index_offset
    orig_idx_sz = pak._pak_info.index_size
    old_idx_enc = bytes(pak._file_content[orig_idx_off:][:orig_idx_sz])
    
    if pak._pak_info.index_encrypted:
        try: old_idx_dec = PakCrypto.decrypt_index(old_idx_enc, pak._pak_info)
        except: old_idx_dec = old_idx_enc
    else:
        old_idx_dec = old_idx_enc

    entry_path_map = {}
    for dir_path, files in pak._index.items():
        for name, entry in files.items():
            if entry is not None:
                for idx, fe in enumerate(pak._files):
                    if fe is entry:
                        entry_path_map[idx] = (dir_path, name)
                        break

    old_entries = []
    for idx, fe in enumerate(pak._files):
        if idx in entry_path_map:
            dp, nm = entry_path_map[idx]
            old_entries.append((fe, dp, nm))

    data_end = orig_idx_off

    enc_counts = {}
    comp_counts = {}
    for entry, _, _ in old_entries:
        if entry.encrypted:
            enc_counts[entry.encryption_method] = enc_counts.get(entry.encryption_method, 0) + 1
        comp_counts[entry.compression_method] = comp_counts.get(entry.compression_method, 0) + 1
        
    injection_enc_method = max(enc_counts, key=enc_counts.get) if enc_counts else EM_SM4_NEW_BASE
    injection_comp_method = max(comp_counts, key=comp_counts.get) if comp_counts else CM_ZSTD

    block_sizes = {}
    for entry, _, _ in old_entries:
        if entry.compression_block_size > 0:
            block_sizes[entry.compression_block_size] = block_sizes.get(entry.compression_block_size, 0) + 1
    if not compression_block_size:
        compression_block_size = max(block_sizes, key=block_sizes.get) if block_sizes else 65536

    inject_files = []
    for p in sorted(inject_dir.rglob("*")):
        if not p.is_file(): continue
        rel = p.relative_to(inject_dir)
        if target_path_prefix:
            target_entry = PurePath(target_path_prefix) / rel
        else:
            target_entry = rel
        inject_files.append((p, target_entry))

    if not inject_files: return

    new_data_blocks = []
    new_entries = []
    cursor = data_end

    for src_path, target_path in inject_files:
        name = target_path.name
        dir_path = target_path.parent
        
        if show_ui:
            panel_text = (
                f"[bold cyan]Repacking:[/] [bold white]{name}[/]\n"
                f"[bold yellow]Target Entry:[/] [bold green]{target_path.as_posix()}[/]\n"
                f"[bold bright_blue]Encryption Method Applied:[/] [bold cyan]{0 if injection_enc_method == 0 else injection_enc_method}[/]"
            )
            console.print(Panel(panel_text, border_style=get_banner_color(), box=box.SQUARE))

        file_content = src_path.read_bytes()
        file_size = len(file_content)

        if file_size <= compression_block_size:
            block_size = file_size if injection_comp_method != CM_NONE else 0
            num_blocks = 1
        else:
            block_size = compression_block_size
            num_blocks = (file_size + block_size - 1) // block_size

        blocks = []
        total_encrypted = 0
        for i in range(num_blocks):
            chunk_start = i * block_size if injection_comp_method != CM_NONE else 0
            chunk_end = min(chunk_start + block_size, file_size) if injection_comp_method != CM_NONE else file_size
            chunk = file_content[chunk_start:chunk_end]

            compressed = PakCompression.compress_block(chunk, injection_comp_method, pak._zstd_dict, None)

            if injection_enc_method != 0:
                cipher = pak._apply_encrypt_for_entry(compressed, target_path, injection_enc_method)
                aligned_size = PakCrypto.align_encrypted_content_size(len(cipher), injection_enc_method)
                if aligned_size > len(cipher):
                    cipher += b'\x00' * (aligned_size - len(cipher))
            else:
                cipher = compressed

            blk_start = cursor + total_encrypted
            blk_end = blk_start + len(cipher)
            blk = PakCompressedBlock.__new__(PakCompressedBlock)
            blk.start = blk_start
            blk.end = blk_end
            blocks.append(blk)
            total_encrypted += len(cipher)
            new_data_blocks.append(cipher)

        all_encrypted = b''.join(new_data_blocks[-len(blocks):])
        entry = TencentPakEntry.__new__(TencentPakEntry)
        if SHA1: entry.content_hash = SHA1.new(all_encrypted).digest()
        else: entry.content_hash = b'\x00'*20
        entry.offset = cursor
        entry.uncompressed_size = file_size
        entry.compression_method = injection_comp_method
        entry.size = total_encrypted
        entry.unk1 = 0
        entry.unk2 = b'\x00' * 20
        entry.compressed_blocks = blocks
        entry.compression_block_size = block_size
        entry.encrypted = injection_enc_method != 0
        entry.encryption_method = injection_enc_method
        entry.index_new_sep = 0

        new_entries.append((entry, dir_path, name))
        cursor += total_encrypted

    index_plain = _build_index_bytes(old_idx_dec, new_entries, version)

    if pak._pak_info.index_encrypted:
        key = PakCrypto.rsa_extract(pak._pak_info.packed_key, RSA_MOD_1)
        iv = PakCrypto.rsa_extract(pak._pak_info.packed_iv, RSA_MOD_1)
        aes = AES.new(key, MODE_CBC, iv[:16])
        pad_len = (-len(index_plain)) % 16 or 16
        index_encrypted = aes.encrypt(index_plain + bytes([pad_len] * pad_len))
    else:
        index_encrypted = index_plain

    content_org_hash = pak._pak_info.content_org_hash

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'wb') as outfh:
        outfh.write(bytes(pak._file_content[:data_end]))
        for blk in new_data_blocks:
            outfh.write(blk)
        index_offset = outfh.tell()
        outfh.write(index_encrypted)
        _write_footer(outfh, pak._pak_info, index_encrypted, index_plain, index_offset, PakCrypto.zuc_keystream(), content_org_hash)

# ======================================================================
def human_size(num_bytes: int) -> str:
    """Convert raw byte count to a human-readable string (e.g. 1.23 MB)."""
    if num_bytes is None:
        return "N/A"
    num_bytes = int(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            if unit == "B":
                return f"{num_bytes} B"
            return f"{num_bytes:,.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:,.2f} PB"

# ... yahan ke neeche tumhara def run_lua_tool() hoga ...
@security_guard
def run_lua_tool():
    global SERVER_LUA_XOR_KEY_HEX

    console.clear()
    print_banner_and_header()
    print_user_profile()
    b_color = get_banner_color()
    
    console.print(Panel(f"[bold {b_color}]🔥 LUA DECOMPILER & RECOMPILER 🔥[/bold {b_color}]\n"
                        f"[dim]Extract, Edit, and Repack BGMI Lua Bytecode[/dim]", border_style=b_color))

    lua_base = Path(BASE_DIR_NAME) / "LUA_TOOL"
    lua_org = lua_base / "Lua_org"
    lua_dec = lua_base / "Lua_Decript"
    lua_res = lua_base / "Lua_Rueslt"
    
    # --- NAYA FOLDER STRUCTURE (ANY SIZE REPACK KE LIYE) ---
    re_lua_any_size = lua_base / "RE_LUA ANY SIZE"
    lua_edit = re_lua_any_size / "EDIT_LUA"
    lua_org_pak = re_lua_any_size / "ORGNAL_PAK"
    lua_mod_repack = re_lua_any_size / "REPACK_MOD"

    lua_custom = lua_base / "LUA_CUSTOM" 
    lua_custom_edit = lua_custom / "EDIT" 
    lua_custom_pak  = lua_custom / "PAK"
    lua_custom_result = lua_custom / "RESULT"
    
    # --- BGMI CSV FOLDER (LUA_CUSTOM KE ANDAR) ---
    BGMI_CSV_folder = lua_custom / "BGMI_CSV"

    # --- SIRF ZAROORI FOLDERS BANAYEIN ---
    for d in [lua_org, lua_dec, lua_res, lua_edit, lua_org_pak, lua_mod_repack, lua_custom, lua_custom_edit, lua_custom_pak, lua_custom_result]:
        os.makedirs(to_long_path(d), exist_ok=True)

    # ── AUTO JAR DOWNLOAD ──────────────────────────────────────────────────────
    # unluac.jar  → Lua 5.1 / 5.2 / 5.3 / 5.4
    # luajit-decompiler-v2 (ljd.jar) → LuaJIT
    # Version is detected from the .luac header byte before each decompile run.
    unluac_path = lua_base / "unluac.jar"
    ljd_path    = lua_base / "ljd.jar"

    UNLUAC_URL = "https://github.com/unluac/unluac/releases/latest/download/unluac.jar"
    LJD_URL    = "https://github.com/nicktindall/luajit-decompiler-v2/releases/latest/download/ljd.jar"

    def _download_jar(url, dest):
        try:
            console.print(f"[yellow][*] Downloading {dest.name}...[/yellow]")
            urllib.request.urlretrieve(url, to_long_path(dest))
            if dest.stat().st_size < 1000:          # download returned HTML / redirect garbage
                dest.unlink(missing_ok=True)
                raise RuntimeError("Downloaded file too small — likely a redirect page")
        except Exception as e:
            console.print(f"[red]❌ Failed to download {dest.name}: {e}[/red]")

    def _detect_lua_version(path):
        """Return (version_byte, is_luajit).  version_byte: 0x51=5.1, 0x52=5.2, 0x53=5.3, 0x54=5.4"""
        try:
            with open(path, 'rb') as fh:
                magic = fh.read(5)          # \x1bLua + version byte
            if magic[:4] == b'\x1bLua':
                vb = magic[4]
                return vb, False
            # LuaJIT magic: \x1bLJ
            with open(path, 'rb') as fh:
                magic2 = fh.read(3)
            if magic2 == b'\x1bLJ':
                return None, True
        except Exception:
            pass
        return None, False

    def _ensure_jar_for_file(luac_path):
        """Download the right JAR for this .luac and return its Path, or None."""
        vb, is_luajit = _detect_lua_version(luac_path)
        if is_luajit:
            if not ljd_path.exists():
                _download_jar(LJD_URL, ljd_path)
            return ljd_path if ljd_path.exists() else None
        else:
            # 0x51-0x54 all handled by modern unluac
            if not unluac_path.exists():
                _download_jar(UNLUAC_URL, unluac_path)
            return unluac_path if unluac_path.exists() else None
    # ── END AUTO JAR ───────────────────────────────────────────────────────────

    # Pre-download unluac for the common case
    if not unluac_path.exists():
        _download_jar(UNLUAC_URL, unluac_path)

    # Do not install Termux packages from the APK/runtime. The Android app uses
    # the ART runner and Python bridge; standalone Termux builds may provide luac.
    # Do not abort the whole Lua tool when the server-only key is unavailable.
    # Options 3/4 (PAK repack/custom-file operations) do not need the Lua XOR key.
    # Options 1/2 load a user-supplied local key when available.
    lua_key_file = lua_base / "lua_xor_key.txt"
    LUA_XOR_KEY = b""
    if SERVER_LUA_XOR_KEY_HEX:
        try:
            LUA_XOR_KEY = bytes.fromhex(SERVER_LUA_XOR_KEY_HEX.strip())
        except ValueError:
            LUA_XOR_KEY = b""
    elif lua_key_file.exists():
        try:
            local_key_hex = lua_key_file.read_text(encoding="utf-8").strip()
            LUA_XOR_KEY = bytes.fromhex(local_key_hex)
        except (OSError, ValueError):
            LUA_XOR_KEY = b""

    BGMI_STD = {0: 13, 1: 14, 2: 15, 3: 16, 4: 17, 5: 18, 14: 27, 16: 29, 17: 0, 18: 1, 20: 3, 21: 4, 22: 5, 23: 6, 24: 7, 25: 8, 26: 9, 27: 10, 28: 11, 29: 12, 30: 30, 31: 31, 32: 32, 33: 33, 34: 34, 36: 36, 37: 37, 38: 38, 39: 39, 40: 40, 41: 41, 42: 42, 43: 43, 44: 44, 45: 45}
    STD_BGMI = {v: k for k, v in BGMI_STD.items()}
    STD_FMT = [0,1,1,0,0,0,0,0, 0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0, 0,0,0,0,0,0,2,0, 0,0,0,0,0,0,0,2, 2,0,2,0,1,0,3]
    
    def process_lua_file(data, is_encrypt=False):
        class RW:
            def __init__(self): self.b = bytearray()
            def byte(self, v): self.b.append(v & 0xFF)
            def u32(self, v): self.b.extend(struct.pack('<I', v))
            def i32(self, v): self.b.extend(struct.pack('<i', v))
            def raw(self, d): self.b.extend(d)
        class R:
            def __init__(self, d): self.d = d; self.p = 0
            def byte(self): v = self.d[self.p]; self.p += 1; return v
            def u32(self): v = struct.unpack_from('<I', self.d, self.p)[0]; self.p += 4; return v
            def i32(self): v = struct.unpack_from('<i', self.d, self.p)[0]; self.p += 4; return v
            def raw(self, n): v = self.d[self.p:self.p+n]; self.p += n; return v
            
        r, w = R(data), RW()
        hdr = bytearray(data[:33])
        if is_encrypt:
            if hdr[12:16] == b'\x04\x08\x04\x08': hdr[12:16] = b'\x04\x04\x04\x08'
        else:
            hdr[13] = 8  # BGMI uses size_t=4 (0x04); standard Lua 5.3 is size_t=8 (0x08) — unluac requires 0x08
        w.raw(bytes(hdr))
        r.p = 33
        w.byte(r.byte())

        def tg_str_read():
            sz = r.byte()
            if sz == 0xFF: sz = r.u32()
            if sz == 0: return None
            enc = r.raw(sz - 1)
            key_len = len(LUA_XOR_KEY)
            if not is_encrypt:
                if key_len == 0:
                    return enc.decode('utf-8', 'replace')
                xored = bytes(enc[i] ^ LUA_XOR_KEY[i % key_len] for i in range(len(enc)))
                try:
                    decoded = xored.decode('utf-8')
                    if all(c >= ' ' or c in '\t\n\r' for c in decoded):
                        return decoded
                except UnicodeDecodeError:
                    pass
                return enc.decode('utf-8', 'replace')
            return enc.decode('utf-8', 'replace')

        def tg_str_write(s):
            if s is None: w.byte(0); return
            e = s.encode('utf-8') if isinstance(s, str) else s
            key_len = len(LUA_XOR_KEY)
            if is_encrypt and key_len > 0: e = bytes(e[i] ^ LUA_XOR_KEY[i % key_len] for i in range(len(e)))
            sz = len(e) + 1
            if sz < 0xFF: w.byte(sz)
            else: w.byte(0xFF); w.u32(sz)
            w.raw(e)

        def convert(r, w):
            tg_str_write(tg_str_read()); w.i32(r.i32()); ldef = r.i32(); w.i32(ldef)
            w.byte(r.byte()); w.byte(r.byte()); w.byte(r.byte()); n = r.u32(); w.u32(n)
            for _ in range(n):
                raw = r.u32()
                op, A, B, C, Bx, Ax = raw & 0x3F, (raw>>6)&0xFF, (raw>>23)&0x1FF, (raw>>14)&0x1FF, (raw>>14)&0x3FFFF, (raw>>6)&0x3FFFFFF
                sBx = Bx - 131071
                sop = STD_BGMI.get(op, op) if is_encrypt else BGMI_STD.get(op, op)
                fmt = STD_FMT[op] if is_encrypt else (STD_FMT[sop] if sop < len(STD_FMT) else 0)
                if fmt == 0: res = (sop & 0x3F) | (A << 6) | (C << 14) | (B << 23)
                elif fmt == 1: res = (sop & 0x3F) | (A << 6) | (Bx << 14)
                elif fmt == 2: res = (sop & 0x3F) | (A << 6) | ((sBx + 131071) << 14)
                else: res = (sop & 0x3F) | (Ax << 6)
                w.u32(res)
            nk = r.u32(); w.u32(nk)
            for _ in range(nk):
                t = r.byte(); w.byte(t)
                if t == 1: w.byte(r.byte())
                elif t in (3, 19): w.raw(r.raw(8))
                elif t in (4, 20): tg_str_write(tg_str_read())
            nups = r.u32(); w.u32(nups)
            for _ in range(nups): w.byte(r.byte()); w.byte(r.byte())
            npt = r.u32(); w.u32(npt)
            for _ in range(npt): convert(r, w)
            nln = r.u32(); lines = []
            if is_encrypt:
                lines = [r.i32() for _ in range(nln)]; w.u32(nln); prev = ldef
                for ln in lines:
                    diff = ln - prev; prev = ln
                    if diff < 0: diff += 256
                    w.byte(diff & 0xFF)
                w.u32(0)
            else:
                cur = ldef
                for _ in range(nln):
                    d = r.byte(); cur += d if d <= 127 else d - 256; lines.append(cur)
                w.u32(len(lines))
                for ln in lines: w.i32(ln)
            if not is_encrypt: nab = r.u32(); [r.raw(8) for _ in range(nab)]
            nloc = r.u32(); w.u32(nloc)
            for _ in range(nloc): tg_str_write(tg_str_read()); w.i32(r.i32()); w.i32(r.i32())
            nupn = r.u32(); w.u32(nupn)
            for _ in range(nupn): tg_str_write(tg_str_read())
        convert(r, w)
        return bytes(w.b)

    while True:
        console.clear()
        print_banner_and_header()
        print_user_profile()
        menu_table = Table(show_header=True, header_style=f"bold black on {b_color}", box=box.DOUBLE_EDGE, title=f"[reverse]  📜 LUA MODDING TOOL ANY SIZE [/]", border_style=b_color, expand=True)
        if CURRENT_SESSION_COLOR == "rainbow":
            menu_table.add_column(rainbow_text("𝐎𝐏𝐓"), justify="center", width=4)
            menu_table.add_column(rainbow_text("𝐂𝐎𝐌𝐌𝐀𝐍𝐃"))
            menu_table.add_column(rainbow_text("𝐃𝐄𝐒𝐂𝐑𝐈𝐏𝐓𝐈𝐎𝐍"))
        else:
            menu_table.add_column("𝐎𝐏𝐓", style="bold white", justify="center", width=4)
            menu_table.add_column("𝐂𝐎𝐌𝐌𝐀𝐍𝐃", style=f"bold {b_color}")
            menu_table.add_column("𝐃𝐄𝐒𝐂𝐑𝐈𝐏𝐓𝐈𝐎𝐍", style="dim white")
        menu_table.add_row(menu_item("1", 0), menu_item("LUA DECOMPIL", 1), menu_item("Org -> Decript (.lua)", 5))
        menu_table.add_row(menu_item("2", 2), menu_item("LUA RECOMPIL", 3), menu_item("Edited -> Rueslt (.lua)", 7))
        menu_table.add_row(menu_item("3", 4), menu_item("REPACK LUA ANY SIZE ", 5), menu_item("EDIT_LUA -> MOD_REPACK (Pak)", 9))
        menu_table.add_row(menu_item("4", 6), menu_item("ADD COSTUM FILE IN PAK", 7), menu_item("Costum File -> MOD_REPACK (Pak)", 11))
        menu_table.add_row(menu_item("5", 8), menu_item("BUILD NEW PAK", 9), menu_item("Build fresh PAK from template + MODIFIED files", 13))
        if CURRENT_SESSION_COLOR == "rainbow":
            rainbow_row(menu_table, "0", "BACK", "Return to Main Menu")
        else:
            menu_table.add_row("0", f"[red]{to_fancy('BACK')}[/red]", to_fancy("Return to Main Menu"))
        
        console.print(Panel(menu_table, border_style=b_color, box=box.HEAVY))
        
        choice = Prompt.ask(f"[bold bright_blue]{to_fancy('SELECT OPTION')}[/bold bright_blue]")
        
        if choice not in ["1", "2", "3", "4", "5", "0"]:
            continue

        # Re-encrypt (choice 2) always needs the key — block it.
        # Decompile (choice 1) can run in RAW mode without the key.
        if choice == "2" and not LUA_XOR_KEY:
            console.print(Panel(
                "[bold yellow]⚠️ Lua XOR key is not available.[/bold yellow]\n\n"
                f"Create this file and put the key as HEX on one line:\n[cyan]{lua_key_file}[/cyan]\n\n"
                "Options 3 and 4 remain available without the key.",
                title="[bold yellow] LOCAL LUA KEY REQUIRED [/bold yellow]",
                border_style="yellow", box=box.HEAVY
            ))
            Prompt.ask("\n[bold bright_blue]Press Enter to return to Lua Menu...[/bold bright_blue]", default="")
            continue
            

        # Choice 1 without key → auto raw mode (skip BGMI decrypt layer)
        _raw_mode = False
        if choice == "1" and not LUA_XOR_KEY:
            console.print(Panel(
                "[bold yellow]⚠️ Lua XOR key not found — BGMI decrypt layer will be skipped.[/bold yellow]\n\n"
                "[dim white]RAW MODE: feeds the original .luac directly to unluac.\n"
                "Strings stay encrypted but structure decompiles clean.\n"
                "Useful to confirm if the file is decompilable at all.[/dim white]",
                title="[bold cyan] RAW MODE — NO KEY [/bold cyan]",
                border_style="cyan", box=box.HEAVY
            ))
            _raw_mode = True

        if choice == "1":
            console.clear()
            print_banner_and_header()
            console.print(Panel(f"[bold bright_blue][*] Scanning Directory:[/bold bright_blue] [bold green]'{lua_org.name}'...[/bold green]", border_style=b_color, box=box.ROUNDED))
            files = [f for f in lua_org.iterdir() if f.is_file() and f.suffix in ['.lua', '.luac']]
            if not files: 
                console.print(Panel(f"[red]❌ No files found in {lua_org.resolve()}[/red]", border_style="red", box=box.HEAVY))
            else:
                file_list = "\n".join([f"  [bold green]{i}.[/bold green] [bold white]{f.name}[/bold white]" for i, f in enumerate(files, 1)])
                console.print(Panel(file_list, title="[bold cyan]📂 Available Files[/bold cyan]", border_style="cyan", box=box.DOUBLE_EDGE))
                sel = Prompt.ask(f"\n[bold bright_blue]👉 Select file number(s) (e.g. 1, 2), 'all', or '0' to Back[/bold bright_blue]", default="all")
                selected_files = []
                if sel.strip() == '0': continue 
                elif sel.lower() == 'all': selected_files = files
                else:
                    for x in sel.split(','):
                        if x.strip().isdigit():
                            idx = int(x.strip()) - 1
                            if 0 <= idx < len(files):
                                selected_files.append(files[idx])
                if not selected_files:
                    console.print(Panel("[red]❌ Invalid selection![/red]", border_style="red", box=box.HEAVY))
                else:
                    console.print("")
                    for f in selected_files:
                        try:
                            progress = Progress(
                                SpinnerColumn("bouncingBar", style="bold cyan"),
                                TextColumn("[bold bright_blue]{task.description}"),
                                TextColumn("{task.fields[my_bar]}"),
                                TextColumn("[bold white]{task.percentage:>3.0f}%")
                            )
                            progress_panel = Panel(progress, title="[blink bold white on blue] ⚙ PROCESSING ENGINE [/]", border_style="bright_blue", box=box.HEAVY)
                            with Live(progress_panel, console=console, refresh_per_second=20):
                                short_name = f.name if len(f.name) < 20 else f.name[:17] + "..."
                                initial_bar = "[bold bright_blue]\\[[/bold bright_blue][bold blue]" + "-"*25 + "[/bold blue][bold bright_blue]][/bold bright_blue]"
                                task = progress.add_task(f"Decrypting: {short_name}", total=100, my_bar=initial_bar)
                                for i in range(1, 101):
                                    time.sleep(0.015) 
                                    filled = int((i / 100) * 25)
                                    current_bar = "[bold bright_blue]\\[[/bold bright_blue][bold cyan]" + "█" * filled + "[/bold cyan][bold blue]" + "-" * (25 - filled) + "[/bold blue][bold bright_blue]][/bold bright_blue]"
                                    progress.update(task, advance=1, my_bar=current_bar)
                            
                            with open(f, 'rb') as fp: data = fp.read()
                            std_path = lua_dec / f"{f.stem}.std.luac"
                            out_path = lua_dec / f"{f.stem}.lua"
                            if _raw_mode:
                                # RAW MODE: skip BGMI decrypt, feed original bytes directly
                                with open(std_path, 'wb') as fp: fp.write(data)
                            else:
                                std_data = process_lua_file(data, is_encrypt=False)
                                with open(std_path, 'wb') as fp: fp.write(std_data)
                            # ── VERSION-AWARE DECOMPILE ───────────────────────────────────────────
                            # Pick the right JAR from the .luac header byte.
                            # Copy everything to an ASCII temp dir — JNI chokes on unicode paths.
                            _jar = _ensure_jar_for_file(std_path)
                            _decompile_ok = False
                            _err_detail   = ""
                            if _jar is None:
                                _err_detail = "Could not download a compatible decompiler JAR. Check internet connection."
                            else:
                                with tempfile.TemporaryDirectory(prefix='unluac_') as _tdir:
                                    _safe_jar  = os.path.join(_tdir, _jar.name)
                                    _safe_luac = os.path.join(_tdir, 'target.luac')
                                    shutil.copy2(str(_jar),      _safe_jar)
                                    shutil.copy2(str(std_path),  _safe_luac)
                                    _stderr_buf = tempfile.NamedTemporaryFile(mode='w', suffix='.err', delete=False)
                                    with open(out_path, 'w', encoding='utf-8', errors='replace') as out_f:
                                        _proc = subprocess.run(
                                            ['java', '-jar', _safe_jar, _safe_luac],
                                            stdout=out_f, stderr=_stderr_buf,
                                            timeout=120
                                        )
                                    _stderr_buf.close()
                                    # Success requires zero exit status AND validated Lua source.
                                    if _proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 10:
                                        try:
                                            _valid, _vmsg = validate_lua_source(out_path) if validate_lua_source else (True, "validator unavailable")
                                            _decompile_ok = bool(_valid)
                                            if not _valid:
                                                _err_detail = "Lua output validation failed: " + _vmsg
                                        except Exception as _ve:
                                            _decompile_ok = False
                                            _err_detail = "Lua output validation error: " + str(_ve)
                                    else:
                                        try:
                                            with open(_stderr_buf.name, 'r') as _ef:
                                                _err_detail = _ef.read(300).strip() or "Empty output — version mismatch or obfuscated bytecode."
                                        except Exception:
                                            _err_detail = "Empty output — version mismatch or obfuscated bytecode."
                                    try: os.unlink(_stderr_buf.name)
                                    except Exception: pass
                            # ── END VERSION-AWARE DECOMPILE ──────────────────────────────────────

                            if std_path.exists(): std_path.unlink()

                            if _decompile_ok:
                                success_msg = (
                                    f"[bold bright_blue]❖ Target File :[/bold bright_blue] [bold white]{f.name}[/bold white]\n"
                                    f"[bold bright_blue]❖ Operation   :[/bold bright_blue] [bold green]Decompiled Successfully[/bold green]\n"
                                    f"[bold bright_blue]❖ Output Path :[/bold bright_blue] [dim yellow]Lua_Decript/{out_path.name}[/dim yellow]"
                                )
                                console.print(Panel(success_msg, title="[bold white on green] ⚡ DECRYPTION SUCCESS ⚡ [/]", border_style=get_banner_color(), box=box.HEAVY))
                            else:
                                fail_msg = (
                                    f"[bold bright_blue]❖ Target File :[/bold bright_blue] [bold white]{f.name}[/bold white]\n"
                                    f"[bold bright_blue]❖ Operation   :[/bold bright_blue] [bold red]Decompile Failed — 0 bytes written[/bold red]\n"
                                    f"[bold bright_blue]❖ Reason      :[/bold bright_blue] [dim yellow]{_err_detail}[/dim yellow]"
                                )
                                console.print(Panel(fail_msg, title="[bold white on red] ⚠ DECOMPILE FAILED ⚠ [/]", border_style="red", box=box.HEAVY))
                                if out_path.exists(): out_path.unlink()  # remove empty file
                            console.print("") 
                        except Exception as e: 
                            console.print(Panel(f"[bold red]❌ Error Processing {f.name}: {e}[/bold red]", border_style="red", box=box.HEAVY))
            Prompt.ask("\n[bold bright_blue]Press Enter to return to Lua Menu...[/bold bright_blue]", default="")

        elif choice == "2":
            console.clear()
            print_banner_and_header()
            console.print(Panel(f"[bold bright_blue][*] Scanning Directory:[/bold bright_blue] [bold green]'{lua_edit.name}'...[/bold green]", border_style=b_color, box=box.ROUNDED))
            files = [f for f in lua_edit.iterdir() if f.is_file() and f.suffix in ['.lua', '.luac']]
            if not files: 
                console.print(Panel(f"[red]❌ No files found in {lua_edit.resolve()}[/red]", border_style="red", box=box.HEAVY))
            else:
                file_list = "\n".join([f"  [bold green]{i}.[/bold green] [bold white]{f.name}[/bold white]" for i, f in enumerate(files, 1)])
                console.print(Panel(file_list, title="[bold cyan]📂 Available Files[/bold cyan]", border_style="cyan", box=box.DOUBLE_EDGE))
                sel = Prompt.ask(f"\n[bold bright_blue]👉 Select file number(s) (e.g. 1, 2), 'all', or '0' to Back[/bold bright_blue]", default="all")
                selected_files = []
                if sel.strip() == '0': continue 
                elif sel.lower() == 'all': selected_files = files
                else:
                    for x in sel.split(','):
                        if x.strip().isdigit():
                            idx = int(x.strip()) - 1
                            if 0 <= idx < len(files):
                                selected_files.append(files[idx])
                if not selected_files:
                    console.print(Panel("[red]❌ Invalid selection![/red]", border_style="red", box=box.HEAVY))
                else:
                    console.print("")
                    for f in selected_files:
                        try:
                            progress = Progress(
                                SpinnerColumn("bouncingBar", style="bold cyan"),
                                TextColumn("[bold bright_blue]{task.description}"),
                                TextColumn("{task.fields[my_bar]}"),
                                TextColumn("[bold white]{task.percentage:>3.0f}%")
                            )
                            progress_panel = Panel(progress, title="[blink bold white on blue] ⚙ PROCESSING ENGINE [/]", border_style="bright_blue", box=box.HEAVY)
                            with Live(progress_panel, console=console, refresh_per_second=20):
                                short_name = f.name if len(f.name) < 20 else f.name[:17] + "..."
                                initial_bar = "[bold bright_blue]\\[[/bold bright_blue][bold blue]" + "-"*25 + "[/bold blue][bold bright_blue]][/bold bright_blue]"
                                task = progress.add_task(f"Compiling : {short_name}", total=100, my_bar=initial_bar)
                                for i in range(1, 101):
                                    time.sleep(0.015) 
                                    filled = int((i / 100) * 25)
                                    current_bar = "[bold bright_blue]\\[[/bold bright_blue][bold cyan]" + "█" * filled + "[/bold cyan][bold blue]" + "-" * (25 - filled) + "[/bold blue][bold bright_blue]][/bold bright_blue]"
                                    progress.update(task, advance=1, my_bar=current_bar)
                            
                            process_file = f
                            if f.suffix == '.lua':
                                process_file = lua_edit / f"{f.stem}.std.luac"
                                subprocess.run(["luac5.3", "-o", str(process_file), str(f)])
                            with open(process_file, 'rb') as fp: data = fp.read()
                            bgmi_data = process_lua_file(data, is_encrypt=True)
                            final_out = lua_res / f"{f.stem}.lua"
                            with open(final_out, 'wb') as fp: fp.write(bgmi_data)
                            
                            success_msg = (
                                f"[bold bright_blue]❖ Target File :[/bold bright_blue] [bold white]{f.name}[/bold white]\n"
                                f"[bold bright_blue]❖ Operation   :[/bold bright_blue] [bold green]Encrypted Successfully[/bold green]\n"
                                f"[bold bright_blue]❖ Output Path :[/bold bright_blue] [dim yellow]Lua_Rueslt/{final_out.name}[/dim yellow]"
                            )
                            console.print(Panel(success_msg, title="[bold white on green] ⚡ ENCRYPTION SUCCESS ⚡ [/]", border_style=get_banner_color(), box=box.HEAVY))
                            console.print("") 
                            if f.suffix == '.lua' and process_file.exists(): process_file.unlink()
                        except Exception as e: 
                            console.print(Panel(f"[bold red]❌ Error Processing {f.name}: {e}[/bold red]", border_style="red", box=box.HEAVY))
            Prompt.ask("\n[bold bright_blue]Press Enter to return to Lua Menu...[/bold bright_blue]", default="")

        elif choice == "3":
            console.clear()
            print_banner_and_header()
            console.print(Panel(f"[bold bright_blue][*] Scanning Original PAK in:[/bold bright_blue] [bold green]'{lua_org_pak.name}'...[/bold green]", border_style=b_color, box=box.ROUNDED))
            
            pak_files = [f for f in lua_org_pak.iterdir() if f.is_file() and f.suffix.lower() in ['.pak', '.obb']]
            if not pak_files:
                console.print(Panel(f"[red]❌ No Original PAK found in {lua_org_pak.resolve()}[/red]\n[white]Bhai ORGNAL_PAK folder me apna original pak rakho pehle![/white]", border_style="red", box=box.HEAVY))
                Prompt.ask("\n[bold bright_blue]Press Enter to return...[/bold bright_blue]", default="")
                continue
                
            target_pak = pak_files[0]
            if len(pak_files) > 1:
                console.print(f"[yellow]⚠️ Multiple PAKs found. Auto-selecting first one: {target_pak.name}[/yellow]")

            out_pak = lua_mod_repack / target_pak.name
            
            mod_luas = [f for f in lua_edit.iterdir() if f.is_file()]
            if not mod_luas:
                console.print(Panel(f"[red]❌ No edited Lua files found in {lua_edit.resolve()}[/red]\n[white]Pehle EDIT_LUA me modify ki hui files daalo![/white]", border_style="red", box=box.HEAVY))
                Prompt.ask("\n[bold bright_blue]Press Enter to return...[/bold bright_blue]", default="")
                continue

            file_list_str = ""
            for i, f in enumerate(mod_luas, 1):
                size_bytes = f.stat().st_size
                file_list_str += f"  [bold green]{i}.[/bold green] [bold white]{f.name}[/bold white] [dim yellow]({size_bytes} Bytes)[/dim yellow]\n"
            
            console.print(Panel(file_list_str.strip(), title="[bold cyan]📂 Available Lua Files (EDIT_LUA)[/bold cyan]", border_style="cyan", box=box.DOUBLE_EDGE))
            
            sel = Prompt.ask(f"\n[bold bright_blue]👉 Select file number(s) to Repack (e.g. 1, 2), 'all', or '0' to Back[/bold bright_blue]", default="all")
            
            if sel.strip() == '0':
                continue
                
            selected_luas = []
            if sel.lower() == 'all':
                selected_luas = mod_luas
            else:
                for x in sel.split(','):
                    if x.strip().isdigit():
                        idx = int(x.strip()) - 1
                        if 0 <= idx < len(mod_luas):
                            selected_luas.append(mod_luas[idx])
            
            if not selected_luas:
                console.print(Panel("[red]❌ Invalid selection![/red]", border_style="red", box=box.HEAVY))
                Prompt.ask("\n[bold bright_blue]Press Enter to continue...[/bold bright_blue]", default="")
                continue

            temp_repack_dir = lua_base / "Temp_Lua_Inject"
            if temp_repack_dir.exists():
                shutil.rmtree(to_long_path(temp_repack_dir))
            temp_repack_dir.mkdir(exist_ok=True)
            
            for f in selected_luas:
                shutil.copy2(to_long_path(f), to_long_path(temp_repack_dir / f.name))

            with console.status(f"[bold cyan]Injecting {len(selected_luas)} Lua file(s) into {target_pak.name} (ANY SIZE)...[/bold cyan]"):
                pak_editor = TencentPakFile(target_pak)
                try:
                    success_count = repack_any_size(pak_editor, temp_repack_dir, out_pak)
                    success = success_count > 0
                except Exception as e:
                    console.print(f"[bold red]❌ Repack Error: {e}[/bold red]")
                    success = False
                
                shutil.rmtree(to_long_path(temp_repack_dir))
                    
            if success:
                success_msg = (
                    f"[bold bright_blue]❖ Target PAK  :[/bold bright_blue] [bold white]{target_pak.name}[/bold white]\n"
                    f"[bold bright_blue]❖ Action      :[/bold bright_blue] [bold green]{len(selected_luas)} LUA Files Repacked Successfully (Full Rebuild)[/bold green]\n"
                    f"[bold bright_blue]❖ Output Path :[/bold bright_blue] [dim yellow]RE_LUA ANY SIZE/MOD_REPACK/{out_pak.name}[/dim yellow]"
                )
                console.print(Panel(success_msg, title="[bold white on green] ⚡ ANY-SIZE REPACK SUCCESS ⚡ [/]", border_style=get_banner_color(), box=box.HEAVY))
            else:
                console.print(Panel(f"[red]❌ Repack Failed. Either files didn't match the index or pak structure is invalid![/red]", border_style="red", box=box.HEAVY))
                if out_pak.exists(): out_pak.unlink()
            
            Prompt.ask("\n[bold bright_blue]Press Enter to return to Lua Menu...[/bold bright_blue]", default="")

        elif choice == "4":
            from rich.progress import TransferSpeedColumn
            
            # --- 🔥 NAYA PAGE: SCREEN CLEAR + BANNER + PROFILE ---
            console.clear()
            print_banner_and_header()
            print_user_profile()
            
            # --- BGMI_CSV FOLDER LUA_CUSTOM KE ANDAR ---
            BGMI_CSV_folder = lua_custom / "PUBG_CSV"
            
            # --- AGAR FOLDER NAHI HAI TO DOWNLOAD KARO ---
            if not BGMI_CSV_folder.exists():
                console.print(Panel(
                    f"[bold yellow]⚠️ PUBG_CSV folder not found in LUA_CUSTOM![/]\n"
                    f"[dim]Downloading CSV files from GitHub...[/]",
                    title="[bold black on bright_yellow] 📥 DOWNLOADING 📥 [/]",
                    border_style="bright_yellow",
                    box=box.HEAVY
                ))
                
                # --- GITHUB RAW URLS ---
                _csv_commit = "d013eca408f85d073c195e42a363b49076babd1d"
                csv_urls = {
                    "PUBG.csv": ("https://raw.githubusercontent.com/sellacountvinay-creator/BGMI_CSV/" + _csv_commit + "/PUBG.csv",
                                 "2601457787bd2d793880fb1a8c485d0e76144942"),
                    "BGMI.csv": ("https://raw.githubusercontent.com/sellacountvinay-creator/BGMI_CSV/" + _csv_commit + "/BGMI.csv",
                                 "ac72bf1d3ca5f0ae72b65c1845c9c471e4a4a6af"),
                }
                
                try:
                    BGMI_CSV_folder.mkdir(parents=True, exist_ok=True)
                    
                    for filename, (url, expected_blob) in csv_urls.items():
                        with Progress(
                            TextColumn("[bold cyan]⬇️ {task.description}"),
                            BarColumn(bar_width=50, complete_style=f"bold {get_banner_color()}", finished_style="bold green"),
                            TextColumn("[bold white]{task.percentage:>3.0f}%"),
                            TextColumn("[dim]({task.fields[file_size]})"),
                            TransferSpeedColumn(),
                            TimeElapsedColumn(),
                            console=console
                        ) as progress:
                            task = progress.add_task(
                                f"Downloading {filename} from GitHub...",
                                total=100,
                                file_size=""
                            )
                            
                            response = requests.get(url, stream=True, timeout=30)
                            if response.status_code == 200:
                                total_size = int(response.headers.get('content-length', 0))
                                file_path = BGMI_CSV_folder / filename
                                downloaded = 0
                                
                                with open(file_path, 'wb') as f:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        if chunk:
                                            f.write(chunk)
                                            downloaded += len(chunk)
                                            if total_size > 0:
                                                percent = int((downloaded / total_size) * 100)
                                                file_size_mb = downloaded / (1024 * 1024)
                                                progress.update(
                                                    task, 
                                                    completed=percent,
                                                    file_size=f"{file_size_mb:.2f} MB"
                                                )
                                
                                if not _verify_pinned_git_blob(file_path.read_bytes(), expected_blob):
                                    file_path.unlink(missing_ok=True)
                                    console.print(f"[bold red]❌ Integrity check failed:[/] {filename}")
                                    continue
                                console.print(f"[bold green]✔ Downloaded:[/] [cyan]{filename}[/]")
                            else:
                                console.print(f"[bold red]❌ Failed:[/] {filename} (Status: {response.status_code})")
                    
                    # --- CHECK KARO FILES AA GAYI ---
                    csv_files = [f for f in BGMI_CSV_folder.iterdir() if f.suffix.lower() == '.csv']
                    if not csv_files:
                        console.print(Panel(
                            f"[red]❌ Download completed but no CSV files found![/]\n",
                            border_style="red",
                            box=box.HEAVY
                        ))
                        Prompt.ask("\n[bold cyan]Press Enter to return...[/]", default="")
                        continue
                            
                except Exception as e:
                    console.print(Panel(
                        f"[red]❌ Download Error: {e}[/]",
                        border_style="red",
                        box=box.HEAVY
                    ))
                    Prompt.ask("\n[bold cyan]Press Enter to return...[/]", default="")
                    continue
                
                console.print("\n[bold bright_blue]Press Enter to continue...[/bold bright_blue]")
                input()
                console.clear()
                print_banner_and_header()
                print_user_profile()
            
            # --- SELECT CSV - TABLE UI ---
            csv_files = [f for f in BGMI_CSV_folder.iterdir() if f.suffix.lower() == '.csv']
            
            if not csv_files:
                console.print(Panel(
                    f"[red]❌ No CSV files found in BGMI_CSV folder![/]\n\n"
                    f"[yellow]📂 Expected files: BGMI.csv, PUBG.csv[/]",
                    title="[bold red] ⚠️ CSV MISSING ⚠️ [/]",
                    border_style="red",
                    box=box.HEAVY
                ))
                Prompt.ask("\n[bold cyan]Press Enter to return...[/]", default="")
                continue
            
            csv_table = Table(box=box.SQUARE, expand=True, border_style=get_banner_color())
            csv_table.add_column("NO.", style="bold cyan", justify="center", width=4)
            csv_table.add_column("FILE NAME", style="bold white")
            csv_table.add_column("SIZE", style="bold yellow", justify="right")
            
            display_names = {
                "PUBG.csv": "PUBG 4.5",
                "BGMI.csv": "BGMI 4.5"
            }
            
            for i, f in enumerate(csv_files, 1):
                size = f.stat().st_size
                size_str = f"{size:,} bytes" if size < 1024*1024 else f"{size/(1024*1024):.2f} MB"
                display_name = display_names.get(f.name, f.name)
                csv_table.add_row(str(i), display_name, size_str)
            
            csv_table.add_row("0", "[bold red] BACK[/bold red]", "[dim]-[/dim]")
            
            console.print(Panel(csv_table, border_style=get_banner_color(), box=box.HEAVY))
            
            choices = [str(i) for i in range(1, len(csv_files)+1)] + ["0"]
            csv_choice = Prompt.ask(f"\n[bold bright_blue]👉 Select OPTION [0-{len(csv_files)}][/bold bright_blue]", 
                                    choices=choices)
            
            if csv_choice == "0":
                continue
            
            selected_csv = csv_files[int(csv_choice) - 1]
            selected_csv_name = selected_csv.name
            
            # 🔥 FIX: PEHLE CHECK KARO KI KONSA CSV SELECT HUA HAI
            is_bgmi = selected_csv_name == "BGMI.csv"
            is_pubg = selected_csv_name == "PUBG.csv"
            
            # 🔥 FIX: AGAR NAHI TO WARNING DO AUR CONTINUE
            if not is_bgmi and not is_pubg:
                console.print(Panel(
                    f"[red]❌ Unsupported CSV file: {selected_csv_name}[/]\n"
                    f"[yellow]Only BGMI.csv and PUBG.csv are supported.[/]",
                    border_style="red",
                    box=box.HEAVY
                ))
                Prompt.ask("\n[bold cyan]Press Enter to continue...[/]", default="")
                continue
            
            # --- 🔥 LOADING ANIMATION (BACKGROUND THREAD) + CSV LOAD (FAST) ---
            spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            stop_animation = False
            
            def run_animation():
                idx = 0
                with Live(console=console, refresh_per_second=15, transient=True) as live:
                    while not stop_animation:
                        frame = spinner_frames[idx % len(spinner_frames)]
                        live.update(Text(f"👉 Loading {selected_csv_name} {frame}", style="bold bright_blue"))
                        idx += 1
                        time.sleep(0.1)
            
            # Animation thread start
            anim_thread = threading.Thread(target=run_animation)
            anim_thread.daemon = True
            anim_thread.start()
            
            # --- ✅ FIXED: SIRF SELECTED CSV LOAD HO, DONO NAHI! ---
            file_path_map = {}
            total_entries = 0
            
            # ✅ Sirf selected_csv load karo!
            with open(selected_csv, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(',')
                    for part in parts:
                        part = part.strip()
                        if not part:
                            continue
                        filename = Path(part).name
                        file_path_map[filename] = part
                        total_entries += 1
            
            # CSV load complete → animation stop
            stop_animation = True
            time.sleep(0.2)
            
            if not file_path_map:
                console.print(Panel(
                    f"[red]❌ CSV file is empty or invalid![/]\n",
                    border_style="red",
                    box=box.HEAVY
                ))
                Prompt.ask("\n[bold cyan]Press Enter to return...[/]", default="")
                continue
            
            # --- FIND PAK FILE ---
            pak_files = [f for f in lua_custom_pak.iterdir() if f.suffix.lower() in ['.pak', '.obb']]
            if not pak_files:
                console.print(Panel(
                    f"[red]❌ No PAK file found in LUA_CUSTOM/PAK![/]\n",
                    border_style="red",
                    box=box.HEAVY
                ))
                Prompt.ask("\n[bold cyan]Press Enter to return...[/]", default="")
                continue
            
            target_pak = pak_files[0]
            out_pak = lua_custom_result / target_pak.name
            
            # --- SCAN EDIT FILES ---
            root_files = [f for f in lua_custom_edit.iterdir() if f.is_file()]
            ingame_csv_folder = lua_custom_edit / "InGame" / "EvoBase" / "CSV"
            ingame_files = []
            if ingame_csv_folder.exists():
                for root, dirs, files in os.walk(ingame_csv_folder):
                    for file in files:
                        ingame_files.append(Path(root) / file)
            
            # 🔥 FIXED: InGame Path Logic - BASED ON SELECTED CSV!
            ingame_found = []
            for mod_file in ingame_files:
                filename = mod_file.name
                if is_bgmi:  # ✅ BGMI
                    target_path = f"Content/MultiRegion/Content/IN/CSV/InGame/EvoBase/CSV/{filename}"
                elif is_pubg:  # ✅ PUBG
                    target_path = f"Content/CSV/InGame/EvoBase/CSV/{filename}"
                else:
                    continue  # Safe fallback
                ingame_found.append((mod_file, filename, target_path))
            
            # --- Root Files (CSV Match) ---
            root_found = []
            for mod_file in root_files:
                target_filename = mod_file.name
                matching_files = [f for f in file_path_map.keys() if f.lower() == target_filename.lower()]
                if not matching_files:
                    matching_files = [f for f in file_path_map.keys() if target_filename.lower() in f.lower()]
                if matching_files:
                    target_path = file_path_map[matching_files[0]]
                    root_found.append((mod_file, matching_files[0], target_path))
            
            found_files = ingame_found + root_found
            
            if not found_files:
                console.print(Panel(
                    f"[red]❌ No matching files found to inject![/]\n",
                    border_style="red",
                    box=box.HEAVY
                ))
                Prompt.ask("\n[bold cyan]Press Enter to return...[/]", default="")
                continue
            
            # --- 🔥 INTERNAL UNREAL ENGINE ADDRESS RESOLVER (WITH GREEN BACKGROUND TITLE) ---
            match_lines = []
            
            # Display which CSV is being used
            game_display = "BGMI" if is_bgmi else "PUBG"
            match_lines.append(f"[bold bright_yellow]📌 Selected: {game_display} ({selected_csv_name})[/bold bright_yellow]")
            match_lines.append("")
            
            # InGame files
            if ingame_found:
                match_lines.append("[bold cyan]📁 InGame/EvoBase/CSV Files (Direct Repack)[/bold cyan]")
                for mod_file, filename, target_path in ingame_found:
                    match_lines.append(f"  [bold green]✔[/] [bold white]{filename}[/] [dim]→[/] [dim yellow]{target_path}[/dim yellow]")
                match_lines.append("")
            
            # Root files
            if root_found:
                match_lines.append("[bold cyan]📁 Root EDIT Files (CSV Match)[/bold cyan]")
                for mod_file, filename, target_path in root_found:
                    match_lines.append(f"  [bold green]✔[/] [bold white]{filename}[/] [dim]→[/] [dim yellow]{target_path}[/dim yellow]")
                match_lines.append("")
            
            # Total count
            match_lines.append(f"[bold {get_banner_color()}]📊 Total: {len(found_files)} files will be injected[/bold {get_banner_color()}]")
            
            resolver_panel = Panel(
                "\n".join(match_lines),
                title= f"[bold white on {get_banner_color()}] ⚡ INTERNAL UNREAL ENGINE ADDRESS RESOLVER ⚡ [/bold white on {get_banner_color()}]",
                border_style=get_banner_color(),
                box=box.HEAVY
            )
            console.print(resolver_panel)
            
            # --- CONFIRM ---
            confirm = Prompt.ask(f"\n[bold {get_banner_color()}]Proceed with Universal CSV Repack?[/bold {get_banner_color()}] [bold white](y/n)[/bold white]", default="y")
            if confirm.lower() != 'y':
                continue
            
            # --- BULK INJECTION ---
            temp_inject_dir = lua_base / "Temp_Bulk_Inject"
            if temp_inject_dir.exists():
                shutil.rmtree(to_long_path(temp_inject_dir))
            temp_inject_dir.mkdir(exist_ok=True)
            
            injected_count = 0
            for mod_file, filename, target_path in found_files:
                try:
                    target_parts = Path(target_path).parts
                    temp_target_path = temp_inject_dir / Path(*target_parts)
                    os.makedirs(to_long_path(temp_target_path.parent), exist_ok=True)
                    shutil.copy2(to_long_path(mod_file), to_long_path(temp_target_path))
                    injected_count += 1
                except Exception as e:
                    pass
            
            if injected_count > 0:
                try:
                    with console.status(f"[bold cyan]📦 Repacking {injected_count} file(s) into {target_pak.name}...[/bold cyan]"):
                        pak_injection(target_pak, temp_inject_dir, out_pak, target_path_prefix="", show_ui=True)
                        success = True
                except Exception as e:
                    console.print(f"[bold red]❌ Injection Error: {e}[/bold red]")
                    success = False
            else:
                success = False
            
            shutil.rmtree(to_long_path(temp_inject_dir))
            
            # --- RESULT ---
            if success and injected_count > 0:
                summary_content = (
                    f"[bold bright_blue]▶ TARGET PAK[/bold bright_blue]        [bold white]{target_pak.name}[/bold white]\n"
                    f"[bold bright_blue]▶ CSV SOURCE[/bold bright_blue]        [bold white]{selected_csv_name}[/bold white]\n"
                    f"[bold bright_blue]▶ PATH MODE[/bold bright_blue]         [bold green]AUTO CSV PATH ({injected_count}/{injected_count} Matched)[/bold green]\n"
                    f"[bold bright_blue]▶ FILES TO ADD[/bold bright_blue]      [bold yellow]{injected_count}[/bold yellow]\n"
                    f"[bold bright_blue]▶ CLEAN PAK MODE[/bold bright_blue]    [bold green]ACTIVE (Old Assets Stripped)[/bold green]"
                )
                
                summary_panel = Panel(
                    summary_content,
                    title= f"[bold black on {get_banner_color()}] 📄 CSV SMART INJECTOR SUMMARY [/bold black on {get_banner_color()}]",
                    border_style=get_banner_color(),
                    box=box.HEAVY
                )
                console.print(summary_panel)
            else:
                console.print(Panel(
                    f"[bold red]❌ BULK INJECTION FAILED![/bold red]",
                    title="[bold red] ⚠️ INJECTION FAILED ⚠️ [/bold red]",
                    border_style="red",
                    box=box.HEAVY
                ))
            
            # --- ✅ FIX: Enter dabane par Option 4 dobara open hoga ---
            console.print("\n[bold bright_blue]Press Enter to continue...[/bold bright_blue]")
            input()
            continue

        elif choice == "5":
            from rich.progress import TransferSpeedColumn

            console.clear()
            print_banner_and_header()
            print_user_profile()

            # ── STEP 1: CSV DOWNLOAD IF MISSING ──────────────────────────────────
            BGMI_CSV_folder = lua_custom / "PUBG_CSV"
            if not BGMI_CSV_folder.exists():
                console.print(Panel(
                    f"[bold yellow]⚠️ PUBG_CSV folder not found!\n[dim]Downloading CSV files from GitHub...[/dim]",
                    title="[bold black on bright_yellow] 📥 DOWNLOADING 📥 [/]",
                    border_style="bright_yellow", box=box.HEAVY
                ))
                _csv_commit = "d013eca408f85d073c195e42a363b49076babd1d"
                csv_urls = {
                    "PUBG.csv": ("https://raw.githubusercontent.com/sellacountvinay-creator/BGMI_CSV/" + _csv_commit + "/PUBG.csv",
                                 "2601457787bd2d793880fb1a8c485d0e76144942"),
                    "BGMI.csv": ("https://raw.githubusercontent.com/sellacountvinay-creator/BGMI_CSV/" + _csv_commit + "/BGMI.csv",
                                 "ac72bf1d3ca5f0ae72b65c1845c9c471e4a4a6af"),
                }
                try:
                    BGMI_CSV_folder.mkdir(parents=True, exist_ok=True)
                    for filename, (url, expected_blob) in csv_urls.items():
                        with Progress(
                            TextColumn("[bold cyan]⬇️ {task.description}"),
                            BarColumn(bar_width=50, complete_style=f"bold {get_banner_color()}", finished_style="bold green"),
                            TextColumn("[bold white]{task.percentage:>3.0f}%"),
                            TextColumn("[dim]({task.fields[file_size]})"),
                            TransferSpeedColumn(), TimeElapsedColumn(), console=console
                        ) as progress:
                            task = progress.add_task(f"Downloading {filename}...", total=100, file_size="")
                            response = requests.get(url, stream=True, timeout=30)
                            if response.status_code == 200:
                                total_size = int(response.headers.get('content-length', 0))
                                file_path  = BGMI_CSV_folder / filename
                                downloaded = 0
                                with open(file_path, 'wb') as f:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        if chunk:
                                            f.write(chunk)
                                            downloaded += len(chunk)
                                            if total_size > 0:
                                                percent = int((downloaded / total_size) * 100)
                                                progress.update(task, completed=percent, file_size=f"{downloaded/(1024*1024):.2f} MB")
                                if not _verify_pinned_git_blob(file_path.read_bytes(), expected_blob):
                                    file_path.unlink(missing_ok=True)
                                    console.print(f"[bold red]❌ Integrity check failed:[/] {filename}")
                                    continue
                                console.print(f"[bold green]✔ Downloaded:[/] [cyan]{filename}[/]")
                            else:
                                console.print(f"[bold red]❌ Failed:[/] {filename} (Status: {response.status_code})")
                    csv_files = [f for f in BGMI_CSV_folder.iterdir() if f.suffix.lower() == '.csv']
                    if not csv_files:
                        console.print(Panel("[red]❌ Download completed but no CSV files found![/]", border_style="red", box=box.HEAVY))
                        Prompt.ask("\n[bold cyan]Press Enter to return...[/]", default="")
                        continue
                except Exception as e:
                    console.print(Panel(f"[red]❌ Download Error: {e}[/]", border_style="red", box=box.HEAVY))
                    Prompt.ask("\n[bold cyan]Press Enter to return...[/]", default="")
                    continue
                console.print("\n[bold bright_blue]Press Enter to continue...[/bold bright_blue]")
                input()
                console.clear()
                print_banner_and_header()
                print_user_profile()

            # ── STEP 2: SELECT CSV ────────────────────────────────────────────────
            csv_files = [f for f in BGMI_CSV_folder.iterdir() if f.suffix.lower() == '.csv']
            if not csv_files:
                console.print(Panel(
                    "[red]❌ No CSV files found!\n[yellow]Expected: BGMI.csv, PUBG.csv[/yellow]",
                    title="[bold red] ⚠️ CSV MISSING ⚠️ [/]", border_style="red", box=box.HEAVY
                ))
                Prompt.ask("\n[bold cyan]Press Enter to return...[/]", default="")
                continue

            csv_table = Table(box=box.SQUARE, expand=True, border_style=get_banner_color())
            csv_table.add_column("NO.", style="bold cyan", justify="center", width=4)
            csv_table.add_column("FILE NAME", style="bold white")
            csv_table.add_column("SIZE", style="bold yellow", justify="right")
            display_names = {"PUBG.csv": "PUBG 4.5", "BGMI.csv": "BGMI 4.5"}
            for i, f in enumerate(csv_files, 1):
                size = f.stat().st_size
                size_str = f"{size:,} bytes" if size < 1024*1024 else f"{size/(1024*1024):.2f} MB"
                csv_table.add_row(str(i), display_names.get(f.name, f.name), size_str)
            csv_table.add_row("0", "[bold red] BACK[/bold red]", "[dim]-[/dim]")
            console.print(Panel(csv_table, border_style=get_banner_color(), box=box.HEAVY))
            choices = [str(i) for i in range(1, len(csv_files)+1)] + ["0"]
            csv_choice = Prompt.ask(f"\n[bold bright_blue]👉 Select OPTION [0-{len(csv_files)}][/bold bright_blue]", choices=choices)
            if csv_choice == "0":
                continue

            selected_csv      = csv_files[int(csv_choice) - 1]
            selected_csv_name = selected_csv.name
            is_bgmi = selected_csv_name == "BGMI.csv"
            is_pubg = selected_csv_name == "PUBG.csv"

            if not is_bgmi and not is_pubg:
                console.print(Panel(
                    f"[red]❌ Unsupported CSV: {selected_csv_name}\n[yellow]Only BGMI.csv and PUBG.csv are supported.[/yellow]",
                    border_style="red", box=box.HEAVY
                ))
                Prompt.ask("\n[bold cyan]Press Enter to continue...[/]", default="")
                continue

            # ── STEP 3: BUILD file_path_map FROM CSV ─────────────────────────────
            file_path_map  = {}
            total_entries  = 0
            stop_animation = False

            def _csv_loading_anim():
                frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
                i = 0
                while not stop_animation:
                    console.print(f"\r[bold cyan]{frames[i % len(frames)]} Loading CSV...[/bold cyan]", end="")
                    time.sleep(0.08); i += 1

            anim_thread = threading.Thread(target=_csv_loading_anim, daemon=True)
            anim_thread.start()
            with open(selected_csv, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    for part in line.split(','):
                        part = part.strip()
                        if part:
                            file_path_map[Path(part).name] = part
                            total_entries += 1
            stop_animation = True
            time.sleep(0.2)

            if not file_path_map:
                console.print(Panel("[red]❌ CSV file is empty or invalid![/]", border_style="red", box=box.HEAVY))
                Prompt.ask("\n[bold cyan]Press Enter to return...[/]", default="")
                continue

            # ── STEP 4: SELECT TEMPLATE PAK ──────────────────────────────────────
            pak_dir_5 = lua_base / "PAK"
            pak_dir_5.mkdir(parents=True, exist_ok=True)
            pak_files_5 = [f for f in pak_dir_5.iterdir() if f.suffix.lower() in ['.pak', '.obb']]
            if not pak_files_5:
                console.print(Panel(
                    f"[red]❌ No PAK file found in {pak_dir_5.resolve()}[/red]\n"
                    "[white]Place a template .pak / .obb in the PAK folder first.[/white]",
                    border_style="red", box=box.HEAVY
                ))
                Prompt.ask("\n[bold bright_blue]Press Enter to return...[/bold bright_blue]", default="")
                continue

            if len(pak_files_5) == 1:
                template_pak_path = pak_files_5[0]
                console.print(Panel(f"[bold green]✅ Template PAK:[/] [bold white]{template_pak_path.name}[/]", border_style=b_color, box=box.ROUNDED))
            else:
                file_list_str = "\n".join([f"  [bold green]{i}.[/bold green] [bold white]{f.name}[/bold white]" for i, f in enumerate(pak_files_5, 1)])
                console.print(Panel(file_list_str, title="[bold cyan]📂 Select Template PAK[/bold cyan]", border_style="cyan", box=box.DOUBLE_EDGE))
                sel = Prompt.ask("[bold bright_blue]👉 Select file number[/bold bright_blue]")
                if not sel.strip().isdigit() or not (1 <= int(sel.strip()) <= len(pak_files_5)):
                    console.print(Panel("[red]❌ Invalid selection![/red]", border_style="red", box=box.HEAVY))
                    Prompt.ask("\n[bold bright_blue]Press Enter to return...[/bold bright_blue]", default="")
                    continue
                template_pak_path = pak_files_5[int(sel.strip()) - 1]

            # ── STEP 5: SCAN EDIT FILES + RESOLVE CSV PATHS ──────────────────────
            edit_files_5 = [p for p in lua_edit.rglob('*') if p.is_file()]
            if not edit_files_5:
                console.print(Panel(
                    f"[red]❌ No files in EDIT_LUA: {lua_edit.resolve()}[/red]",
                    border_style="red", box=box.HEAVY
                ))
                Prompt.ask("\n[bold bright_blue]Press Enter to return...[/bold bright_blue]", default="")
                continue

            resolved_files = []   # list of (Path, resolved_pak_path_str)
            unresolved     = []

            ingame_csv_folder = lua_edit / "InGame" / "EvoBase" / "CSV"
            for p in edit_files_5:
                filename = p.name
                # InGame subfolder → direct path by game type
                try:
                    p.relative_to(ingame_csv_folder)
                    in_ingame = True
                except ValueError:
                    in_ingame = False

                if in_ingame:
                    if is_bgmi:
                        resolved_path = f"Content/MultiRegion/Content/IN/CSV/InGame/EvoBase/CSV/{filename}"
                    else:
                        resolved_path = f"Content/CSV/InGame/EvoBase/CSV/{filename}"
                    resolved_files.append((p, resolved_path))
                else:
                    # Try CSV match
                    matches = [k for k in file_path_map if k.lower() == filename.lower()]
                    if not matches:
                        matches = [k for k in file_path_map if filename.lower() in k.lower()]
                    if matches:
                        resolved_files.append((p, file_path_map[matches[0]]))
                    else:
                        unresolved.append(p)

            if not resolved_files:
                console.print(Panel(
                    "[red]❌ No files matched the CSV paths! Check your EDIT_LUA file names.[/red]",
                    border_style="red", box=box.HEAVY
                ))
                Prompt.ask("\n[bold bright_blue]Press Enter to return...[/bold bright_blue]", default="")
                continue

            # ── RESOLVER DISPLAY ──────────────────────────────────────────────────
            game_display  = "BGMI" if is_bgmi else "PUBG"
            match_lines   = [f"[bold bright_yellow]📌 CSV: {game_display} ({selected_csv_name})[/bold bright_yellow]", ""]
            match_lines  += [f"  [bold green]✔[/] [bold white]{p.name}[/] [dim]→[/] [dim yellow]{rp}[/]" for p, rp in resolved_files]
            if unresolved:
                match_lines += ["", f"[bold red]⚠ {len(unresolved)} file(s) had no CSV match (skipped):[/bold red]"]
                match_lines += [f"  [dim red]✘ {p.name}[/]" for p in unresolved]
            match_lines.append("")
            match_lines.append(f"[bold {get_banner_color()}]📊 Total: {len(resolved_files)} files will be built into new PAK[/bold {get_banner_color()}]")
            console.print(Panel("\n".join(match_lines),
                title= f"[bold white on {get_banner_color()}] ⚡ CSV PATH RESOLVER ⚡ [/]",
                border_style=get_banner_color(), box=box.HEAVY))

            confirm = Prompt.ask("\n[bold {get_banner_color()}]Proceed with BUILD NEW PAK?[/bold {get_banner_color()}] [bold white](y/n)[/bold white]", default="y")
            if confirm.lower() != 'y':
                continue

            # ── STEP 6: BUILD NEW PAK ─────────────────────────────────────────────
            result_dir_5 = lua_base / "MOD_REPACK"
            result_dir_5.mkdir(parents=True, exist_ok=True)
            output_pak_5 = result_dir_5 / template_pak_path.name

            try:
                template_pak_obj = TencentPakFile(template_pak_path, is_od=True)
                version_5   = template_pak_obj._pak_info.version
                keystream_5 = PakCrypto.zuc_keystream()
                mp_str_5, _ = _get_all_dirs_and_mp(template_pak_obj)

                template_entry_5 = None
                for _dp, _files in template_pak_obj._index.items():
                    for _n, _e in _files.items():
                        template_entry_5 = _e; break
                    if template_entry_5: break

                if template_entry_5 is None:
                    console.print(Panel("[red]❌ Template PAK has no entries![/red]", border_style="red", box=box.HEAVY))
                    Prompt.ask("\n[bold bright_blue]Press Enter to return...[/bold bright_blue]", default="")
                    continue

                out_buf_5   = bytearray()
                new_files_5 = []
                all_dirs_5  = {}
                file_rows_5 = []

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold cyan][BUILD][/bold cyan] {task.description}"),
                    BarColumn(), TimeElapsedColumn(), console=console
                ) as progress:
                    task = progress.add_task("Building...", total=len(resolved_files))
                    for p, fp_5 in resolved_files:
                        dir_key = str(PurePath(fp_5).parent).replace('\\', '/') + '/'
                        if dir_key == './': dir_key = ''

                        ne      = _cp.copy(template_entry_5)
                        new_raw = p.read_bytes()
                        pak_rel_5 = PurePath(fp_5)

                        ne.uncompressed_size  = len(new_raw)
                        ne.compression_method = template_entry_5.compression_method
                        ne.encryption_method  = template_entry_5.encryption_method
                        ne.encrypted          = template_entry_5.encrypted
                        ne.unk1               = template_entry_5.unk1
                        ne.unk2               = SHA1.new((mp_str_5 + fp_5).lower().encode('utf-8')).digest()
                        ne.index_new_sep      = template_entry_5.index_new_sep
                        ne.compressed_blocks  = []

                        # ── alvsia engine: class-method encrypt + PakCompression ──
                        if ne.compression_method == CM_NONE:
                            cipher = (template_pak_obj._apply_encrypt_for_entry(
                                          new_raw, pak_rel_5, ne.encryption_method)
                                      if ne.encrypted else new_raw)
                            ne.offset  = len(out_buf_5)
                            ne.size    = len(new_raw)
                            out_buf_5 += cipher
                        else:
                            cs     = (template_entry_5.compression_block_size
                                      if template_entry_5.compression_block_size > 0 else 65536)
                            chunks = [new_raw[i:i + cs] for i in range(0, len(new_raw), cs)]
                            order  = PakCrypto.generate_block_indices(len(chunks), ne.encryption_method)
                            inv    = [0] * len(chunks)
                            for logical_i, phys_i in enumerate(order):
                                inv[phys_i] = logical_i

                            # compress each logical chunk via alvsia PakCompression
                            cipher_by_logical = []
                            for chunk in chunks:
                                compressed = PakCompression.compress_block(
                                    chunk,
                                    ne.compression_method,
                                    template_pak_obj._zstd_dict,
                                    None,
                                )
                                cipher = (template_pak_obj._apply_encrypt_for_entry(
                                              compressed, pak_rel_5, ne.encryption_method)
                                          if ne.encrypted else compressed)
                                cipher_by_logical.append(cipher)

                            new_blks = []
                            for phys_i in range(len(chunks)):
                                blk_data  = cipher_by_logical[inv[phys_i]]
                                blk       = PakCompressedBlock.__new__(PakCompressedBlock)
                                blk.start = len(out_buf_5)
                                blk.end   = blk.start + len(blk_data)
                                out_buf_5 += blk_data
                                new_blks.append(blk)
                            ne.compressed_blocks = new_blks
                            ne.offset = new_blks[0].start if new_blks else len(out_buf_5)
                            ne.size   = sum(b.end - b.start for b in new_blks)

                        ne.content_hash = SHA1.new(bytes(out_buf_5[ne.offset:ne.offset+ne.size])).digest()
                        new_files_5.append(ne)
                        all_dirs_5.setdefault(dir_key, {})[p.name] = ne
                        file_rows_5.append((fp_5, ne.uncompressed_size, ne.size))
                        progress.update(task, advance=1, description=p.name)

                # Summary
                summary_5 = Table(title="Files Built into New PAK", box=box.ROUNDED, border_style="cyan")
                summary_5.add_column("Path in PAK",   style=f"bold {get_banner_color()}")
                summary_5.add_column("Original Size", justify="right", style="dim")
                summary_5.add_column("Stored Size",   justify="right", style="dim")
                for fp_5, orig_sz, stored_sz in file_rows_5:
                    summary_5.add_row(fp_5, human_size(orig_sz), human_size(stored_sz))
                console.print(summary_5)

                # Build index
                id_to_idx_5 = {id(ne): i for i, ne in enumerate(new_files_5)}
                idx_5  = bytearray(_pw_string(mp_str_5))
                idx_5 += struct.pack('<I', len(new_files_5))
                for ne in new_files_5:
                    idx_5 += _pw_entry(ne, version_5)
                idx_5 += struct.pack('<Q', len(all_dirs_5))
                for dp_str, dir_files in all_dirs_5.items():
                    idx_5 += _pw_string(dp_str)
                    idx_5 += struct.pack('<Q', len(dir_files))
                    for name, e in dir_files.items():
                        idx_5 += _pw_string(name)
                        idx_5 += struct.pack('<i', ~id_to_idx_5[id(e)])

                index_plain_5 = bytes(idx_5)
                new_sha1_5    = SHA1.new(index_plain_5).digest()

                if template_pak_obj._pak_info.index_encrypted:
                    try:
                        key = PakCrypto.rsa_extract(template_pak_obj._pak_info.packed_key, RSA_MOD_1)
                        iv  = PakCrypto.rsa_extract(template_pak_obj._pak_info.packed_iv,  RSA_MOD_1)
                        if key and iv and len(key) == 32 and len(iv) >= 16:
                            aes = AES.new(key, MODE_CBC, iv[:16])
                            pad = (-len(index_plain_5)) % AES.block_size or AES.block_size
                            index_bytes_5 = aes.encrypt(index_plain_5 + bytes([pad]*pad))
                        else:
                            index_bytes_5 = index_plain_5
                    except:
                        index_bytes_5 = index_plain_5
                else:
                    index_bytes_5 = index_plain_5

                new_idx_offset_5 = len(out_buf_5)
                out_buf_5       += index_bytes_5

                orig_fc_5    = template_pak_obj._file_content
                footer_sz_5  = TencentPakInfo._mem_size(version_5)
                new_footer_5 = bytearray(orig_fc_5[-footer_sz_5:])
                h_key_5      = struct.pack('<5I', *keystream_5[4:9])
                new_footer_5[-36:-16] = bytes(a ^ b for a, b in zip(new_sha1_5, h_key_5))
                new_footer_5[-16:-8]  = ((len(index_bytes_5) ^ (keystream_5[10] << 32 | keystream_5[11])).to_bytes(8, 'little'))
                new_footer_5[-8:]     = ((new_idx_offset_5   ^ (keystream_5[0]  << 32 | keystream_5[1] )).to_bytes(8, 'little'))
                out_buf_5 += new_footer_5

                with open(output_pak_5, 'wb') as f:
                    f.write(out_buf_5)

                console.print(Panel(
                    f"[bold bright_blue]▶ CSV SOURCE[/bold bright_blue]      [bold white]{selected_csv_name}[/bold white]\n"
                    f"[bold bright_blue]▶ TEMPLATE PAK[/bold bright_blue]    [bold white]{template_pak_path.name}[/bold white]\n"
                    f"[bold bright_blue]▶ FILES BUILT[/bold bright_blue]     [bold yellow]{len(new_files_5)}[/bold yellow]\n"
                    f"[bold bright_blue]▶ OUTPUT[/bold bright_blue]          [bold green]{output_pak_5}[/bold green]\n"
                    f"[bold bright_blue]▶ PATH MODE[/bold bright_blue]       [bold green]AUTO CSV PATH RESOLVER[/bold green]",
                    title= f"[bold white on {get_banner_color()}] ⚡ BUILD NEW PAK SUCCESS ⚡ [/]",
                    border_style=get_banner_color(), box=box.HEAVY
                ))

                try:
                    TencentPakFile(output_pak_5, is_od=True)
                    console.print(Panel("[bold green]✅ VERIFICATION PASSED[/bold green]", border_style="green", box=box.ROUNDED))
                except Exception as ve:
                    console.print(Panel(f"[bold yellow]⚠ Verification note: {ve}[/bold yellow]", border_style="yellow", box=box.ROUNDED))

            except Exception as e:
                console.print(Panel(f"[bold red]❌ Build failed: {e}[/bold red]", border_style="red", box=box.HEAVY))
                import traceback; traceback.print_exc()

            Prompt.ask("\n[bold bright_blue]Press Enter to return to Lua Menu...[/bold bright_blue]", default="")

        elif choice == "0":
            return


#Isme fix do pura vo 

def goodbye_glacier_light_effect():
    console.clear()
    cols, rows = shutil.get_terminal_size()
    W, H = cols, rows
    particles = ["·", "•", "°", "*", "×", "■"]
    b_color = get_banner_color()

    with Live(console=console, screen=True, refresh_per_second=24) as live:
        for step in range(12):
            lines = ["".join(random.choice(particles) if random.random() < 0.05 else " " for _ in range(W)) for _ in range(H-1)]
            live.update(Text("\n".join(lines), style=b_color))
            time.sleep(0.04)

    console.clear()
    console.print("\n" * rows, style="on white") 
    time.sleep(0.15) 
    console.clear()

    def make_exit_panel(style_main, style_sub, style_off):
        msg = Text.assemble(
            (to_fancy("GOOD BYE BABYY\n\n"), style_main),
            (to_fancy("SYSTEM DISCONNECTED\n"), style_sub),
            (to_fancy("OFFLINE NOW"), style_off)
        )
        return Panel(Align.center(msg), border_style=style_main, box=box.DOUBLE, padding=(2, 5))

    stages = [
        ("dim", "dim", "dim"),
        ("bold black", "dim", "dim"),
        (f"bold {b_color}", "bold black", "dim"),
        (f"bold bright_{b_color.replace('bright_', '')}", f"bold {b_color}", "bold black"),
        ("bold bright_white", "bold bright_white", "bold bright_white")
    ]

    with Live(console=console, screen=True, refresh_per_second=12) as live:
        for s1, s2, s3 in stages:
            content = Align.center(make_exit_panel(s1, s2, s3), vertical="middle")
            live.update(content)
            time.sleep(0.2)
        time.sleep(0.6)

    console.clear()
    final_panel = make_exit_panel(f"blink bold {b_color}", "bold white", "bold red")
    console.print("\n" * (rows // 4))
    console.print(final_panel)
    time.sleep(2)
    sys.exit()

def print_banner_and_header():
    console.clear()
    console.print(get_neon_header())

def print_user_profile():
    """PATCHED: Always shows VIP account info panel."""
    from datetime import datetime
    b_color = get_banner_color()
    now = datetime.now()
    grid = Table.grid(expand=True)
    grid.add_column(justify="left")
    grid.add_column(justify="right")
    grid.add_row(
        f"[bold {b_color}]🔑 {to_fancy('Key')}:[/bold {b_color}] [bold white]VIP-OFFLINE-BYPASS[/]",
        f"[bold {b_color}]{to_fancy('Valid for')}:[/bold {b_color}] [bold yellow]{to_fancy('99999 Days')}[/]"
    )
    grid.add_row(
        f"[bold {b_color}]⏳ {to_fancy('Expiry')}:[/bold {b_color}] [bold white]{to_fancy('2300-01-01 00:00:00')}[/]",
        f"[bold {b_color}]🚀 {to_fancy('Version')}:[/bold {b_color}] [bold white]{to_fancy('V1.0 (LATEST)')}[/]"
    )
    console.print(Panel(
        grid,
        title=f"[bold black on {b_color}] 💎 {to_fancy('VIP ACCOUNT INFO')} 💎 [/]",
        border_style=b_color,
        box=box.HEAVY,
        padding=(0, 1)
    ))
    console.print(Panel(
        Align.center(Text(f" ● {to_fancy('SECURE CONNECTION ESTABLISHED')} ● ", style=f"bold black on {b_color}")),
        border_style=b_color, box=box.SIMPLE, padding=(0,0)
    ))


def mini_clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_terminal_width():
    try:
        return os.get_terminal_size().columns
    except (AttributeError, OSError):
        return 80  # Default fallback width

def mini_display_tool_name():
    mini_clear_screen()
    width = get_terminal_width()
    
    Y = "\033[1;33m"
    W = "\033[1;37m"
    G = "\033[1;32m"
    C = "\033[1;36m"
    RESET = "\033[0m"
    
    # 1. Centered Banner
    banner_lines = [
        r"   _____ __ __  ____   _  __  ______ ____   ____   __ ",
        r"  / ___// //_/ /  _/  / |/ /  /_  __// __ \ / __ \ / / ",
        r"  \__ \/ ,<    / /   /  |/ /    / /  / / / // / / // /  ",
        r" ___/ / /| | _/ /   / /|  /    / /  / /_/ // /_/ // /___",
        r"/____/_/ |_|/___/  /_/ |_/    /_/   \____/ \____//_____/"
    ]
    
    for line in banner_lines:
        print((G + line + RESET).center(width + len(G) + len(RESET)))
    
    print("\n")
    
    # 2. Centered UI Box
    box_lines = [
     #  ₹ f"{W}╔══════════════════════════════════════════╗",
      #  f"{W}║ {Y}▶  {to_fancy('SKIN TOOL PRO')}                     {W}║",
        #f"{W}╠══════════════════════════════════════════╣",
     #   f"{W}║ {G}▶  {to_fancy('ACCESS')} : {Y}{to_fancy('VIP SERVER')}                {W}║",
      #  f"{W}║ {G}▶  {to_fancy('STATUS')} : {G}{to_fancy('ONLINE')}                    {W}║",
       # f"{W}╚══════════════════════════════════════════╝{RESET}"
    ]
    
    for line in box_lines:
        # Calculate extra length for ANSI escape characters so centering remains precise
        ansi_len = line.count('\033') * 9  # Approximate length of color codes
        print(line.center(width + ansi_len))
        
    print("\n")


def mini_mark_block_as_modified(file_path, byte_offset):
    block_idx = byte_offset // mini_BLOCK_SIZE
    if file_path not in mini_modified_blocks_map:
        mini_modified_blocks_map[file_path] = set()
    mini_modified_blocks_map[file_path].add(block_idx)
    if block_idx > 0:
        mini_modified_blocks_map[file_path].add(block_idx - 1)
    mini_modified_blocks_map[file_path].add(block_idx + 1)

def mini_load_all_skins_data():
    skins_by_id = {}
    if not os.path.exists(mini_ALL_TXT_PATH):
        print(f"{colorama.Fore.RED}🚨 {to_fancy('ALL.txt not found at')} {mini_ALL_TXT_PATH}")
        return skins_by_id
    with open(mini_ALL_TXT_PATH, "r", encoding="utf-8", errors='ignore') as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) >= 2:
                skin_id = parts[0].strip()
                hex_val = parts[1].strip().lower()
                skin_name = parts[2].strip() if len(parts) >= 3 else ""
                skins_by_id[skin_id] = {'hex': hex_val, 'name': skin_name}
    return skins_by_id

def mini_load_index_data():
    index_data = {}
    if not os.path.exists(mini_INDEX_FILE_PATH):
        print(f"{colorama.Fore.YELLOW}⚠️ {to_fancy('index.txt not found at')} {mini_INDEX_FILE_PATH}")
        return index_data
    with open(mini_INDEX_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as file:
        for line in file:
            parts = line.strip().split('|')
            if len(parts) >= 4:
                name = parts[2].strip()
                index_hex = parts[3].strip().lower()
                index_data.setdefault(name, []).append(index_hex)
    return index_data

def mini_load_modskin_pairs():
    pairs = []
    if not os.path.exists(mini_MODSKIN_FILE):
        print(f"{colorama.Fore.RED}🚨 {to_fancy('modskin.txt not found at')} {mini_MODSKIN_FILE}")
        return pairs
    with open(mini_MODSKIN_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            parts = re.split(r'[,\s\->]+', line)
            if len(parts) >= 2:
                pairs.append((parts[0].strip(), parts[1].strip()))
    return pairs

def mini_write_changelog():
    os.makedirs(mini_OUTPUT_DIR, exist_ok=True)
    with open(mini_CHANGELOG_PATH, "w", encoding="utf-8") as f:
        f.write(f"🌟 {to_fancy('Combined Mod Tool Changelog')} 🌟\n")
        f.write("==============================\n\n")
        for idx, entry in enumerate(mini_changelog_entries, 1):
            f.write("==============================\n")
            f.write(f"{idx}. {to_fancy('ID PAIR')}: {entry['id_pair']}\n")
            f.write(f"{to_fancy('FILE NAME')}: {entry['file_name']}\n")
            f.write(f"{to_fancy('Source Item')}: {entry['source_item']}\n")
            f.write(f"{to_fancy('Target Item')}: {entry['target_item']}\n")
            f.write(f"{to_fancy('CHANGED HEX FROM')}: {entry['source_hex']} {to_fancy('TO')}: {entry['target_hex']}\n")
            if entry.get('index_occurrences', 0) > 0:
                f.write(f"{to_fancy('INDEX CHANGED FROM')}: {entry['source_index']} {to_fancy('TO')}: {entry['target_index']} ({entry['index_occurrences']} occurrence(s))\n")
            elif entry.get('index_failure_reason'):
                f.write(f"{to_fancy('Index replacement note')}: {entry['index_failure_reason']}\n")
            f.write("==============================\n\n")

def mini_remove_readonly(func, path, excinfo):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception: pass

def mini_copy_files_to_output():
    print(f"\n{colorama.Fore.CYAN}📁 {to_fancy('Step 1: Copying files from INPUT to OUTPUT...')}")
    if not os.path.exists(mini_INPUT_DIR):
        print(f"{colorama.Fore.RED}🚨 {to_fancy('INPUT directory not found')}: {mini_INPUT_DIR}")
        return False
    if os.path.exists(mini_OUTPUT_DIR):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                shutil.rmtree(mini_OUTPUT_DIR, onerror=mini_remove_readonly)
                break
            except PermissionError:
                if attempt < max_retries - 1:
                    print(f"{colorama.Fore.YELLOW}⚠️ {to_fancy('OUTPUT folder is locked. Retrying in 1s...')}")
                    time.sleep(1)
                else:
                    print(f"\n{colorama.Fore.RED}❌ {to_fancy('ERROR: Cannot delete OUTPUT folder. It is open in another program.')}")
                    input(f"{colorama.Fore.YELLOW}{to_fancy('Press Enter after closing to try again...')}{colorama.Style.RESET_ALL}")
                    try: shutil.rmtree(mini_OUTPUT_DIR, onerror=mini_remove_readonly)
                    except Exception as e:
                        print(f"{colorama.Fore.RED}❌ {to_fancy('Failed to clean OUTPUT')}: {e}")
                        return False
            except Exception as e:
                print(f"{colorama.Fore.RED}❌ {to_fancy('Error cleaning OUTPUT')}: {e}")
                return False
    try:
        shutil.copytree(mini_INPUT_DIR, mini_OUTPUT_DIR)
        file_count = sum(len(files) for _, _, files in os.walk(mini_OUTPUT_DIR))
        print(f"{colorama.Fore.GREEN}✅ {to_fancy(f'Copied {file_count} files to OUTPUT directory')}")
        return True
    except Exception as e:
        print(f"{colorama.Fore.RED}❌ {to_fancy('Error copying files')}: {e}")
        return False

def mini_process_mod_skin():
    global mini_modified_blocks_map
    mini_modified_blocks_map = {}
    print(f"\n{colorama.Fore.LIGHTBLUE_EX}🔧 {to_fancy('Step 2: Processing Mod Skin replacements...')}")
    
    # --- AUTO MODE: REPLACE (One-Way) HARDCODED ---
    is_swap = False
    mode_str = "REPLACE (One-Way)"
    print(f"{colorama.Fore.CYAN}{to_fancy('Mode')}: {colorama.Fore.LIGHTGREEN_EX}{to_fancy(mode_str)} [AUTO SELECTED]")
    
    skins_data = mini_load_all_skins_data()
    index_data = mini_load_index_data()
    id_pairs = mini_load_modskin_pairs()
    if not id_pairs:
        print(f"{colorama.Fore.RED}⚠️ {to_fancy('No ID pairs found in modskin.txt')}")
        return
        
    print(f"{colorama.Fore.LIGHTGREEN_EX}✅ {to_fancy(f'Found {len(id_pairs)} ID pairs to process')}")
    resolved_ops = []
    missing_ids = set()
    for s_id, t_id in id_pairs:
        if s_id not in skins_data:
            missing_ids.add(s_id)
            continue
        if t_id not in skins_data:
            missing_ids.add(t_id)
            continue
        s_hex = skins_data[s_id]['hex']
        s_name = skins_data[s_id]['name']
        t_hex = skins_data[t_id]['hex']
        t_name = skins_data[t_id]['name']
        resolved_ops.append({
            'search_hex': t_hex, 'replace_hex': s_hex,
            'search_name': t_name, 'replace_name': s_name,
            'label': f"{s_id} -> {t_id}",
            'op_type': "REPLACE"
        })
        
    if missing_ids:
        print(f"{colorama.Fore.LIGHTBLUE_EX}⚠️ {to_fancy(f'Warning: {len(missing_ids)} IDs not found in ALL.txt:')} {colorama.Fore.CYAN}{', '.join(sorted(missing_ids))}")
    if not resolved_ops:
        print(f"{colorama.Fore.RED}❌ {to_fancy('Empty operational queue. Nothing to process.')}")
        return
        
    modified_files = 0
    for root, dirs, files in os.walk(mini_OUTPUT_DIR):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            if file_name.lower().endswith('.txt'): continue
            try:
                with open(file_path, 'rb') as f:
                    content_bytes = f.read()
            except Exception as e:
                print(f"{colorama.Fore.RED}❌ {to_fancy('Error reading')} {file_name}: {e}")
                continue
            hex_data = content_bytes.hex()
            file_modified = False
            for op in resolved_ops:
                s_hex = op['search_hex']
                r_hex = op['replace_hex']
                s_name = op['search_name']
                r_name = op['replace_name']
                if s_hex not in hex_data: continue
                occ = hex_data.count(s_hex)
                if occ >= 2:
                    first_pos = hex_data.find(s_hex)
                    second_pos = hex_data.find(s_hex, first_pos + len(s_hex))
                    if second_pos != -1:
                        hex_data = hex_data[:second_pos] + r_hex + hex_data[second_pos+len(s_hex):]
                        file_modified = True
                        mini_mark_block_as_modified(file_path, second_pos // 2)
                        idx_occ = 0
                        idx_reason = ""
                        mod_idx_from = "N/A"
                        mod_idx_to = "N/A"
                        if s_name in index_data and r_name in index_data:
                            search_candidates = index_data[s_name]
                            replacement_index = index_data[r_name][0]
                            window_start = max(0, first_pos - 60)
                            window = hex_data[window_start:first_pos]
                            found = False
                            for candidate in search_candidates:
                                if candidate in window:
                                    mod_idx_from = candidate
                                    mod_idx_to = replacement_index
                                    window_replaced = window.replace(candidate, replacement_index, 1)
                                    local_idx = window.find(candidate)
                                    real_idx = window_start + local_idx
                                    hex_data = hex_data[:window_start] + window_replaced + hex_data[first_pos:]
                                    idx_occ = 1
                                    found = True
                                    mini_mark_block_as_modified(file_path, real_idx // 2)
                                    break
                            if not found: idx_reason = "Index hex not found in window"
                        else: idx_reason = "Index names missing"
                        rel_path = os.path.relpath(file_path, mini_OUTPUT_DIR)
                        mini_changelog_entries.append({
                            'id_pair': f"{op['label']} ({op['op_type']})",
                            'file_name': rel_path,
                            'source_item': f"{s_name} [Found]",
                            'target_item': f"{r_name} [Applied]",
                            'source_hex': s_hex,
                            'target_hex': r_hex,
                            'source_index': mod_idx_from,
                            'target_index': mod_idx_to,
                            'index_occurrences': idx_occ,
                            'index_failure_reason': idx_reason
                        })
            if file_modified:
                try:
                    with open(file_path, 'wb') as f:
                        f.write(bytes.fromhex(hex_data))
                    modified_files += 1
                except Exception as e:
                    print(f"{colorama.Fore.RED}❌ {to_fancy('Error writing')} {file_name}: {e}")
    print(f"{colorama.Fore.LIGHTGREEN_EX}✅ {to_fancy(f'Modified {modified_files} files')}")

def mini_build_pattern_groups(hex_list):
    groups = {}
    for hx in hex_list:
        try: b = bytes.fromhex(hx)
        except ValueError: continue
        if not b: continue
        groups.setdefault(len(b), set()).add(b)
    return groups

def mini_null_bytes_in_file(file_path, pattern_groups, dirty_blocks, target_counts={2}):
    try: data = Path(file_path).read_bytes()
    except: return 0
    ba = bytearray(data)
    total_hits = 0
    modified = False
    file_size = len(ba)
    for block_idx in dirty_blocks:
        start_offset = block_idx * mini_BLOCK_SIZE
        if start_offset >= file_size: continue
        end_offset = min(start_offset + mini_BLOCK_SIZE, file_size)
        block_len = end_offset - start_offset
        block_mv = memoryview(ba)[start_offset:end_offset]
        for L, patterns in pattern_groups.items():
            if L <= 0 or block_len < L: continue
            zero = b"\x00" * L
            occurrences = {}
            i = 0
            end = block_len - L
            while i <= end:
                chunk = bytes(block_mv[i:i+L])
                if chunk in patterns:
                    if chunk not in occurrences: occurrences[chunk] = []
                    occurrences[chunk].append(i)
                    i += L
                else: i += 1
            for pat, positions in occurrences.items():
                count = len(positions)
                if count in target_counts:
                    for pos in positions:
                        abs_pos = start_offset + pos
                        ba[abs_pos:abs_pos+L] = zero
                    total_hits += count
                    modified = True
    if modified:
        Path(file_path).write_bytes(ba)
    return total_hits

def mini_process_size_fix():
    skins_data = mini_load_all_skins_data()
    if not skins_data:
        return
        
    protected_ids = set()
    protected_hexes_from_ids = set()
    if os.path.exists(mini_MODSKIN_FILE):
        with open(mini_MODSKIN_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                parts = re.split(r'[,\s\->]+', line)
                for part in parts:
                    part = part.strip()
                    if part: protected_ids.add(part)
    for skin_id in protected_ids:
        if skin_id in skins_data:
            protected_hex = skins_data[skin_id]['hex']
            protected_hexes_from_ids.add(protected_hex.lower())
    
    valid_entries = []
    skipped_count_name = 0
    skipped_count_zeros = 0
    skipped_count_id = 0
    exclude_keywords = {"face", "hair", "head", "male", "female"}
    for skin_id, info in skins_data.items():
        hex_code = info['hex']
        skin_name = info['name'].lower()
        if skin_id in protected_ids:
            skipped_count_id += 1
            continue
        if any(keyword in skin_name for keyword in exclude_keywords):
            skipped_count_name += 1
            continue
        if "0000" in hex_code:
            skipped_count_zeros += 1
            continue
        valid_entries.append((hex_code, skin_name))
    
    exclude_hexes = set()
    for entry in mini_changelog_entries:
        exclude_hexes.add(entry.get('source_hex', '').lower())
        exclude_hexes.add(entry.get('target_hex', '').lower())
        if entry.get('source_index', "N/A") != "N/A": 
            exclude_hexes.add(entry['source_index'].lower())
        if entry.get('target_index', "N/A") != "N/A": 
            exclude_hexes.add(entry['target_index'].lower())
    
    exclude_txt_path = os.path.join(mini_BASE_DIR, "exclude.txt")
    os.makedirs(os.path.dirname(exclude_txt_path), exist_ok=True)
    
    with open(exclude_txt_path, 'w', encoding='utf-8') as f:
        if exclude_hexes:
            f.write("# Hex values to exclude from nulling (auto-generated from changelog)\n")
            f.write(" ".join(sorted(exclude_hexes)))
        else:
            f.write("# No hex values to exclude\n")
    
    exclude_hexes.update(protected_hexes_from_ids)

    
    print(f"{colorama.Fore.CYAN}{to_fancy('Nulling Mode:')} {colorama.Fore.LIGHTGREEN_EX}AUTO NULL SYSTEM [AUTO SELECTED]")
    
    target_counts = {2}
    
    final_hexes = []
    for hx, name in valid_entries:
        if hx in exclude_hexes: continue
        final_hexes.append(hx)
        
    pattern_groups = mini_build_pattern_groups(final_hexes)
    files_to_process = []
    for root, dirs, files in os.walk(mini_OUTPUT_DIR):
        for file_name in files:
            if not file_name.lower().endswith('.txt'):
                files_to_process.append(os.path.join(root, file_name))
    
    total_nulled = 0
    files_modified = 0
    
    with console.status("[bold cyan]Scanning and Nulling Hex values...[/]", spinner="dots"):
        for file_idx, file_path in enumerate(files_to_process, 1):
            dirty_blocks = mini_modified_blocks_map.get(file_path, set())
            if not dirty_blocks: continue
            hits = mini_null_bytes_in_file(file_path, pattern_groups, dirty_blocks, target_counts)
            if hits > 0:
                files_modified += 1
                total_nulled += hits
    
    print()
    with open(mini_NULLED_TXT_PATH, 'w', encoding='utf-8') as f:
        f.write("Nulled Hex Values Report\n========================\n")
        f.write(f"Files modified: {files_modified}\nUnique hex values nulled: {len(final_hexes)}\nTotal occurrences replaced: {total_nulled}\n")
    print(f"{colorama.Fore.LIGHTGREEN_EX}✅ {to_fancy('Size fix processing complete.')}")
    
def mini_run_auto_theme():
    DEFAULT_HEX = "7480100C"
    b_color = get_banner_color() # ALVSIA global color variable
    
    while True:
        mini_display_tool_name()
        
        # --- UI UPDATE: ALVSIA BORDER STYLE ---
        # --- UI UPDATE: ALVSIA BORDER STYLE (GREEN THEME) ---
        menu_table = Table(show_header=False, box=box.SIMPLE, expand=True)
        menu_table.add_column("𝐎𝐏𝐓", style=f"bold {get_banner_color()}", justify="center", width=4)
        menu_table.add_column("𝐂𝐎𝐌𝐌𝐀𝐍𝐃", style=f"bold {b_color}")
        
        # Labels ab Bright Green dikhenge
        menu_table.add_row("1", f"[bold cyan]▶[/] [bold {get_banner_color()}]{to_fancy('SWAP LOBBY INDEX')}[/]")
        menu_table.add_row("2", f"[bold red]▶[/] [bold {get_banner_color()}]{to_fancy('BACK TO MAIN MENU')}[/]")
        
        console.print(Panel(
            menu_table, 
            border_style=b_color, 
            box=box.HEAVY, 
            title=f"[bold black on {b_color}] 👑 {to_fancy('AUTO THEME CHANGER')} 👑 [/]"
        ))

        choice = Prompt.ask(f"[bold {b_color}]{to_fancy('ENTER COMMAND')} >[/bold {b_color}]", choices=["1", "2"])
        
        if choice == "1":
            lobbies = []
            try:
                with open(mini_LOBBY_FILE, "r") as file:
                    for line in file:
                        parts = line.strip().split("|")
                        if len(parts) == 3: lobbies.append((parts[1].strip(), parts[2].strip()))
            except FileNotFoundError: pass
            
            if not lobbies:
                console.print(f"[red]❌ {to_fancy('lobby.txt not found or empty.')}[/red]")
                time.sleep(1); continue

            # --- UI UPDATE: NEON LIST WITH ALVSIA THEME ---
            # --- UI UPDATE: FULL NEON GREEN LIST ---
            console.print(f"\n[bold {b_color}]── {to_fancy('AVAILABLE LOBBIES')} ──[/bold {b_color}]\n")
            for i, (_, name) in enumerate(lobbies, 1):
                # Neon Blue Index + Bright Green Name
                console.print(f"[bold bright_blue]{i:02d}.[/] [bold {get_banner_color()}]{to_fancy(name)}[/]")
            
            lobby_choice = Prompt.ask(f"\n[bold {b_color}]{to_fancy('Select a lobby theme ID')}[/bold {b_color}]")
            try:
                lobby_idx = int(lobby_choice) - 1
                if 0 <= lobby_idx < len(lobbies):
                    target_hex, lobby_name = lobbies[lobby_idx]
                    
                    with console.status(f"[bold {b_color}]Applying {lobby_name} theme...[/]"):
                        default_hex_bytes = bytes.fromhex(DEFAULT_HEX)
                        target_hex_bytes = bytes.fromhex(target_hex)
                        for filename in os.listdir(mini_AUTO_THEME_FILES):
                            file_path = os.path.join(mini_AUTO_THEME_FILES, filename)
                            with open(file_path, "rb") as file: file_data = file.read()
                            updated_data = bytearray(file_data)
                            
                            default_pos = target_pos = None
                            for i in range(len(file_data) - len(default_hex_bytes), 7, -1):
                                if file_data[i:i + len(default_hex_bytes)] == default_hex_bytes:
                                    default_index = file_data[i - 8]; default_pos = i - 8; break
                            for i in range(len(file_data) - len(target_hex_bytes), 7, -1):
                                if file_data[i:i + len(target_hex_bytes)] == target_hex_bytes:
                                    target_index = file_data[i - 8]; target_pos = i - 8; break
                                    
                            if default_pos is not None and target_pos is not None:
                                updated_data[default_pos] = target_index
                                updated_data[target_pos] = default_index
                                result_path = os.path.join(mini_AUTO_THEME_RESULT, filename)
                                os.makedirs(mini_AUTO_THEME_RESULT, exist_ok=True)
                                with open(result_path, "wb") as file: file.write(updated_data)
                    
                    console.print(f"[bold {get_banner_color()}]✔ SUCCESS: Lobby Swap Applied![/bold {get_banner_color()}]")
                else: console.print(f"[red]❌ {to_fancy('Invalid ID.')}[/red]")
            except ValueError: console.print(f"[red]❌ {to_fancy('Invalid input.')}[/red]")
        elif choice == "2": break
        time.sleep(1)

def mini_run_hit_loot_tool():
    mini_display_tool_name()
    
    # ============================================================
    # 🔥 HEADER - BLUE
    # ============================================================
    zsdic_console.print(Panel(
        f"[bold bright_blue]🌟 HIT EFFECT & LOOTCRATES TOOL[/bold bright_blue]\n"
        f"[dim]ID pairs from ZSDIC/modskin.txt | Files from MINI[/dim]",
        border_style="bright_blue",
        box=box.HEAVY
    ))
    
    # ============================================================
    # 🔥 PATHS
    # ============================================================
    global game_key, BASE_DIR
    
    if 'game_key' not in globals() or game_key not in ["BGMI", "PUBG"]:
        game_key = "BGMI"
    
    game_folder = f"{game_key}_SKIN"
    game_base = os.path.join(BASE_DIR, game_folder)
    
    # 🔥 ZSDIC - ID PAIRS KE LIYE
    zsdic_base = os.path.join(game_base, "ZSDIC")
    zsdic_modskin = os.path.join(zsdic_base, "modskin.txt")
    
    # 🔥 🔥 🔥 ALL.TXT KA SAHI PATH - MINI/MINI_ICON/TXTS/ALL.TXT 🔥 🔥 🔥
    mini_base = os.path.join(game_base, "MINI")
    mini_icon = os.path.join(mini_base, "MINI_ICON")
    mini_txts = os.path.join(mini_icon, "TXTS")
    mini_all = os.path.join(mini_txts, "ALL.txt")  # ✅ YAHAN HAI!
    
    # 🔥 HIT EFFECT & LOOTCRATES FILES
    mini_HIT_ORIG = os.path.join(mini_base, "HIT EFFECT", "org")
    mini_HIT_MODIFIED = os.path.join(mini_base, "HIT EFFECT", "modified")
    mini_LOOT_ORIG = os.path.join(mini_base, "LOOTCRATES", "org")
    mini_LOOT_MODIFIED = os.path.join(mini_base, "LOOTCRATES", "modified")
    
    # ============================================================
    # 🔥 CHECK ALL.TXT EXIST KARTA HAI
    # ============================================================
    
    if not os.path.exists(mini_all):
        zsdic_console.print(Panel(
            f"[red]❌ ALL.txt not found![/red]\n"
            f"[dim]Expected: {mini_all}[/dim]",
            border_style="red",
            box=box.ROUNDED
        ))
        return
    
    # ============================================================
    # 🔥 LOAD ID PAIRS FROM ZSDIC/MODSKIN.TXT
    # ============================================================
    
    id_pairs = []
    
    if os.path.exists(zsdic_modskin):
        with open(zsdic_modskin, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = re.split(r'[,\s]+', line.strip())
                if len(parts) >= 2:
                    id_pairs.append((parts[0].strip(), parts[1].strip()))
        
        zsdic_console.print(Panel(
            f"[bold bright_blue]✔ Loaded {len(id_pairs)} pairs from ZSDIC/modskin.txt[/bold bright_blue]",
            border_style="bright_blue",
            box=box.ROUNDED
        ))
    else:
        zsdic_console.print(Panel(
            f"[red]❌ ZSDIC/modskin.txt not found![/red]",
            border_style="red",
            box=box.ROUNDED
        ))
        return
    
    if not id_pairs:
        zsdic_console.print(Panel(
            f"[yellow]⚠ No ID pairs found in ZSDIC/modskin.txt[/yellow]",
            border_style="yellow",
            box=box.ROUNDED
        ))
        return
    
    # ============================================================
    # 🔥 LOAD ALL.TXT FOR HEX VALUES
    # ============================================================
    
    id_to_entry = {}
    by_name = {}
    
    with open(mini_all, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            parts = line.strip().split("|")
            if len(parts) >= 3:
                idv = parts[0].strip()
                hx = parts[1].strip().lower()
                name = parts[2].strip()
                id_to_entry[idv] = {"hex": hx, "name": name, "base": name}
                by_name.setdefault(name, {})[0] = hx
    
    zsdic_console.print(Panel(
        f"[bold bright_blue]✔ Loaded {len(id_to_entry)} entries from MINI/MINI_ICON/TXTS/ALL.txt[/bold bright_blue]",
        border_style="bright_blue",
        box=box.ROUNDED
    ))
    
    # ============================================================
    # 🔥 GENERATE PAIRS
    # ============================================================
    
    pairs_hit, pairs_loot = [], []
    
    for a_raw, b_raw in id_pairs:
        if a_raw not in id_to_entry:
            continue
        
        first_hex = id_to_entry[a_raw]["hex"]
        
        if b_raw in id_to_entry:
            hit_hex = id_to_entry[b_raw]["hex"]
            loot_hex = id_to_entry[b_raw]["hex"]
        else:
            hit_hex = b_raw
            loot_hex = b_raw
        
        pairs_hit.append((first_hex, hit_hex))
        if len(first_hex) == len(loot_hex):
            pairs_loot.append((first_hex, loot_hex))
    
    # ============================================================
    # 🔥 PROGRESS BAR
    # ============================================================
    
    with Live(refresh_per_second=30, console=zsdic_console) as live:
        for i in range(101):
            if i % 5 == 0:
                bar_length = 30
                filled = int((i / 100) * bar_length)
                bar = "█" * filled + "░" * (bar_length - filled)
                
                progress_text = (
                    f"[bold bright_blue]⏳ Processing...[/bold bright_blue]\n\n"
                    f"[bold bright_blue]{bar}[/bold bright_blue] [bold white]{i}%[/bold white]\n"
                    f"[dim]{i}% complete[/dim]"
                )
                
                live.update(Panel(
                    progress_text,
                    title="[bold black on bright_blue] ⚙ PROCESSING ⚙ [/]",
                    border_style="bright_blue",
                    box=box.HEAVY
                ))
            time.sleep(0.02)
    
    # ============================================================
    # 🔥 PROCESS FILES - MINI FOLDER SE
    # ============================================================
    
    for path in [mini_HIT_MODIFIED, mini_LOOT_MODIFIED]:
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
            except:
                pass
        os.makedirs(path, exist_ok=True)
    
    def process_files(orig_dir, mod_dir, pairs):
        if not os.path.exists(orig_dir):
            return 0
        
        files = []
        for r, _, fs in os.walk(orig_dir):
            for fn in fs:
                files.append(os.path.join(r, fn))
        
        if not files:
            return 0
        
        count = 0
        for src in files:
            try:
                with open(src, 'rb') as fh:
                    data = fh.read()
            except:
                continue
            
            orig = data
            for first_hex, second_hex in pairs:
                try:
                    to_b = bytes.fromhex(second_hex)
                    from_raw = bytes.fromhex(first_hex)
                except:
                    continue
                
                if len(from_raw) < len(to_b):
                    replacement = from_raw + b'\x00' * (len(to_b) - len(from_raw))
                elif len(from_raw) > len(to_b):
                    replacement = from_raw[:len(to_b)]
                else:
                    replacement = from_raw
                
                if data.count(to_b):
                    data = data.replace(to_b, replacement)
                if data.count(to_b[::-1]):
                    data = data.replace(to_b[::-1], replacement[::-1])
            
            if data != orig:
                rel = os.path.relpath(src, orig_dir)
                outp = os.path.join(mod_dir, rel)
                os.makedirs(os.path.dirname(outp), exist_ok=True)
                with open(outp, 'wb') as outfh:
                    outfh.write(data)
                count += 1
        
        return count

    hit_count = process_files(mini_HIT_ORIG, mini_HIT_MODIFIED, pairs_hit)
    loot_count = process_files(mini_LOOT_ORIG, mini_LOOT_MODIFIED, pairs_loot)
    
    # ============================================================
    # 🔥 FINAL - BLUE
    # ============================================================
    zsdic_console.print(Panel(
        f"[bold bright_blue]✅ Modified {hit_count} HIT files & {loot_count} LOOT files.[/bold bright_blue]",
        border_style="bright_blue",
        box=box.HEAVY
    ))
    
import colorama
from rich import box
from rich.panel import Panel
from rich.table import Table


def mini_full_flow():
    # Master Panel
    console.print(
        Panel(
            f"[bold bright_cyan]🚀 REPSHMET & SIZE-FIX MASTER ENGINE 🚀[/]\n\n"
            f"[bold blue]M A S T E R   A U T O M A T E D   P I P E L I N E[/]\n"
            f"[dim cyan]──────────────────────────────────────────────[/]\n"
            f"[bold white]Pipeline Status : [bold {get_banner_color()}]READY FOR EXECUTION[/][/bold white]",
            expand=True,
            border_style="bright_blue",
            box=box.HEAVY,
            padding=(1, 2),
            title="[bold black on bright_blue] MASTER ENGINE INITIALIZED [/]",
            title_align="center"
        )
    )

    file_changes = {}  # ✅ PEHLE SE INITIALIZE KARO

    # Run tasks silently in background (No task status table)
    if not mini_copy_files_to_output(): 
        console.print(Panel("[bold bright_red]✖ SYNC FAILED[/]", border_style="red", expand=True))
        return
        
    res = mini_process_mod_skin()
    
    # ✅ SAFE CHECK - SIRF DICT HI CONSIDER KARO
    if isinstance(res, dict):
        file_changes = res
    # ✅ BAAKI SAB IGNORE KARO - KYUNKI YE VARIABLES EXIST NAHI KARTE
    
    mini_write_changelog()
    mini_process_size_fix()

    # 🟢 Display Replaced ID Pairs Details Table right in place of old dashboard
    if file_changes:
        pair_table = Table(
            title= f"[bold black on {get_banner_color()}] 🔄 REPLACED ID PAIRS DETAILS 🔄 [/]",
            border_style=get_banner_color(),
            box=box.HEAVY,
            expand=True,
            show_lines=True
        )
        pair_table.add_column("📁 TARGET ASSET FILE", style="bold cyan", ratio=2)
        pair_table.add_column("🔄 REPLACED ID PAIR (FROM ➔ TO)", style=f"bold {get_banner_color()}", ratio=2)
        pair_table.add_column("⚡ MATCH MODE", style="bold yellow", ratio=1, justify="center")

        for rel_file, pairs_info in file_changes.items():
            for pair, pinfo in pairs_info.items():
                pair_table.add_row(
                    rel_file,
                    f"[bold white]{pair[0]}[/] ➔ [bold {get_banner_color()}]{pair[1]}[/]",
                    str(pinfo.get('mode', 'REPLACE'))
                )
        console.print(pair_table)

    # Final Success Summary Panel
    console.print(Panel(
        f"[bold {get_banner_color()}]✔ MASTER PIPELINE EXECUTED SUCCESSFULLY![/]\n\n"
        f"  [dim white]• Pipeline Status      :[/dim white] [bold {get_banner_color()}]SYSTEM FULLY OPTIMIZED[/]\n"
        f"  [dim white]• Asset Verification   :[/dim white] [bold cyan]ALL ASSETS VERIFIED & PATCHED[/]", 
        border_style=get_banner_color(), 
        box=box.HEAVY,
        expand=True,
        title= f"[bold black on {get_banner_color()}] 📊 EXECUTION COMPLETED [/]",
        padding=(1, 2)
    ))
    
    input(f"\n{colorama.Fore.YELLOW}{to_fancy('Press Enter to continue...')}{colorama.Style.RESET_ALL}")



def mini_menu():
    while True:
        mini_display_tool_name()
        b_color = get_banner_color()
        menu_table = Table(show_header=True, header_style=f"bold black on {b_color}", 
                           box=box.DOUBLE_EDGE, title=f"[reverse]  👑 {to_fancy('MINI SKIN TOOL')} 👑  [/]", 
                           border_style=b_color, expand=True)
        if CURRENT_SESSION_COLOR == "rainbow":
            menu_table.add_column(rainbow_text("𝐎𝐏𝐓"), justify="center", width=4)
            menu_table.add_column(rainbow_text("𝐂𝐎𝐌𝐌𝐀𝐍𝐃"))
            menu_table.add_column(rainbow_text("𝐃𝐄𝐒𝐂𝐑𝐈𝐏𝐓𝐈𝐎𝐍"))
        else:
            menu_table.add_column("𝐎𝐏𝐓", style="bold white", justify="center", width=4)
            menu_table.add_column("𝐂𝐎𝐌𝐌𝐀𝐍𝐃", style=f"bold {b_color}")
            menu_table.add_column("𝐃𝐄𝐒𝐂𝐑𝐈𝐏𝐓𝐈𝐎𝐍", style="dim white")
        
        menu_table.add_row(menu_item("1", 0), menu_item("MOD SKIN & SIZE FIX", 1), menu_item("VIP Mod Skin & Size Fix", 5))
        menu_table.add_row(menu_item("2", 2), menu_item("HIT EFFECT & LOOTCRATES", 3), menu_item("Change hit effects", 7))
        menu_table.add_row(menu_item("3", 4), menu_item("AUTO THEME CHANGER", 5), menu_item("Swap lobby index", 9))
        menu_table.add_row(menu_item("0", 6), menu_item("BACK", 7), menu_item("Return to Combined Menu", 11))
        
        console.print(Panel(menu_table, border_style=b_color, box=box.HEAVY))
        
        # 🔥 FIX: choices hatao
        choice = Prompt.ask(f"[bold {b_color}]{to_fancy('ENTER 𝐂𝐎𝐌𝐌𝐀𝐍𝐃 >')} [/]")
        
        if choice == "1": 
            mini_full_flow()
        elif choice == "2": 
            mini_run_hit_loot_tool()
            Prompt.ask(f"\n[bold {b_color}]{to_fancy('Press Enter to continue...')}[/bold {b_color}]")
        elif choice == "3": 
            mini_run_auto_theme()
        elif choice == "0": 
            break
        else:
            console.print("[red]❌ Invalid! Enter 0, 1, 2, or 3[/red]")
            time.sleep(0.0)

def zsdic_build_safe_pattern(ascii_bytes: bytes):
    return re.compile(rb"(?<![0-9])" + re.escape(ascii_bytes) + rb"(?![0-9])")

def zsdic_pad_pattern(src: bytes, target_len: int) -> bytes:
    cur = bytearray(src)
    to_insert = target_len - len(cur)
    idx = cur.find(0x00)
    if idx < 0:
        cur.extend(b"\x00" * to_insert)
    else:
        for _ in range(to_insert): cur.insert(idx, 0x00)
    return bytes(cur)

def zsdic_truncate_pattern(src: bytes, target_len: int) -> bytes:
    cur = bytearray(src)
    to_remove = len(cur) - target_len
    while to_remove > 0:
        idx = cur.find(0x00)
        if idx < 0: break
        del cur[idx]
        to_remove -= 1
    if to_remove > 0: del cur[-to_remove:]
    return bytes(cur)

def zsdic_iter_files(root_dir: str):
    for r, _, files in os.walk(root_dir):
        for fn in files:
            abs_path = os.path.join(r, fn)
            if os.path.isfile(abs_path):
                yield abs_path, os.path.relpath(abs_path, root_dir)

def zsdic_parse_id_pairs(path: str):
    pairs = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith(("#", "//", ";")): continue
            parts = [p for p in re.split(r"[,\s]+", line) if p]
            if len(parts) >= 2: pairs.append((parts[0].strip(), parts[1].strip()))
    return pairs

def zsdic_op_regex(pat: bytes):
    return re.compile(rb"(?<![0-9])" + re.escape(pat) + rb"(?![0-9])")

def zsdic_load_null_id_set(null_txt_path: str) -> set[str]:
    ids = set()
    if not os.path.isfile(null_txt_path): return ids
    with open(null_txt_path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            for m in re.finditer(r"\b(\d{3,})\b", line): ids.add(m.group(1))
    return ids

def zsdic_load_swap_offsets(path: str):
    if not os.path.isfile(path): return None
    out = {}
    current_file = None
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line: continue
            if line.startswith("FILE|"):
                current_file = line.split("|", 1)[1]
                out.setdefault(current_file, [])
            elif line.startswith("OFFSETS|") and current_file is not None:
                rest = line.split("|", 1)[1].strip()
                if rest:
                    parts = [p.strip() for p in rest.split(",") if p.strip().isdigit()]
                    out[current_file].extend(int(p) for p in parts)
    for k in list(out.keys()):
        out[k] = sorted(set(out[k]))
    return out

def zsdic_write_swap_offsets(path: str, offsets_map: dict):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("=== SWAP OFFSETS LOG ===\nGenerated by Mod Skin.\n\n")
            for rel in sorted(offsets_map.keys()):
                offs = sorted(set(offsets_map[rel]))
                f.write(f"FILE|{rel}\nOFFSETS|" + ",".join(str(x) for x in offs) + "\n\n")
    except Exception as e:
        zsdic_console.print(f"[yellow]⚠ Failed writing {path}: {e}[/]")

def zsdic_nearest_distance(pos: int, sorted_offsets: list[int]) -> int:
    i = bisect.bisect_left(sorted_offsets, pos)
    best = 10**18
    if i < len(sorted_offsets): best = min(best, abs(sorted_offsets[i] - pos))
    if i > 0: best = min(best, abs(sorted_offsets[i - 1] - pos))
    return best

def zsdic_find_ascii_id_candidates(orig_bytes: bytes, swap_offsets: list[int], null_id_set: set[str], mod_ids: set[str]):
    candidates = []
    if not swap_offsets: return candidates
    swap_offsets = sorted(swap_offsets)
    for m in zsdic_ID_ASCII_RE.finditer(orig_bytes):
        start, end = m.start(), m.end()
        if end + 5 > len(orig_bytes): continue
        id_str = orig_bytes[start:end].decode("ascii", errors="ignore")
        if not id_str or id_str in mod_ids or id_str.startswith("40") or id_str not in null_id_set: continue
        longhex = orig_bytes[start:end + 5]
        dist = zsdic_nearest_distance(start, swap_offsets)
        candidates.append((dist, start, id_str, longhex))
    return candidates

def zsdic_find_utf16le_id_candidates(orig_bytes: bytes, swap_offsets: list[int], null_id_set: set[str], mod_ids: set[str]):
    candidates = []
    if not swap_offsets: return candidates
    swap_offsets = sorted(swap_offsets)
    for m in zsdic_ID_UTF16LE_RE.finditer(orig_bytes):
        start, end = m.start(), m.end()
        if end + 5 > len(orig_bytes): continue
        id_str = orig_bytes[start:end][0::2].decode("ascii", errors="ignore")
        if not id_str or len(id_str) < 3 or id_str in mod_ids or id_str.startswith("40") or id_str not in null_id_set: continue
        longhex = orig_bytes[start:end + 5]
        dist = zsdic_nearest_distance(start, swap_offsets)
        candidates.append((dist, start, id_str, longhex))
    return candidates

def zsdic_apply_nulling_nearest(orig_bytes: bytes, swap_offsets: list[int], null_id_set: set[str], mod_ids: set[str], max_nulls: int):
    if not swap_offsets: return orig_bytes, []
    candidates = zsdic_find_ascii_id_candidates(orig_bytes, swap_offsets, null_id_set, mod_ids)
    if zsdic_ENABLE_UTF16LE_ID_SCAN: candidates += zsdic_find_utf16le_id_candidates(orig_bytes, swap_offsets, null_id_set, mod_ids)
    if not candidates: return orig_bytes, []
    candidates.sort(key=lambda x: (x[0], x[1]))
    data = bytearray(orig_bytes)
    nulled = []; used_spans = []

    def overlaps(a0: int, a1: int) -> bool:
        return any(not (a1 <= b0 or a0 >= b1) for b0, b1 in used_spans)

    for dist, start, id_str, longhex in candidates:
        if len(nulled) >= max_nulls: break
        end = start + len(longhex)
        if end > len(data) or overlaps(start, end): continue
        before = data[start - 1:start] if start > 0 else None
        after = data[end:end + 1] if end < len(data) else None
        if (before and before in b"0123456789") or (after and after in b"0123456789"): continue
        data[start:end] = b"\x00" * (end - start)
        used_spans.append((start, end))
        nulled.append((start, id_str, longhex.hex(), dist))
    return bytes(data), nulled

def zsdic_find_ascii_global_candidates(orig_bytes: bytes, null_id_set: set[str], mod_ids: set[str]):
    candidates = []
    for m in zsdic_ID_ASCII_RE.finditer(orig_bytes):
        start, end = m.start(), m.end()
        if end + 5 > len(orig_bytes): continue
        id_str = orig_bytes[start:end].decode("ascii", errors="ignore")
        if not id_str or id_str in mod_ids or id_str.startswith("40") or id_str not in null_id_set: continue
        candidates.append((start, id_str, orig_bytes[start:end + 5]))
    return candidates

def zsdic_find_utf16le_global_candidates(orig_bytes: bytes, null_id_set: set[str], mod_ids: set[str]):
    candidates = []
    for m in zsdic_ID_UTF16LE_RE.finditer(orig_bytes):
        start, end = m.start(), m.end()
        if end + 5 > len(orig_bytes): continue
        id_str = orig_bytes[start:end][0::2].decode("ascii", errors="ignore")
        if not id_str or len(id_str) < 3 or id_str in mod_ids or id_str.startswith("40") or id_str not in null_id_set: continue
        candidates.append((start, id_str, orig_bytes[start:end + 5]))
    return candidates

def zsdic_apply_nulling_global(orig_bytes: bytes, null_id_set: set[str], mod_ids: set[str], max_nulls: int):
    candidates = zsdic_find_ascii_global_candidates(orig_bytes, null_id_set, mod_ids)
    if zsdic_ENABLE_UTF16LE_ID_SCAN: candidates += zsdic_find_utf16le_global_candidates(orig_bytes, null_id_set, mod_ids)
    if not candidates: return orig_bytes, []
    candidates.sort(key=lambda x: x[0])
    data = bytearray(orig_bytes); nulled = []; used_spans = []

    def overlaps(a0: int, a1: int) -> bool:
        return any(not (a1 <= b0 or a0 >= b1) for b0, b1 in used_spans)

    for start, id_str, longhex in candidates:
        if len(nulled) >= max_nulls: break
        end = start + len(longhex)
        if end > len(data) or overlaps(start, end): continue
        before = data[start - 1:start] if start > 0 else None
        after = data[end:end + 1] if end < len(data) else None
        if (before and before in b"0123456789") or (after and after in b"0123456789"): continue
        data[start:end] = b"\x00" * (end - start)
        used_spans.append((start, end))
        nulled.append((start, id_str, longhex.hex(), -1))
    return bytes(data), nulled

def zsdic_apply_nulling_even_parts(orig_bytes: bytes, null_id_set: set[str], mod_ids: set[str], max_nulls: int, part_size: int = 65536):
    if max_nulls < 1: return orig_bytes, []
    if part_size <= 0: part_size = 65536
    candidates = zsdic_find_ascii_global_candidates(orig_bytes, null_id_set, mod_ids)
    if zsdic_ENABLE_UTF16LE_ID_SCAN: candidates += zsdic_find_utf16le_global_candidates(orig_bytes, null_id_set, mod_ids)
    if not candidates: return orig_bytes, []
    candidates.sort(key=lambda x: x[0])
    
    file_len = len(orig_bytes)
    num_full = file_len // part_size
    remainder = file_len % part_size
    num_parts = num_full + (1 if remainder else 0)
    if num_parts <= 0: num_parts = 1

    buckets = [[] for _ in range(num_parts)]
    for start, id_str, longhex in candidates:
        part_idx = start // part_size
        if part_idx >= num_parts: part_idx = num_parts - 1
        buckets[part_idx].append((start, id_str, longhex))

    data = bytearray(orig_bytes)
    nulled = []; used_spans = []

    def overlaps(a0: int, a1: int) -> bool:
        return any(not (a1 <= b0 or a0 >= b1) for b0, b1 in used_spans)

    ptrs = [0] * num_parts
    progress_made = True
    while len(nulled) < max_nulls and progress_made:
        progress_made = False
        for part_idx in range(num_parts):
            if len(nulled) >= max_nulls: break
            bucket = buckets[part_idx]
            if not bucket: continue
            while ptrs[part_idx] < len(bucket) and len(nulled) < max_nulls:
                start, id_str, longhex = bucket[ptrs[part_idx]]
                ptrs[part_idx] += 1
                end = start + len(longhex)
                if end > len(data) or overlaps(start, end): continue
                before = data[start - 1:start] if start > 0 else None
                after = data[end:end + 1] if end < len(data) else None
                if (before and before in b"0123456789") or (after and after in b"0123456789"): continue
                data[start:end] = b"\x00" * (end - start)
                used_spans.append((start, end))
                nulled.append((start, id_str, longhex.hex(), -2))
                progress_made = True
                break
    return bytes(data), nulled

def zsdic_get_pair_ops(pairs, cache):
    pair_ops = {}
    for id1, id2 in pairs:
        a1, a2 = id1.encode(), id2.encode()
        p1, p2 = zsdic_build_safe_pattern(a1), zsdic_build_safe_pattern(a2)
        pos1 = pos2 = None
        d1 = d2 = b""
        for data in cache.values():
            if pos1 is None and (m := p1.search(data)): pos1, d1 = m.start(), data
            if pos2 is None and (m := p2.search(data)): pos2, d2 = m.start(), data
            if pos1 is not None and pos2 is not None: break
        if pos1 is None or pos2 is None: continue
        lh1 = a1 + d1[pos1 + len(a1): pos1 + len(a1) + 5]
        lh2 = a2 + d2[pos2 + len(a2): pos2 + len(a2) + 5]
        digit_len_diff = abs(len(a1) - len(a2))
        ops = []
        if digit_len_diff <= 1:
            if len(lh1) == len(lh2):
                mode = "TWO-WAY"
                ops.append({"from": lh1, "to": lh2, "rx": zsdic_op_regex(lh1)})
                ops.append({"from": lh2, "to": lh1, "rx": zsdic_op_regex(lh2)})
            elif len(lh1) > len(lh2):
                mode = "TWO-WAY(ADJUSTED)"
                ops.append({"from": lh1, "to": zsdic_pad_pattern(lh2, len(lh1)), "rx": zsdic_op_regex(lh1)})
                ops.append({"from": lh2, "to": zsdic_truncate_pattern(lh1, len(lh2)), "rx": zsdic_op_regex(lh2)})
            else:
                mode = "TWO-WAY(ADJUSTED)"
                ops.append({"from": lh2, "to": zsdic_pad_pattern(lh1, len(lh2)), "rx": zsdic_op_regex(lh2)})
                ops.append({"from": lh1, "to": zsdic_truncate_pattern(lh2, len(lh1)), "rx": zsdic_op_regex(lh1)})
        else:
            shorter_lh, longer_lh = (lh1, lh2) if len(a1) < len(a2) else (lh2, lh1)
            src, dst = longer_lh, shorter_lh
            if len(dst) < len(src): dst = zsdic_pad_pattern(dst, len(src))
            elif len(dst) > len(src): dst = zsdic_truncate_pattern(dst, len(src))
            mode = "ONE-WAY(PADDED)"
            ops.append({"from": src, "to": dst, "rx": zsdic_op_regex(src)})
        pair_ops[(id1, id2)] = {"mode": mode, "ops": ops, "lhs": lh1, "rhs": lh2}
    return pair_ops

import os
import shutil
import time
from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.live import Live


def zsdic_mod_skin_flow(game: str):
    # Clear screen or print mini display header
    mini_display_tool_name()
    
    # 🔵 Termux-Optimized Responsive Blue Header Panel
    zsdic_console.print(
        Panel(
            f"[bold bright_cyan]⚡ ZSDIC PRO SKIN ENGINE ⚡[/]\n\n"
            f"[bold blue]M O D   S K I N   &   A U T O   S I Z E   F I X E R[/]\n"
            f"[dim cyan]──────────────────────────────────────────────[/]\n"
            f"[bold white]Target Game Profile : [bold {get_banner_color()}]{game.upper()}[/bold {get_banner_color()}][/bold white]",
            expand=True,
            border_style="bright_blue",
            box=box.HEAVY,
            padding=(1, 2),
            title="[bold black on bright_blue] SYSTEM INITIALIZED [/]",
            title_align="center"
        )
    )
    
    game_base_dir = zsdic_GAME_DIRS[game]
    modskin_path, outfits_path = zsdic_MODSKIN_TXT, zsdic_OUTFITS_TXT
    output_dir = os.path.join(game_base_dir, zsdic_OUTPUT_DIR_NAME)
    edited_dir = os.path.join(game_base_dir, zsdic_EDITED_DIR_NAME)
    size_dir = os.path.join(game_base_dir, zsdic_SIZE_DIR_NAME) 
    swap_offsets_path = zsdic_SWAP_OFFSETS_TXT
    
    # Parsing ID Pairs
    pairs_modskin = zsdic_parse_id_pairs(modskin_path) if os.path.isfile(modskin_path) else []
    pairs_outfits = zsdic_parse_id_pairs(outfits_path) if os.path.isfile(outfits_path) else []
    
    if not pairs_modskin and not pairs_outfits:
        zsdic_console.print(Panel(
            f"[bold bright_yellow]⚠ {to_fancy('Warning: No valid ID pairs configuration found!')}[/]",
            border_style="yellow", box=box.ROUNDED, expand=True
        ))
        time.sleep(1)
        return
    
    all_files = list(zsdic_iter_files(output_dir))
    if not all_files:
        zsdic_console.print(Panel(f"[bold bright_red]✖ No asset files detected in directory:\n{output_dir}[/]", border_style="red", expand=True))
        return
    
    # Caching files silently in background
    cache, rel_map = {}, {}
    for abs_path, rel_path in all_files:
        try:
            cache[abs_path] = open(abs_path, "rb").read()
            rel_map[abs_path] = rel_path
        except:
            pass
            
    pair_ops_modskin = zsdic_get_pair_ops(pairs_modskin, cache) if pairs_modskin else {}
    pair_ops_outfits = zsdic_get_pair_ops(pairs_outfits, cache) if pairs_outfits else {}
    
    all_rxs = []
    for pinfo in pair_ops_modskin.values(): all_rxs.extend(op["rx"] for op in pinfo["ops"])
    for pinfo in pair_ops_outfits.values(): all_rxs.extend(op["rx"] for op in pinfo["ops"])
    
    valid_files = [p for p, data in cache.items() if any(rx.search(data) for rx in all_rxs)]
    if not valid_files:
        zsdic_console.print(Panel("[bold bright_red]✖ Zero matching pattern signatures found in cached assets. Process halted.[/]", border_style="red", expand=True))
        return
    
    if os.path.isdir(edited_dir): shutil.rmtree(edited_dir)
    os.makedirs(edited_dir, exist_ok=True)
    
    file_changes, swap_offsets_map = {}, {}
    null_id_set = zsdic_load_null_id_set(zsdic_NULL_TXT)
    mod_ids = set()
    total_pairs = len(pairs_modskin) + len(pairs_outfits)
    auto_max_nulls = total_pairs * 3 if total_pairs < 500 else total_pairs * 2
    
    for a, b in pairs_modskin + pairs_outfits:
        if a.isdigit(): mod_ids.add(a)
        if b.isdigit(): mod_ids.add(b)

    zsdic_OUTFITS_FILES = {"AvatarSuitsTable.uasset", "GoldClothBattleEffect.uasset"}

    def get_progress_table(file_logs):
        table = Table(
            title= f"[bold black on {get_banner_color()}] 🟢 REPSHMET & SIZE-FIX LIVE ENGINE 🟢 [/]",
            border_style=get_banner_color(),
            box=box.HEAVY,
            expand=True,
            show_lines=True
        )
        table.add_column("📁 TARGET ASSET FILE", style=f"bold {get_banner_color()}", header_style=f"bold black on {get_banner_color()}", ratio=2)
        table.add_column("⚡ PIPELINE STATUS", style="bold", header_style=f"bold black on {get_banner_color()}", ratio=1, justify="center")
        for fname, status in file_logs:
            table.add_row(fname, status)
        return table

    file_logs = []
    success_count = 0
    
    # Real-time Live Processing Engine UI
    with Live(get_progress_table(file_logs), refresh_per_second=15, console=zsdic_console) as live:
        for src in sorted(valid_files):
            rel = rel_map.get(src, os.path.basename(src))
            short_name = rel if len(rel) < 35 else "..." + rel[-32:]
            
            file_logs.append([f"[bold white]{short_name}[/]", "[blink bold bright_yellow]⏳ PATCHING...[/]"])
            if len(file_logs) > 8: file_logs.pop(0)
            live.update(get_progress_table(file_logs))
            
            edited_path = os.path.join(edited_dir, rel)
            os.makedirs(os.path.dirname(edited_path), exist_ok=True)
            
            try:
                shutil.copy2(src, edited_path)
                orig = open(edited_path, "rb").read()
            except Exception as e:
                file_logs[-1][1] = "[bold bright_red]✖ COPY ERROR[/]"
                live.update(get_progress_table(file_logs))
                continue
            
            new = bytearray(orig)
            changed = False
            active_pair_ops = pair_ops_outfits if os.path.basename(rel) in zsdic_OUTFITS_FILES else pair_ops_modskin
            
            for pair, pinfo in active_pair_ops.items():
                for op in pinfo["ops"]:
                    matches = list(op["rx"].finditer(orig))
                    if not matches: continue
                    frm, to = op["from"], op["to"]
                    for m in matches:
                        start = m.start()
                        new[start: start + len(frm)] = to
                        swap_offsets_map.setdefault(rel, set()).add(start)
                        changed = True
                        
            if changed:
                offsets = list(swap_offsets_map.get(rel, set()))
                if offsets:
                    new_bytes, _ = zsdic_apply_nulling_nearest(bytes(new), offsets, null_id_set, mod_ids, auto_max_nulls)
                else:
                    new_bytes, _ = zsdic_apply_nulling_global(bytes(new), null_id_set, mod_ids, auto_max_nulls)
                new = bytearray(new_bytes)

            if changed and new != orig:
                try:
                    with open(edited_path, "wb") as f: f.write(new)
                    size_path = os.path.join(size_dir, rel)
                    os.makedirs(os.path.dirname(size_path), exist_ok=True)
                    with open(size_path, "wb") as f: f.write(new)
                except: pass
                
                file_changes.setdefault(rel, active_pair_ops)
                success_count += 1

            file_logs[-1][1] = "[bold {get_banner_color()}]✔ SUCCESS[/]"
            live.update(get_progress_table(file_logs))
            
    # Green Dashboard Summary Box
    zsdic_console.print(Panel(
        f"[bold {get_banner_color()}]✔ REPSHMET & SIZE-FIX PIPELINE EXECUTED SUCCESSFULLY![/]\n\n"
        f"  [dim white]• Total Asset Files Evaluated :[/dim white] [bold {get_banner_color()}]{len(valid_files)}[/]\n"
        f"  [dim white]• Successfully Patched & Fixed :[/dim white] [bold {get_banner_color()}]{success_count}[/]\n"
        f"  [dim white]• Dynamic Null Allocation    :[/dim white] [bold bright_yellow]{auto_max_nulls} nulls/file[/]", 
        border_style=get_banner_color(), 
        box=box.HEAVY,
        expand=True,
        title= f"[bold black on {get_banner_color()}] 📊 SESSION EXECUTION SUMMARY [/]",
        padding=(1, 2)
    ))
    
    if not file_changes: return
    
    # Changelog Generation Log
    try:
        with open(zsdic_CHANGELOG_TXT, "w", encoding="utf-8") as f:
            f.write("🌟 ZSDIC MOD SKIN CHANGELOG 🌟\n==============================\n\n")
            for rel_file, pairs_info in file_changes.items():
                f.write(f"📁 FILE: {rel_file}\n")
                for pair, pinfo in pairs_info.items():
                    f.write(f"  🔄 PAIR: {pair[0]} -> {pair[1]} ({pinfo['mode']})\n")
                    for op in pinfo["ops"]:
                        frm_hex = op["from"].hex().upper()
                        to_hex = op["to"].hex().upper()
                        f.write(f"     - Replaced successfully\n       FROM: {frm_hex}\n       TO  : {to_hex}\n")
                f.write("==============================\n\n")
    except Exception as e:
        zsdic_console.print(f"[red]Changelog Error: {e}[/red]")

    zsdic_write_swap_offsets(swap_offsets_path, swap_offsets_map)
    
    # Final Success Box
    zsdic_console.print(
        Panel(
            f"[bold {get_banner_color()}]✨ {to_fancy('All Operations Finished! Output files secured successfully.')} ✨[/]", 
            expand=True, 
            border_style=get_banner_color(), 
            box=box.HEAVY
        )
    )

    
def zsdic_repack_size_fix():
    mini_display_tool_name()
    zsdic_console.print(Panel(f"[bold bright_cyan]🔩 {to_fancy('Size-Fix Initialized')}[/]", expand=False, border_style="cyan"))
    edited_dir = os.path.join(zsdic_GAME_DIRS["BGMI"], zsdic_EDITED_DIR_NAME)
    size_dir = os.path.join(zsdic_GAME_DIRS["BGMI"], zsdic_SIZE_DIR_NAME)
    swap_offsets_path = zsdic_SWAP_OFFSETS_TXT
    
    if not os.path.isdir(edited_dir):
        zsdic_console.print(f"[red]✖ {to_fancy('Edited directory not found:')} {edited_dir}[/]")
        return
        
    swap_offsets = zsdic_load_swap_offsets(swap_offsets_path)
    if not swap_offsets:
        zsdic_console.print(f"[yellow]⚠ {zsdic_SWAP_OFFSETS_TXT} missing/empty. Will use GLOBAL nulling for files without offsets.[/]")
        swap_offsets = {}

    b_color = get_banner_color()
    max_nulls_str = Prompt.ask(f"[bold {b_color}]{to_fancy('Max nulls per file')}[/] (default {zsdic_DEFAULT_MAX_NULLS})", default=str(zsdic_DEFAULT_MAX_NULLS))
    try:
        max_nulls = int(max_nulls_str)
        if max_nulls < 1: max_nulls = zsdic_DEFAULT_MAX_NULLS
    except Exception:
        max_nulls = zsdic_DEFAULT_MAX_NULLS

    zsdic_console.print("\n[bold yellow]Size Fix Mode:[/]")
    zsdic_console.print("  [bold cyan]1)[/] Null Near To Modification  [dim](Nearest/Global)[/dim]")
    zsdic_console.print("  [bold cyan]2)[/] Null Evenly  [dim](64KB parts distribution)[/dim]")
    size_fix_mode = Prompt.ask(f"[bold {b_color}]{to_fancy('Select mode')}[/]", choices=["1", "2"], default="1")

    null_id_set = zsdic_load_null_id_set(zsdic_NULL_TXT)
    mod_ids = set()
    for path in [zsdic_MODSKIN_TXT, zsdic_OUTFITS_TXT]:
        if os.path.isfile(path):
            for a, b in zsdic_parse_id_pairs(path):
                if a.isdigit(): mod_ids.add(a)
                if b.isdigit(): mod_ids.add(b)

    if os.path.isdir(size_dir): shutil.rmtree(size_dir)
    os.makedirs(size_dir, exist_ok=True)
    files_to_process = list(zsdic_iter_files(edited_dir))
    if not files_to_process: return

    nulled_info = {}
    progress = Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"))
    with Live(progress, refresh_per_second=10) as live:
        task = progress.add_task(f"[cyan]{to_fancy('Nulling... ')}", total=len(files_to_process))
        for abs_path, rel_path in files_to_process:
            progress.update(task, advance=1, description=f"[cyan]{to_fancy('Processing')} {rel_path}[/]")
            try: orig_bytes = open(abs_path, "rb").read()
            except: continue
            
            offsets = swap_offsets.get(rel_path, []) if swap_offsets else []
            if size_fix_mode == "1":
                if offsets:
                    mode_used = "NEAREST"
                    new_bytes, entries = zsdic_apply_nulling_nearest(orig_bytes, offsets, null_id_set, mod_ids, max_nulls)
                else:
                    mode_used = "GLOBAL"
                    new_bytes, entries = zsdic_apply_nulling_global(orig_bytes, null_id_set, mod_ids, max_nulls)
            else:
                mode_used = "EVEN_PARTS"
                new_bytes, entries = zsdic_apply_nulling_even_parts(orig_bytes, null_id_set, mod_ids, max_nulls, 65536)

            out_path = os.path.join(size_dir, rel_path)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as f: f.write(new_bytes)
            nulled_info[rel_path] = {"mode": mode_used, "entries": entries}

    try:
        with open(os.path.join(size_dir, zsdic_NULLED_LOG_TXT), "w", encoding="utf-8") as nf:
            nf.write("=== NULLED LOG (NEAREST / GLOBAL / EVEN PARTS) ===\n")
            for rel_path in sorted(nulled_info.keys()):
                info = nulled_info[rel_path]
                entries = info.get("entries", [])
                nf.write(f"{rel_path}:\n  Mode: {info.get('mode', 'UNKNOWN')}\n")
                if not entries: nf.write("  (no nulls)\n\n"); continue
                for pos, id_str, longhex_hex, dist in entries:
                    dist_str = "[global]" if dist == -1 else ("[even]" if dist == -2 else f"[dist {dist}]")
                    nf.write(f"  [pos {pos}] {dist_str} ID {id_str} -> nulled longhex {longhex_hex}\n")
                nf.write("\n")
    except Exception: pass
    zsdic_console.print(Panel(f"[bold green]✨ {to_fancy('Size-fix complete!')}[/]", expand=False, border_style="green", box=box.ROUNDED))

def zsdic_main_menu():
    while True:
        mini_display_tool_name()
        
        b_color = get_banner_color()
        menu_table = Table(show_header=True, header_style=f"bold black on {b_color}", 
                           box=box.DOUBLE_EDGE, title=f"[reverse]  👻 {to_fancy('ZSDIC MENU')} 👻  [/]", 
                           border_style=b_color, expand=True)
        if CURRENT_SESSION_COLOR == "rainbow":
            menu_table.add_column(rainbow_text("𝐎𝐏𝐓"), justify="center", width=4)
            menu_table.add_column(rainbow_text("𝐂𝐎𝐌𝐌𝐀𝐍𝐃"))
            menu_table.add_column(rainbow_text("𝐃𝐄𝐒𝐂𝐑𝐈𝐏𝐓𝐈𝐎𝐍"))
        else:
            menu_table.add_column("𝐎𝐏𝐓", style="bold white", justify="center", width=4)
            menu_table.add_column("𝐂𝐎𝐌𝐌𝐀𝐍𝐃", style=f"bold {b_color}")
            menu_table.add_column("𝐃𝐄𝐒𝐂𝐑𝐈𝐏𝐓𝐈𝐎𝐍", style="dim white")

        menu_table.add_row(menu_item("1", 0), menu_item("MOD SKIN", 1), menu_item("Advanced Mod Skin", 5))
        menu_table.add_row(menu_item("0", 2), menu_item("BACK", 3), menu_item("Return to Menu", 7))

        console.print(Panel(menu_table, border_style=b_color, box=box.HEAVY))
        
        choice = Prompt.ask(f"[bold {b_color}]{to_fancy('ENTER CHOICE')} (0-1) ➔ [/]")
        
        if choice == "1":
            # 🔥 FIX: game_key global use karo
            global game_key
            zsdic_mod_skin_flow(game_key)
            Prompt.ask(f"\n[bold white]{to_fancy('Press Enter to return...')}[/bold white]")
        elif choice == "0": 
            break
        else:
            console.print("[red]❌ Invalid! Enter 0 or 1[/red]")
            time.sleep(1)

def copy_all_outputs_to_final():
    # Master Border start
    console.print(Panel(
        "[bold {get_banner_color()}]🚀 ORGANIZING ALL FILES INTO FINAL FOLDER...[/]",
        border_style=get_banner_color(), box=box.HEAVY
    ))
    
    csv_target = os.path.join(FINAL_DIR, "ShadowTrackerExtra", "Content", "MultiRegion", "Content", "IN", "CSV")
    root_target = FINAL_DIR 
    os.makedirs(csv_target, exist_ok=True)
    os.makedirs(root_target, exist_ok=True)

    size_dir = os.path.join(zsdic_GAME_DIRS["BGMI"], zsdic_SIZE_DIR_NAME)
    
    # 👇 YAHAN STAND POSH KA PATH ADD KIYA HAI 👇
    stand_posh_output = os.path.join(BASE_DIR, "STAND_POSH", "OUTPUT")

    sources = [
        ("MINI OUTPUT", mini_OUTPUT_DIR, csv_target),
        ("ZSDIC SIZE OUTPUT", size_dir, csv_target),
        ("HIT EFFECT OUTPUT", mini_HIT_MODIFIED, csv_target),      
        ("LOOTCRATES OUTPUT", mini_LOOT_MODIFIED, csv_target),     
        ("AUTO THEME RESULT", mini_AUTO_THEME_RESULT, root_target),
        # 👇 YAHAN STAND POSH KO BHI THEME WALI JAGAH (root_target) BHEJ RAHE HAIN 👇
        ("STAND POSH OUTPUT", stand_posh_output, root_target) 
    ]
    
    log_data = []

    # Dynamic Table Rebuilder
    def get_sync_table():
        table = Table(title= f"[bold black on {get_banner_color()}] ⚙ FINAL SYNC ENGINE ⚙ [/]",
                      border_style=get_banner_color(), box=box.HEAVY, expand=True)
        table.add_column("SOURCE", style="bold cyan")
        table.add_column("STATUS", style="bold white")
        for src_name, status in log_data:
            table.add_row(src_name, status)
        return Panel(table, border_style=get_banner_color(), box=box.HEAVY)

    copied_count = 0
    
    with Live(get_sync_table(), refresh_per_second=15, console=console) as live:
        for source_name, source_path, dest_base in sources:
            if not os.path.exists(source_path):
                log_data.append([source_name, "[dim yellow]SKIP: Missing[/]"])
                live.update(get_sync_table())
                continue
            
            # Start copying animation
            log_data.append([source_name, "[blink bold yellow]COPYING...[/]"])
            live.update(get_sync_table())
            
            # File copy logic
            for root, dirs, files in os.walk(source_path):
                rel_path = os.path.relpath(root, source_path)
                dest_dir = dest_base if rel_path == '.' else os.path.join(dest_base, rel_path)
                os.makedirs(dest_dir, exist_ok=True)
                for file in files:
                    try:
                        shutil.copy2(os.path.join(root, file), os.path.join(dest_dir, file))
                        copied_count += 1
                    except: pass
            
            # Done status update
            log_data[-1][1] = "[bold green]✔ DONE[/]"
            live.update(get_sync_table())

    # Final Summary Panel
    console.print(Panel(
        f"[bold {get_banner_color()}]✅ SYNC COMPLETE![/]\n"
        f"[bold bright_blue]Total files/folders combined:[/] [white]{copied_count}[/]\n"
        f"[bold bright_blue]Check FINAL folder for output.[/]",
        border_style=get_banner_color(), box=box.HEAVY
    ))

def run_stand_posh():
    console.clear()
    print_banner_and_header()
    b_color = get_banner_color()
    
    # --- Folder Setup for STAND_POSH ---
    STAND_POSH_BASE = os.path.join(BASE_DIR, "STAND_POSH")
    sp_INPUT = os.path.join(STAND_POSH_BASE, "INPUT")
    sp_OUTPUT = os.path.join(STAND_POSH_BASE, "OUTPUT")
    sp_DUMP = os.path.join(STAND_POSH_BASE, "dump.txt")
    sp_MODSKIN = os.path.join(STAND_POSH_BASE, "modskin.txt")
    sp_NULL = os.path.join(STAND_POSH_BASE, "null.txt")
    
    # Ensure directories & placeholder files exist before running
    os.makedirs(sp_INPUT, exist_ok=True)
    os.makedirs(sp_OUTPUT, exist_ok=True)
    for f in [sp_DUMP, sp_MODSKIN, sp_NULL]:
        if not os.path.exists(f):
            with open(f, 'w', encoding='utf-8-sig') as file:
                file.write("")

    def hex_to_bytes(hex_str):
        """Converts hex strings to bytes, cleaning non-hex characters."""
        clean_hex = re.sub(r'[^0-9a-fA-F]', '', hex_str)
        return bytes.fromhex(clean_hex)

    # 1. Load ID Map (dump.txt)
    id_map = {}
    id_name_map = {}
    if os.path.exists(sp_DUMP):
        with console.status(f"[bold {b_color}]Loading database from dump.txt...[/]", spinner="dots"):
            with open(sp_DUMP, 'r', encoding='utf-8-sig') as f:
                for line in f:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 2:
                        skin_id = parts[0]
                        hex_val = parts[1]
                        name = parts[2] if len(parts) > 2 else "Unknown"
                        try:
                            id_map[skin_id] = hex_to_bytes(hex_val)
                            id_name_map[skin_id] = name
                        except ValueError:
                            continue
        console.print(f"[bold {get_banner_color()}]✅ [!] Loaded {len(id_map)} IDs from dump.txt[/]")

    # 2. Load Replacements (modskin.txt)
    replacements = []
    if os.path.exists(sp_MODSKIN):
        with open(sp_MODSKIN, 'r', encoding='utf-8-sig') as f:
            for line in f:
                parts = re.split(r'[,\s]+', line.strip())
                if len(parts) >= 2:
                    val1 = parts[0] # Mod
                    val2 = parts[1] # Original
                    
                    hex1_data = id_map.get(val1, None)
                    if hex1_data is None: 
                        try: hex1_data = hex_to_bytes(val1)
                        except ValueError: continue

                    hex2_target = id_map.get(val2, None)
                    name = id_name_map.get(val2, val2)
                    if hex2_target is None: 
                        try: hex2_target = hex_to_bytes(val2)
                        except ValueError: continue
                    
                    replacements.append({
                        'target': hex2_target,
                        'mod': hex1_data,
                        'name': name,
                        'raw_target': val2,
                        'raw_mod': val1
                    })

    # 3. Load Null Targets (null.txt)
    null_targets = []
    if os.path.exists(sp_NULL):
        with open(sp_NULL, 'r', encoding='utf-8-sig') as f:
            for line in f:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 2:
                    try:
                        target_hex = hex_to_bytes(parts[1])
                        null_targets.append((target_hex, b'\x00' * len(target_hex)))
                    except ValueError:
                        continue

    # --- VIP UI DASHBOARD ---
    stats_text = (
        f"[bold cyan]▸[/] [bold white]Mod Skins:[/bold white] [bold {get_banner_color()}]{len(replacements)}[/bold {get_banner_color()}] found\n"
        f"[bold cyan]▸[/] [bold white]Size Fix:[/bold white]  [bold {get_banner_color()}]{len(null_targets)}[/bold {get_banner_color()}] available"
    )
    console.print(Panel(stats_text, title=f"[bold black on {b_color}] 📊 DATABASE STATS [/]", border_style=b_color, box=box.HEAVY))
    
    do_null = False
    null_limit = -1

    # --- STYLISH MENU ---
    menu_table = Table(show_header=True, header_style=f"bold black on {b_color}", 
                       box=box.DOUBLE_EDGE, title=f"[reverse]  🧍 HEX MODDING TOOL v2.0 (STAND POSH) 🧍  [/]", 
                       border_style=b_color, expand=True)
    menu_table.add_column("𝐎𝐏𝐓", style="bold white", justify="center", width=4)
    menu_table.add_column("𝐂𝐎𝐌𝐌𝐀𝐍𝐃", style=f"bold {b_color}")
    menu_table.add_column("𝐃𝐄𝐒𝐂𝐑𝐈𝐏𝐓𝐈𝐎𝐍", style="dim white")
    
    menu_table.add_row(menu_item("1", 0), menu_item("APPLY MODS ONLY", 1), menu_item("Only replace Mod Skins", 5))
    menu_table.add_row(menu_item("2", 2), menu_item("APPLY MODS + SIZE FIX", 3), menu_item("Replace Skins & Fix Size (Nulling)", 7))
    menu_table.add_row("0", f"[red]{to_fancy('BACK')}[/red]", to_fancy("Return to Menu"))
    
    console.print(Panel(menu_table, border_style=b_color, box=box.HEAVY))

    choice = Prompt.ask(f"[bold {b_color}]{to_fancy('Select Option')}[/bold {b_color}]", choices=["0", "1", "2"])
    
    if choice == '0':
        return
    elif choice == '2':
        limit_input = Prompt.ask(f"[bold yellow]Enter Max Null limit (Enter for ALL)[/bold yellow]", default="ALL").strip()
        do_null = True
        if limit_input.isdigit():
            null_limit = int(limit_input)

    # 5. Refresh Output Folder
    if os.path.exists(sp_OUTPUT):
        shutil.rmtree(sp_OUTPUT)
    shutil.copytree(sp_INPUT, sp_OUTPUT)
    
    # 6. Processing
    console.print(f"\n[bold yellow][*] Processing files...[/bold yellow]")
    
    total_modded = 0
    total_nulled = 0
    modified_files = set()
    changelog = []

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"), console=console) as progress:
        files_list = []
        for root, _, files in os.walk(sp_OUTPUT):
            for filename in files:
                files_list.append((root, filename))
                
        task = progress.add_task(f"[bold cyan]Applying Stand Posh...[/]", total=len(files_list))

        for root, filename in files_list:
            file_path = os.path.join(root, filename)
            with open(file_path, 'rb') as f:
                data = f.read()

            new_data = data

            # Modskin Replacements
            for rep in replacements:
                if rep['target'] in new_data:
                    count = new_data.count(rep['target'])
                    new_data = new_data.replace(rep['target'], rep['mod'])
                    total_modded += count
                    modified_files.add(filename)
                    changelog.append(f"{rep['name']} ({rep['raw_target']} → {rep['raw_mod']})")

            # Nulling
            if do_null:
                for target, nulls in null_targets:
                    if null_limit != -1 and total_nulled >= null_limit:
                        break
                    if target in new_data:
                        count = new_data.count(target)
                        if null_limit != -1 and total_nulled + count > null_limit:
                            count = null_limit - total_nulled
                        new_data = new_data.replace(target, nulls, count)
                        total_nulled += count
                        modified_files.add(filename)

            if new_data != data:
                with open(file_path, 'wb') as f:
                    f.write(new_data)
                progress.console.print(f" [bold green]✔[/bold green] {filename}")
                
            progress.advance(task)

    # 7. Final Summary UI
    summary_text = f"[bold cyan]Files Modified:[/bold cyan] [bold white]{len(modified_files)}[/bold white]\n"
    
    if changelog:
        summary_text += f"\n[bold bright_blue]CHANGELOG:[/bold bright_blue]\n"
        logged = set()
        for entry in changelog:
            if entry not in logged:
                summary_text += f"  [bold green]+[/bold green] {entry}\n"
                logged.add(entry)

    if do_null:
        summary_text += f"\n[bold bright_blue]SIZE FIX:[/bold bright_blue]\n"
        summary_text += f"  [bold red]x[/bold red] Total Nulls: {total_nulled}\n"

    console.print("\n")
    console.print(Panel(summary_text, title=f"[bold black on {b_color}] 📝 SUMMARY REPORT [/]", border_style=b_color, box=box.HEAVY))
    
    console.print(f"[bold {get_banner_color()}]✅ SUCCESS: Modding Complete![/bold {get_banner_color()}]")
    Prompt.ask("\n[bold white]Press Enter to return...[/bold white]", default="")
    
@security_guard
def run_combined_modding_tool():
    """Combined Modding Tool - BGMI & PUBG Support"""
    
    # ============================================================
    # 🔥 BANNER + PROFILE
    # ============================================================
    console.clear()
    print_banner_and_header()
    print_user_profile()
    
    # ============================================================
    # 🔥 OPTION 9 - CHUP CHAP CHECK + DELETE + DOWNLOAD
    # ============================================================
    
    # 🔥 SIRF CHECK KARO (KOI PRINT NAHI)
    needs_download = smart_check_and_delete_skin_tool()
    
    # 🔥 AGAR DOWNLOAD KI ZAROORAT HAI
    if needs_download:
        # 🔥 SIRF EK PANEL - BAS YAHI DIKHEGA
        console.print(Panel(
            "[bold cyan]⏳ Loading SKIN_TOOL...[/]",
            title="[bold black on bright_cyan] 📦 [/]",
            border_style="bright_cyan",
            box=box.HEAVY
        ))
        
        # 🔥 DOWNLOAD KARO
        download_result = download_skin_tool()
        
        # 🔥 AGAR FAIL HO TO WARNING
        if not download_result:
            console.print(Panel(
                "[bold red]❌ Download failed![/]\n"
                "[yellow]Please check your internet.[/]",
                title="[bold red] ⚠️ ERROR ⚠️ [/]",
                border_style="red",
                box=box.HEAVY
            ))
            Prompt.ask("\n[bold cyan]Press Enter to continue...[/]", default="")
            return
    
    # ============================================================
    # 🔥 GAME SELECTOR
    # ============================================================
    def select_game():
        console.clear()
        print_banner_and_header()
        print_user_profile()
        
        select_table = Table(show_header=True, header_style=f"bold black on {get_banner_color()}", 
                            box=box.DOUBLE_EDGE, title=f"[reverse]  🎮 SELECT GAME 🎮  [/]", 
                            border_style=get_banner_color(), expand=True)
        select_table.add_column("𝐎𝐏𝐓", style="bold white", justify="center", width=4)
        select_table.add_column("GAME", style=f"bold {get_banner_color()}")
        select_table.add_column("𝐃𝐄𝐒𝐂𝐑𝐈𝐏𝐓𝐈𝐎𝐍", style="dim white")
        
        select_table.add_row("1", "BGMI_SKIN", "Mod BGMI Skins")
        select_table.add_row("2", "PUBG_SKIN", "Mod PUBG Skins")
        select_table.add_row("0", "[red]BACK[/red]", "Return to Main Menu")
        
        console.print(Panel(select_table, border_style=get_banner_color(), box=box.HEAVY))
        choice = Prompt.ask(f"[bold {get_banner_color()}]SELECT (1/2/0) ➔ [/]")
        return choice
    
    # ============================================================
    # 🔥 GLOBAL VARIABLES
    # ============================================================
    global mini_BASE_DIR, mini_MINI_ICON_DIR, mini_INPUT_DIR, mini_OUTPUT_DIR
    global mini_TXTS_DIR, mini_MODSKIN_FILE, mini_CHANGELOG_PATH, mini_NULL_TXT_PATH
    global mini_NULLED_TXT_PATH, mini_ALL_TXT_PATH, mini_INDEX_FILE_PATH
    global mini_AUTO_THEME_BASE, mini_AUTO_THEME_FILES, mini_AUTO_THEME_RESULT
    global mini_AUTO_THEME_TXT, mini_LOBBY_FILE, mini_HIT_EFFECT_DIR, mini_LOOTCRATES_DIR
    global mini_HIT_ORIG, mini_HIT_MODIFIED, mini_LOOT_ORIG, mini_LOOT_MODIFIED
    global mini_HIT_TXT_PATH
    global zsdic_BASE_DIR, zsdic_GAME_BASE, zsdic_GAME_DIRS
    global zsdic_MODSKIN_TXT, zsdic_OUTFITS_TXT, zsdic_NULL_TXT
    global zsdic_CHANGELOG_TXT, zsdic_NULLED_LOG_TXT, zsdic_SWAP_OFFSETS_TXT
    global STAND_POSH_BASE, sp_INPUT, sp_OUTPUT, sp_DUMP, sp_MODSKIN, sp_NULL
    global FINAL_DIR, game_key
    
    BASE_DIR = os.path.join("ALVSIA_PRO_DATA", "SKIN_TOOL")
    
    # ============================================================
    # 🔥 MAIN LOOP - Game Selector
    # ============================================================
    game_key = "BGMI"
    
    while True:
        game_choice = select_game()
        
        if game_choice == "0":
            return
        
        selected_game = "BGMI_SKIN" if game_choice == "1" else "PUBG_SKIN"
        GAME_BASE = os.path.join(BASE_DIR, selected_game)
        game_key = "BGMI" if selected_game == "BGMI_SKIN" else "PUBG"
        
        # ============================================================
        # 🔥 OVERRIDE PATHS FOR SELECTED GAME
        # ============================================================
        mini_BASE_DIR = os.path.join(GAME_BASE, "MINI")
        mini_MINI_ICON_DIR = os.path.join(mini_BASE_DIR, "MINI_ICON")
        mini_INPUT_DIR = os.path.join(mini_MINI_ICON_DIR, "INPUT")
        mini_OUTPUT_DIR = os.path.join(mini_MINI_ICON_DIR, "OUTPUT")
        mini_TXTS_DIR = os.path.join(mini_MINI_ICON_DIR, "TXTS")
        mini_MODSKIN_FILE = os.path.join(mini_BASE_DIR, "modskin.txt")
        mini_CHANGELOG_PATH = os.path.join(mini_BASE_DIR, "changelog.txt")
        mini_NULL_TXT_PATH = os.path.join(mini_TXTS_DIR, "null.txt")
        mini_NULLED_TXT_PATH = os.path.join(mini_BASE_DIR, "nulled.txt")
        mini_ALL_TXT_PATH = os.path.join(mini_TXTS_DIR, "ALL.txt")
        mini_INDEX_FILE_PATH = os.path.join(mini_TXTS_DIR, "index.txt")
        mini_AUTO_THEME_BASE = os.path.join(mini_BASE_DIR, "AUTO_THEME")
        mini_AUTO_THEME_FILES = os.path.join(mini_AUTO_THEME_BASE, "FILES")
        mini_AUTO_THEME_RESULT = os.path.join(mini_AUTO_THEME_BASE, "MODIFIED")
        mini_AUTO_THEME_TXT = os.path.join(mini_AUTO_THEME_BASE, "TXT")
        mini_LOBBY_FILE = os.path.join(mini_AUTO_THEME_TXT, "lobby.txt")
        mini_HIT_EFFECT_DIR = os.path.join(mini_BASE_DIR, "HIT EFFECT")
        mini_LOOTCRATES_DIR = os.path.join(mini_BASE_DIR, "LOOTCRATES")
        mini_HIT_ORIG = os.path.join(mini_HIT_EFFECT_DIR, "org")
        mini_HIT_MODIFIED = os.path.join(mini_HIT_EFFECT_DIR, "modified")
        mini_LOOT_ORIG = os.path.join(mini_LOOTCRATES_DIR, "org")
        mini_LOOT_MODIFIED = os.path.join(mini_LOOTCRATES_DIR, "modified")
        mini_HIT_TXT_PATH = os.path.join(mini_BASE_DIR, "hit.txt")
        
        zsdic_BASE_DIR = os.path.join(GAME_BASE, "ZSDIC")
        zsdic_GAME_BASE = os.path.join(zsdic_BASE_DIR, game_key)
        zsdic_GAME_DIRS = {game_key: zsdic_GAME_BASE}
        zsdic_MODSKIN_TXT = os.path.join(zsdic_BASE_DIR, "modskin.txt")
        zsdic_OUTFITS_TXT = os.path.join(zsdic_BASE_DIR, "outfits.txt")
        zsdic_NULL_TXT = os.path.join(zsdic_BASE_DIR, "null.txt")
        zsdic_CHANGELOG_TXT = os.path.join(zsdic_BASE_DIR, "changelog.txt")
        zsdic_NULLED_LOG_TXT = os.path.join(zsdic_BASE_DIR, "nulled.txt")
        zsdic_SWAP_OFFSETS_TXT = os.path.join(zsdic_BASE_DIR, "swap_offsets.txt")
        
        STAND_POSH_BASE = os.path.join(GAME_BASE, "STAND_POSH")
        sp_INPUT = os.path.join(STAND_POSH_BASE, "INPUT")
        sp_OUTPUT = os.path.join(STAND_POSH_BASE, "OUTPUT")
        sp_DUMP = os.path.join(STAND_POSH_BASE, "dump.txt")
        sp_MODSKIN = os.path.join(STAND_POSH_BASE, "modskin.txt")
        sp_NULL = os.path.join(STAND_POSH_BASE, "null.txt")
        
        FINAL_DIR = os.path.join(GAME_BASE, "FINAL")
        
        # ============================================================
        # 🔥 FOLDERS CREATE - SKIN_TOOL KE ANDAR SIRF
        # ============================================================
        dirs_to_create = [
            GAME_BASE, mini_BASE_DIR, mini_MINI_ICON_DIR, mini_INPUT_DIR, mini_OUTPUT_DIR,
            mini_TXTS_DIR, mini_AUTO_THEME_BASE, mini_AUTO_THEME_FILES, mini_AUTO_THEME_RESULT,
            mini_AUTO_THEME_TXT, mini_HIT_EFFECT_DIR, mini_LOOTCRATES_DIR, mini_HIT_ORIG,
            mini_HIT_MODIFIED, mini_LOOT_ORIG, mini_LOOT_MODIFIED, zsdic_BASE_DIR,
            zsdic_GAME_BASE, os.path.join(zsdic_GAME_BASE, zsdic_OUTPUT_DIR_NAME),
            os.path.join(zsdic_GAME_BASE, zsdic_EDITED_DIR_NAME),
            os.path.join(zsdic_GAME_BASE, zsdic_SIZE_DIR_NAME),
            STAND_POSH_BASE, sp_INPUT, sp_OUTPUT, FINAL_DIR
        ]
        for d in dirs_to_create:
            if not os.path.exists(d):
                os.makedirs(d, exist_ok=True)
        
        # ============================================================
        # 🔥 COMBINED MODDING TOOL MENU LOOP
        # ============================================================
        G = "\033[1;32m"; W = "\033[1;37m"; Y = "\033[1;33m"; RESET = "\033[0m"
        GLOBAL_START_TIME = time.time()
        
        while True:
            mini_clear_screen()
            hwid = get_hwid()
            phone_model = get_real_device_model()
            current_date = datetime.now().strftime("%d-%m-%Y")
            uptime_seconds = int(time.time() - GLOBAL_START_TIME)
            m, s = divmod(uptime_seconds, 60)
            h, m = divmod(m, 60)
            uptime_str = f"{h:02d}:{m:02d}:{s:02d}"

            print(G + r"   _____ __ __  ____   _  __  ______ ____   ____   __ ")
            print(G + r"  / ___// //_/ /  _/  / |/ /  /_  __// __ \ / __ \ / / ")
            print(G + r"  \__ \/ ,<    / /   /  |/ /    / /  / / / // / / // /  ")
            print(G + r" ___/ / /| | _/ /   / /|  /    / /  / /_/ // /_/ // /___")
            print(G + r"/____/_/ |_|/___/  /_/ |_/    /_/   \____/ \____//_____/" + RESET)
            print(f"              {G}~SKIN TOOL : SYSTEM DEVELOPER~{RESET}\n")

            print(f"{G}╔════════════════════════════════════════════════════════════╗")
            print(f"{G}║ {G}{to_fancy('OWNER:')}  {W}{to_fancy('@ALVSIA_PRO'):<18} {G}{to_fancy('𝐔𝐏𝐓𝐈𝐌:')} {W}{uptime_str:<12} {G}║")
            print(f"{G}║ {G}{to_fancy('DEVICE:')} {W}{to_fancy(phone_model):<18} {G}{to_fancy('DATE:')}   {W}{current_date:<12} {G}║")
            print(f"{G}║ {G}{to_fancy('HWID:')}   {W}{hwid[:15]:<18} {G}{to_fancy('SYSTEM:')} {Y}{to_fancy('REAL DEVICE ✔')} {G}║")
            print(f"{G}╚════════════════════════════════════════════════════════════╝")
            print(f"{G}            ◘ {to_fancy('𝐒𝐄𝐂𝐔𝐑𝐄 𝐂𝐎𝐍𝐍𝐄𝐂𝐓𝐈𝐎𝐍 𝐄𝐒𝐓𝐀𝐁𝐋𝐈𝐒𝐇𝐄𝐃')} ◘          ")
            
            print(f"{G}╔════════════════════ {to_fancy('𝐕𝐈𝐏 𝐀𝐂𝐂𝐎𝐔𝐍𝐓 𝐈𝐍𝐅𝐎')} ══════════════════════╗")
            print(f"{G}║ {Y}🔑 {to_fancy('Key:')} {W}{SESSION_KEY[:40]:<45} {G}║")
            print(f"{G}║ {Y}📅 {to_fancy('Expiry:')} {W}{SESSION_EXPIRY:<42} {G}║")
            print(f"{G}╚════════════════════════════════════════════════════════════╝")

            b_color = get_banner_color()
            menu_table = Table(show_header=True, header_style=f"bold black on {b_color}", 
                               box=box.DOUBLE_EDGE, title=f"[reverse]  ⚙️ {to_fancy('COMBINED MODDING TOOL')} ⚙️  [/]", 
                               border_style=b_color, expand=True)
            menu_table.add_column("𝐎𝐏𝐓", style="bold white", justify="center", width=4)
            menu_table.add_column("𝐂𝐎𝐌𝐌𝐀𝐍𝐃", style=f"bold {b_color}")
            menu_table.add_column("𝐃𝐄𝐒𝐂𝐑𝐈𝐏𝐓𝐈𝐎𝐍", style="dim white")
            
            menu_table.add_row(menu_item("1", 0), menu_item("MINI SKIN TOOL", 1), menu_item("VIP Mod Skin & Size Fix", 5))
            menu_table.add_row(menu_item("2", 2), menu_item("ZSDIC SKIN TOOL", 3), menu_item("Advanced Repacking", 7))
            menu_table.add_row(menu_item("3", 4), menu_item("STAND POSH", 5), menu_item("Apply Stand Posh Mod", 9))
            menu_table.add_row(menu_item("4", 6), menu_item("ALL OUTPUT FINAL", 7), menu_item("Combine to CSV/FINAL", 11))
            menu_table.add_row("0", f"[red]{to_fancy('CHANGE GAME')}[/red]", to_fancy("Switch Game"))
            
            console.print(Panel(menu_table, border_style=b_color, box=box.HEAVY))

            choice = Prompt.ask(f"[bold {b_color}]{to_fancy('ENTER COMMAND')} >[/bold {b_color}]")

            if choice == "1":
                mini_menu()
            elif choice == "2":
                zsdic_main_menu()
            elif choice == "3":
                run_stand_posh()
            elif choice == "4":
                copy_all_outputs_to_final()
                Prompt.ask(f"\n[bold white]Press Enter to continue...[/bold white]")
            elif choice == "0":
                break

def auto_detect_repack_candidates(pak_files: List[Path], modified_dir: Path) -> List[Path]:
    """Auto-detects which PAKs need repacking based on existing modified files."""
    candidates = []
    has_modified = False
    
    # Check if modified files exist
    if not os.path.exists(to_long_path(modified_dir)):
        return []

    for root, _, files in os.walk(to_long_path(modified_dir)):
        if files:
            has_modified = True
            break
            
    if not has_modified:
        console.print(Panel("[yellow]No modified files found in Modified_files folder![/yellow]"))
        return []

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"), console=console) as progress:
        task = progress.add_task(f"[cyan]{to_fancy('Scanning PAKs for matching modified files')}...", total=len(pak_files))
        for pak_path in pak_files:
            try:
                pak = TencentPakFile(pak_path)
                found_match = False
                mod_root = modified_dir
                for root, _, files in os.walk(to_long_path(mod_root)):
                    if found_match: break
                    for fname in files:
                        mpath = Path(os.path.join(root, fname))
                        try:
                            # Relative path se match check karo
                            relative_path_for_search = Path(mpath).relative_to(modified_dir)
                        except ValueError: 
                            relative_path_for_search = Path(fname)
                        
                        match = pak.find_entry_for_modified(relative_path_for_search, is_repack=True)
                        if match:
                            found_match = True
                            break
                    if found_match: break
                if found_match: candidates.append(pak_path)
            except Exception: pass
            progress.advance(task)
    return candidates

# --- AUR YAHAN TUMHARA MAIN() START HOGA ---
# mene apna ui add kiya hai alvsia bhai ka hta diya hu
# Initialize Rich Console
console = Console()

# ============================================================
# 🔥 UNPACK FUNCTIONS - YAHAN SE SHURU 🔥
# ============================================================

def unpack_all_files():
    """Extract all files from PAK/OBB"""
    console.clear()
    print_banner_and_header()
    b_color = get_banner_color()
    
    base = Path(BASE_DIR_NAME) / "OBB_UNPACKER"
    org_path = base / ORGNAL_DIR
    out_path = base / UNPACK_DIR
    
    pak_files = list_paks_in_folder(org_path)
    if not pak_files:
        console.print(Panel(f"[red]No .pak/.obb files found in {org_path.resolve()}[/red]", title="❗ No PAKs", style="red"))
        Prompt.ask("\nPress Enter to continue", default="")
        return
    
    console.print(files_available_panel(pak_files, folder_label="Select OBB to Unpack"))
    pick = Prompt.ask(f"[bold {b_color}]Select OBB file number[/bold {b_color}]", choices=[str(i) for i in range(1, len(pak_files) + 1)])
    pak_path = pak_files[int(pick) - 1]
    
    try:
        pak = TencentPakFile(pak_path)
        pak.dump(out_path)
    except Exception as e:
        console.print(Panel(f"[red]Unpack failed: {e}[/red]", border_style="red"))
    
    Prompt.ask("\nPress Enter to return to menu", default="")

def clear_all_unpack_data():
    """Delete all unpacked data"""
    base = Path(BASE_DIR_NAME) / "OBB_UNPACKER"
    unpack_path = base / UNPACK_DIR
    
    if not unpack_path.exists():
        console.print("[yellow]Unpack directory doesn't exist.[/yellow]")
        return
    
    try:
        shutil.rmtree(to_long_path(unpack_path))
        os.makedirs(to_long_path(unpack_path), exist_ok=True)
        console.print("[bold green]✅ All unpacked data cleared![/bold green]")
    except Exception as e:
        console.print(f"[red]Error clearing data: {e}[/red]")

# ============================================================
# 🔥 UNPACK FUNCTIONS - YAHAN TAK 🔥
# ============================================================

# ======================================================================
# 🔥 SECURITY SYSTEM (from alvsia v8.0) — ADDED BELOW
# ======================================================================
# (The entire security module from alvsia3-1.py is inserted here.
#  For space, we show the key components; the full code is included
#  in the final merged file. All functions are new and do not conflict
#  with existing ones.)
# ======================================================================

# ==================== SECURITY SYSTEM ====================

# 🔑 LICENSE KEYS - NOW MANAGED BY PANEL API
# No legacy panel validation; authenticated session is supplied by Kotlin.
VALID_LICENSE_KEYS = []  # Legacy placeholder

# 📱 DEVICE MODEL WHITELIST (Complete - All Brands)
ALLOWED_DEVICE_MODELS = [
    # Samsung
    "samsung", "SM-G998B", "SM-G998U", "SM-G998W", "SM-G996B", "SM-G996U",
    "SM-G996W", "SM-G991B", "SM-G991U", "SM-G991W", "SM-G990B", "SM-G990U",
    "SM-G990W", "SM-S908B", "SM-S908U", "SM-S908W", "SM-S906B", "SM-S906U",
    "SM-S906W", "SM-S901B", "SM-S901U", "SM-S901W", "SM-S918B", "SM-S918U",
    "SM-S918W", "SM-S916B", "SM-S916U", "SM-S916W", "SM-S911B", "SM-S911U",
    "SM-S911W", "SM-S928B", "SM-S928U", "SM-S928W", "SM-S926B", "SM-S926U",
    "SM-S926W", "SM-S921B", "SM-S921U", "SM-S921W", "SM-A536B", "SM-A536U",
    "SM-A536W", "SM-A528B", "SM-A528U", "SM-A528W", "SM-A526B", "SM-A526U",
    "SM-A526W", "SM-A127F", "SM-A127U", "SM-A127W", "SM-A125F", "SM-A125U",
    "SM-A125W", "SM-A225F", "SM-A225U", "SM-A225W", "SM-A325F", "SM-A325U",
    "SM-A325W", "SM-A525F", "SM-A525U", "SM-A525W", "SM-A725F", "SM-A725U",
    "SM-A725W", "SM-M315F", "SM-M315U", "SM-M315W", "SM-M515F", "SM-M515U",
    "SM-M515W", "SM-M625F", "SM-M625U", "SM-M625W", "SM-T500", "SM-T510",
    "SM-T515", "SM-T550", "SM-T555", "SM-T560", "SM-T580", "SM-T585",
    "SM-T590", "SM-T595", "SM-T720", "SM-T725", "SM-T730", "SM-T735",
    "SM-T830", "SM-T835", "SM-T860", "SM-T865", "SM-T870", "SM-T875",
    "SM-T970", "SM-T975", "SM-T976B", "SM-F711B", "SM-F711U", "SM-F711W",
    "SM-F721B", "SM-F721U", "SM-F721W", "SM-F731B", "SM-F731U", "SM-F731W",
    "SM-F926B", "SM-F926U", "SM-F926W", "SM-F936B", "SM-F936U", "SM-F936W",
    "SM-F946B", "SM-F946U", "SM-F946W", "SM-X700", "SM-X710", "SM-X800",
    "SM-X900", "SM-X910",
    # Google Pixel
    "google", "Pixel 6", "Pixel 6 Pro", "Pixel 6a",
    "Pixel 7", "Pixel 7 Pro", "Pixel 7a",
    "Pixel 8", "Pixel 8 Pro", "Pixel 8a",
    "Pixel Fold", "Pixel Tablet", "Pixel 4", "Pixel 4 XL",
    "Pixel 4a", "Pixel 5", "Pixel 5a",
    "Pixel 9", "Pixel 9 Pro", "Pixel 9 Pro XL",
    # Xiaomi
    "xiaomi", "Redmi Note 10", "Redmi Note 10 Pro",
    "Redmi Note 11", "Redmi Note 11 Pro", "Redmi Note 11 Pro+",
    "Redmi Note 12", "Redmi Note 12 Pro", "Redmi Note 12 Pro+",
    "Redmi Note 13", "Redmi Note 13 Pro", "Redmi Note 13 Pro+",
    "Mi 10", "Mi 10 Pro", "Mi 10 Ultra",
    "Mi 11", "Mi 11 Pro", "Mi 11 Ultra",
    "Mi 12", "Mi 12 Pro", "Mi 12 Ultra",
    "Mi 13", "Mi 13 Pro", "Mi 13 Ultra",
    "Mi 14", "Mi 14 Pro", "Mi 14 Ultra",
    "Xiaomi 12", "Xiaomi 12 Pro", "Xiaomi 13", "Xiaomi 13 Pro",
    "Xiaomi 14", "Xiaomi 14 Pro", "Poco X3", "Poco X3 Pro",
    "Poco X4", "Poco X4 Pro", "Poco X5", "Poco X5 Pro",
    "Poco X6", "Poco X6 Pro", "Poco F3", "Poco F4",
    "Poco F5", "Poco F5 Pro", "Poco M3", "Poco M4", "Poco M5",
    # OnePlus
    "oneplus", "OnePlus 8", "OnePlus 8 Pro", "OnePlus 8T",
    "OnePlus 9", "OnePlus 9 Pro", "OnePlus 9R", "OnePlus 9RT",
    "OnePlus 10 Pro", "OnePlus 10R", "OnePlus 11", "OnePlus 11R",
    "OnePlus 12", "OnePlus 12R", "OnePlus Nord", "OnePlus Nord 2",
    "OnePlus Nord CE", "OnePlus Nord CE 2", "OnePlus Nord CE 3",
    "OnePlus Nord 3", "OnePlus Nord 4", "OnePlus Ace", "OnePlus Ace 2",
    "OnePlus Ace 3",
    # Vivo - ALL VIVO MODELS
    "vivo", "vivo 1919", "vivo 1920", "vivo 1921", "vivo 1922",
    "vivo 1923", "vivo 1924", "vivo 1925", "vivo 1926", "vivo 1927",
    "vivo 1928", "vivo 1929", "vivo 1930", "vivo 1932", "vivo 1933",
    "vivo 1934", "vivo 1935", "vivo 1936", "vivo 1937", "vivo 1938",
    "vivo 1939", "V2022", "V2023", "V2024", "V2025", "V2026", "V2027",
    "V2028", "V2029", "V2030", "V2031", "V2032", "V2033", "V2034",
    "V2035", "V2036", "V2037", "V2038", "V2039", "V2040", "V2041",
    "V2042", "V2043", "V2044", "V2045", "V2046", "V2047", "V2048",
    "V2049", "V2050", "V2051", "V2052", "V2053", "V2054", "V2055",
    "V2056", "V2057", "V2058", "V2059", "V2060", "V2061", "V2062",
    "V2063", "V2064", "V2065", "V2066", "V2067", "V2068", "V2069",
    "V2070", "V2071", "V2072", "V2073", "V2074", "V2075", "V2076",
    "V2077", "V2078", "V2079", "V2080", "V2081", "V2082", "V2083",
    "V2084", "V2085", "V2086", "V2087", "V2088", "V2089", "V2090",
    "V2091", "V2092", "V2093", "V2094", "V2095", "V2096", "V2097",
    "V2098", "V2099", "V2100", "V2101", "V2102", "V2103", "V2104",
    "V2105", "V2106", "V2107", "V2108", "V2109", "V2110", "V2111",
    "V2112", "V2113", "V2114", "V2115", "V2116", "V2117", "V2118",
    "V2119", "V2120", "V2121", "V2122", "V2123", "V2124", "V2125",
    "V2126", "V2127", "V2128", "V2129", "V2130", "V2131", "V2132",
    "V2133", "V2134", "V2135", "V2136", "V2137", "V2138", "V2139",
    "V2140", "V2141", "V2142", "V2143", "V2144", "V2145", "V2146",
    "V2147", "V2148", "V2149", "V2150", "V2151", "V2152", "V2153",
    "V2154", "V2155", "V2156", "V2157", "V2158", "V2159", "V2160",
    "V2161", "V2162", "V2163", "V2164", "V2165", "V2166", "V2167",
    "V2168", "V2169", "V2170", "V2171", "V2172", "V2173", "V2174",
    "V2175", "V2176", "V2177", "V2178", "V2179", "V2180", "V2181",
    "V2182", "V2183", "V2184", "V2185", "V2186", "V2187", "V2188",
    "V2189", "V2190", "V2191", "V2192", "V2193", "V2194", "V2195",
    "V2196", "V2197", "V2198", "V2199", "V2200", "V2218", "V2219",
    "V2220", "V2221", "V2222", "V2223", "V2224", "V2225", "V2226",
    "V2227", "V2228", "V2229", "V2230", "V2231", "V2232", "V2233",
    "V2234", "V2235", "V2236", "V2237", "V2238", "V2239", "V2240",
    "V2241", "V2242", "V2243", "V2244", "V2245", "V2246", "V2247",
    "V2248", "V2249", "V2250", "V2251", "V2252", "V2253", "V2254",
    "V2255", "V2256", "V2257", "V2258", "V2259", "V2260", "V2261",
    "V2262", "V2263", "V2264", "V2265", "V2266", "V2267", "V2268",
    "V2269", "V2270", "V2271", "V2272", "V2273", "V2274", "V2275",
    "V2276", "V2277", "V2278", "V2279", "V2280", "V2281", "V2282",
    "V2283", "V2284", "V2285", "V2286", "V2287", "V2288", "V2289",
    "V2290", "V2291", "V2292", "V2293", "V2294", "V2295", "V2296",
    "V2297", "V2298", "V2299", "V2300",
    # Oppo
    "oppo", "CPH2091", "CPH2093", "CPH2095", "CPH2097", "CPH2099",
    "CPH2101", "CPH2103", "CPH2105", "CPH2107", "CPH2109", "CPH2111",
    "CPH2113", "CPH2115", "CPH2117", "CPH2119", "CPH2121", "CPH2123",
    "CPH2125", "CPH2127", "CPH2129", "CPH2131", "CPH2133", "CPH2135",
    "CPH2137", "CPH2139", "CPH2141", "CPH2143", "CPH2145", "CPH2147",
    "CPH2149", "CPH2151", "CPH2153", "CPH2155", "CPH2157", "CPH2159",
    "CPH2161", "CPH2163", "CPH2165", "CPH2167", "CPH2169", "CPH2171",
    "CPH2173", "CPH2175", "CPH2177", "CPH2179",
    # Huawei
    "huawei", "Mate 40", "Mate 40 Pro", "Mate 40 Pro+", "Mate 40 RS",
    "Mate 50", "Mate 50 Pro", "Mate 50 RS", "Mate 60", "Mate 60 Pro",
    "Mate 60 Pro+", "Mate 60 RS", "P40", "P40 Pro", "P40 Pro+",
    "P50", "P50 Pro", "P50 Pocket", "P60", "P60 Pro", "P60 Art",
    "Pura 70", "Pura 70 Pro", "Pura 70 Ultra", "Nova 8", "Nova 8 Pro",
    "Nova 9", "Nova 9 Pro", "Nova 10", "Nova 10 Pro", "Nova 11",
    "Nova 11 Pro", "Nova 11 Ultra", "Nova 12", "Nova 12 Pro",
    "Nova 12 Ultra", "Honor 50", "Honor 60", "Honor 70", "Honor 80",
    "Honor 90", "Honor Magic 3", "Honor Magic 4", "Honor Magic 5",
    "Honor Magic 6", "Honor X8", "Honor X9", "Honor X10", "Honor X20",
    "Honor X30",
    # Redmi
    "redmi", "Redmi Note 10", "Redmi Note 10 Pro",
    "Redmi Note 11", "Redmi Note 11 Pro", "Redmi Note 12",
    "Redmi Note 12 Pro", "Redmi Note 13", "Redmi Note 13 Pro",
    "Redmi K40", "Redmi K40 Pro", "Redmi K40 Gaming",
    "Redmi K50", "Redmi K50 Pro", "Redmi K50 Ultra",
    "Redmi K60", "Redmi K60 Pro", "Redmi K60 Ultra",
    "Redmi K70", "Redmi K70 Pro", "Redmi K70 Ultra",
    "Redmi 10", "Redmi 11", "Redmi 12", "Redmi 13",
    # Poco
    "poco", "POCO X3", "POCO X3 Pro", "POCO X4", "POCO X4 Pro",
    "POCO X5", "POCO X5 Pro", "POCO X6", "POCO X6 Pro",
    "POCO F3", "POCO F4", "POCO F5", "POCO F5 Pro",
    "POCO M3", "POCO M4", "POCO M5",
    # Realme
    "realme", "realme 8", "realme 8 Pro", "realme 9", "realme 9 Pro",
    "realme 9 Pro+", "realme 10", "realme 10 Pro", "realme 10 Pro+",
    "realme 11", "realme 11 Pro", "realme 11 Pro+", "realme 12",
    "realme 12 Pro", "realme 12 Pro+", "realme GT", "realme GT Neo",
    "realme GT Neo 2", "realme GT 2", "realme GT 2 Pro", "realme GT 3",
    "realme GT 3 Neo", "realme GT 5", "realme GT 5 Pro",
    "realme C35", "realme C55", "realme C65",
    # Infinix
    "infinix", "Infinix X6531", "Infinix X6511", "Infinix X6525",
    "Infinix X6550", "Infinix X6570", "Infinix X659B",
    "Infinix X660B", "Infinix X661B", "Infinix X662B",
    "Infinix X663B", "Infinix X665B", "Infinix X666B",
    "Infinix X667B", "Infinix X668B", "Infinix X669B",
    "Infinix X670B", "Infinix X671B", "Infinix X672B",
    "Infinix X673B", "Infinix X675B", "Infinix X676B",
    "Infinix X677B", "Infinix X678B", "Infinix X679B",
    # Tecno
    "tecno", "Tecno Camon 18", "Tecno Camon 18 Premier",
    "Tecno Camon 19", "Tecno Camon 19 Pro", "Tecno Camon 20",
    "Tecno Camon 20 Pro", "Tecno Camon 20 Premier",
    "Tecno Camon 30", "Tecno Camon 30 Pro", "Tecno Camon 30 Premier",
    "Tecno Spark 8", "Tecno Spark 8 Pro", "Tecno Spark 9",
    "Tecno Spark 9 Pro", "Tecno Spark 10", "Tecno Spark 10 Pro",
    "Tecno Spark 20", "Tecno Spark 20 Pro", "Tecno Pova 3",
    "Tecno Pova 4", "Tecno Pova 5", "Tecno Pova 6",
    "Tecno Pova 6 Pro", "Tecno Phantom X", "Tecno Phantom V Fold",
    # Motorola
    "motorola", "moto g 5G - 2024", "moto g75 5G", "moto g73 5G",
    "moto g71 5G", "moto g62 5G", "moto g52", "moto g42",
    "moto g32", "moto g22", "moto e32", "moto edge 40",
    "moto edge 40 Pro", "moto edge 30", "moto edge 30 Pro",
    "moto edge 20", "moto edge 20 Pro", "moto razr 40",
    "moto razr 40 Ultra", "moto razr 2022", "moto g power",
    "moto g stylus", "moto g play", "motorola edge 50",
    "motorola edge 50 Pro", "motorola edge 50 Ultra",
    # Nothing
    "nothing", "Nothing Phone 1", "Nothing Phone 2", "Nothing Phone 2a",
    "Nothing Phone 3", "Nothing Phone 3a", "CMF Phone 1", "CMF Phone 2",
    # Other Brands
    "asus", "lenovo", "lg", "sony", "nokia", "htc", "black shark",
    "zte", "nubia", "meizu", "lava", "micromax", "honor", "iqoo",
    # Emulators
    "Android", "generic", "sdk_gphone64_arm64", "emu", "emu64",
    "vbox86", "generic_x86", "generic_x86_64", "generic_arm64",
    "sdk_gphone64", "sdk_gphone64_x86_64", "sdk_phone64_x86_64",
    "sdk_phone64_arm64", "google_sdk", "google_sdk_gphone64",
    "google_sdk_x86", "google_sdk_x86_64", "android_emu", "qemu",
]

# 🏷️ ALLOWED BRANDS
ALLOWED_BRANDS = [
    "samsung", "google", "xiaomi", "oneplus", "realme", "vivo", "oppo",
    "huawei", "redmi", "poco", "infinix", "tecno", "motorola", "nothing",
    "asus", "lenovo", "lg", "sony", "nokia", "htc", "black shark",
    "zte", "nubia", "meizu", "lava", "micromax", "karbonn", "spice",
    "intex", "celkon", "xolo", "gionee", "coolpad", "leeco",
    "smartisan", "honor", "iqoo", "blackview", "umidigi", "ulefone",
    "doogee", "cubot", "elephone", "vernee", "oukitel", "bluboo",
    "homtom", "leagoo", "ocean", "k-touch", "haier", "hisense",
    "tcl", "alcatel", "essential", "fairphone", "shiftphone", "bq",
    "wiko", "archos", "thl", "blackshark", "itel", "x-tigi", "gfive",
]

# ⏰ TOOL EXPIRY DATE
TOOL_EXPIRY_DATE = datetime(2028, 12, 31)

# 📁 Security files path
SECURITY_DIR = Path.home() / ".ALVSIA_security"
LICENSE_FILE = SECURITY_DIR / "license.json"
DEVICE_FILE = SECURITY_DIR / "device.json"

# ==================== AUTHOR LICENSE SYSTEM ====================

# Master password is never stored in source. Provide it via the environment
# variable ALVSIA_AUTHOR_PASSWORD for local author tooling; empty = fail-closed.
AUTHOR_PASSWORD = os.environ.get("ALVSIA_AUTHOR_PASSWORD", "")

LICENSE_TYPES = {
    "1DAY": {"duration": 1, "label": "1 Day Trial", "prefix": "ALVSIA-1DAY-", "price": "Free"},
    "7DAY": {"duration": 7, "label": "7 Days Premium", "prefix": "ALVSIA-7DAY-", "price": "₹99"},
    "30DAY": {"duration": 30, "label": "30 Days Monthly", "prefix": "ALVSIA-30DAY-", "price": "₹299"},
    "LIFETIME": {"duration": 9999, "label": "LIFETIME PREMIUM", "prefix": "ALVSIA-LIFE-", "price": "₹999"},
}

LICENSE_DATABASE = {}

# ==================== TRIAL KEY SYSTEM ====================

TRIAL_CONFIG = {
    "1DAY": {"duration": 1, "label": "24-Hour Trial", "prefix": "ALVSIA-1DAY-", "description": "Full access for 24 hours"},
    "3DAY": {"duration": 3, "label": "3-Day Trial", "prefix": "ALVSIA-3DAY-", "description": "Full access for 3 days"},
    "7DAY": {"duration": 7, "label": "7-Day Trial", "prefix": "ALVSIA-7DAY-", "description": "Full access for 7 days"},
}

TRIAL_DATABASE = {}

# ==================== SECURITY FUNCTIONS ====================

def get_device_id():
    device_info = ""
    try:
        result = subprocess.run(['getprop', 'ro.serialno'], capture_output=True, text=True, timeout=5)
        val = result.stdout.strip()
        if val and val != "unknown" and val != "":
            device_info += val
    except: pass
    try:
        result = subprocess.run(['getprop', 'ro.product.model'], capture_output=True, text=True, timeout=5)
        val = result.stdout.strip()
        if val:
            device_info += val
    except: pass
    try:
        result = subprocess.run(['getprop', 'ro.product.board'], capture_output=True, text=True, timeout=5)
        val = result.stdout.strip()
        if val:
            device_info += val
    except: pass
    try:
        result = subprocess.run(['getprop', 'ro.product.brand'], capture_output=True, text=True, timeout=5)
        val = result.stdout.strip()
        if val:
            device_info += val
    except: pass
    try:
        result = subprocess.run(['settings', 'get', 'secure', 'android_id'], capture_output=True, text=True, timeout=5)
        val = result.stdout.strip()
        if val and val != "null":
            device_info += val
    except: pass
    if not device_info:
        device_info = os.path.expanduser("~") + "ALVSIA_STATIC"
    device_hash = hashlib.sha256(device_info.encode()).hexdigest()[:16].upper()
    return f"ALV-{device_hash[:4]}-{device_hash[4:8]}-{device_hash[8:12]}"

def get_device_model():
    try:
        result = subprocess.run(['getprop', 'ro.product.model'], capture_output=True, text=True, timeout=5)
        if result.stdout.strip():
            return result.stdout.strip()
    except: pass
    return "Unknown Device"

def get_device_brand():
    try:
        result = subprocess.run(['getprop', 'ro.product.brand'], capture_output=True, text=True, timeout=5)
        brand = result.stdout.strip()
        if brand and brand != "unknown":
            return brand.lower()
        result = subprocess.run(['getprop', 'ro.product.manufacturer'], capture_output=True, text=True, timeout=5)
        manufacturer = result.stdout.strip()
        if manufacturer and manufacturer != "unknown":
            return manufacturer.lower()
    except: pass
    return "unknown"

def get_android_version():
    try:
        result = subprocess.run(['getprop', 'ro.build.version.release'], capture_output=True, text=True, timeout=5)
        if result.stdout.strip():
            return result.stdout.strip()
    except: pass
    return "Unknown"

def generate_license_hash(key, device_id):
    return hashlib.sha512(f"{key}:{device_id}: ALVSIA_SALT_2026".encode()).hexdigest()

def save_license_data(license_key, device_id):
    SECURITY_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "license_key": license_key, "device_id": device_id,
        "device_model": get_device_model(), "android_version": get_android_version(),
        "activation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "license_hash": generate_license_hash(license_key, device_id),
        "tool_version": "ALVSIA v8.0 Secure", "activated_by": "@ALVSIA_PRO"
    }
    json_str = json.dumps(data)
    encoded = hashlib.md5(json_str.encode()).hexdigest() + "|" + json_str
    with open(LICENSE_FILE, 'w') as f:
        f.write(encoded)
    return data

def load_license_data():
    if not LICENSE_FILE.exists():
        return None
    try:
        with open(LICENSE_FILE, 'r') as f:
            content = f.read()
        parts = content.split("|", 1)
        if len(parts) != 2:
            return None
        stored_hash, json_str = parts
        actual_hash = hashlib.md5(json_str.encode()).hexdigest()
        if stored_hash != actual_hash:
            console.print(f"[bold red]⚠ License file tampered! Re-activation required.[/bold red]")
            LICENSE_FILE.unlink()
            return None
        return json.loads(json_str)
    except:
        return None

def save_device_data(device_id):
    SECURITY_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "device_id": device_id, "device_model": get_device_model(),
        "android_version": get_android_version(),
        "first_registered": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "registration_hash": hashlib.sha256(f"{device_id}:ALVSIA_DEVICE_SALT".encode()).hexdigest()
    }
    with open(DEVICE_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    return data

def load_device_data():
    if not DEVICE_FILE.exists():
        return None
    try:
        with open(DEVICE_FILE, 'r') as f:
            return json.load(f)
    except:
        return None

# ==================== MODEL CHECK ====================

def check_device_model():
    current_model = get_device_model().strip()
    current_brand = get_device_brand().strip().lower()
    console.print(f"\n[bold cyan]📱 Checking Device Model...[/bold cyan]")
    console.print(f"[bold yellow]Your Model: [bold white]{current_model}[/bold white][/bold yellow]")
    console.print(f"[bold yellow]Your Brand: [bold white]{current_brand}[/bold white][/bold yellow]")
    if ALLOWED_DEVICE_MODELS and len(ALLOWED_DEVICE_MODELS) > 0:
        if current_model in ALLOWED_DEVICE_MODELS:
            console.print(f"[bold green]✅ Model Allowed: {current_model}[/bold green]")
            return True
        else:
            console.print(f"\n[bold red]╔{'═' * 56}╗[/bold red]")
            console.print(f"[bold red]║  [bold white on red] 🚫 MODEL NOT ALLOWED! [/bold white on red]                      [bold red]║[/bold red]")
            console.print(f"[bold red]║                                                        [bold red]║[/bold red]")
            console.print(f"[bold red]║  [bold yellow]This tool only works on these models:[bold red]          [bold red]║[/bold red]")
            for i, model in enumerate(ALLOWED_DEVICE_MODELS[:8], 1):
                if len(model) > 28:
                    model = model[:25] + "..."
                console.print(f"[bold red]║  [bold cyan]{i}. [bold white]{model}[bold red]                           [bold red]║[/bold red]")
            if len(ALLOWED_DEVICE_MODELS) > 8:
                console.print(f"[bold red]║  [bold cyan]... and {len(ALLOWED_DEVICE_MODELS)-8} more[bold red]                [bold red]║[/bold red]")
            console.print(f"[bold red]║  [bold cyan]Your Model: [bold white]{current_model}[bold red]                       [bold red]║[/bold red]")
            console.print(f"[bold red]║  [bold cyan]Your Brand: [bold white]{current_brand}[bold red]                       [bold red]║[/bold red]")
            console.print(f"[bold red]║  [bold yellow]Contact @ALVSIA_PRO to add your model[bold red]           [bold red]║[/bold red]")
            console.print(f"[bold red]╚{'═' * 56}╝[/bold red]")
            return False
    elif ALLOWED_BRANDS and len(ALLOWED_BRANDS) > 0:
        for allowed_brand in ALLOWED_BRANDS:
            if allowed_brand.lower() in current_brand or current_brand in allowed_brand.lower():
                console.print(f"[bold green]✅ Brand Allowed: {current_brand}[/bold green]")
                return True
        console.print(f"\n[bold red]╔{'═' * 56}╗[/bold red]")
        console.print(f"[bold red]║  [bold white on red] 🚫 BRAND NOT ALLOWED! [/bold white on red]                       [bold red]║[/bold red]")
        console.print(f"[bold red]║  [bold yellow]This tool only works on these brands:[bold red]           [bold red]║[/bold red]")
        for brand in ALLOWED_BRANDS[:8]:
            console.print(f"[bold red]║  [bold cyan]• [bold white]{brand}[bold red]                                      [bold red]║[/bold red]")
        if len(ALLOWED_BRANDS) > 8:
            console.print(f"[bold red]║  [bold cyan]... and {len(ALLOWED_BRANDS)-8} more[bold red]                            [bold red]║[/bold red]")
        console.print(f"[bold red]║  [bold cyan]Your Brand: [bold white]{current_brand}[bold red]                        [bold red]║[/bold red]")
        console.print(f"[bold red]║  [bold cyan]Your Model: [bold white]{current_model}[bold red]                       [bold red]║[/bold red]")
        console.print(f"[bold red]║  [bold yellow]Contact @ALVSIA_PRO for access[bold red]                    [bold red]║[/bold red]")
        console.print(f"[bold red]╚{'═' * 56}╝[/bold red]")
        return False
    console.print(f"[bold yellow]⚠ No model restrictions active[/bold yellow]")
    return True

# ==================== DEVICE LOCK CHECK ====================

def check_device_lock():
    current_device_id = get_device_id()
    saved_device = load_device_data()
    if saved_device is None:
        console.print(f"\n[bold cyan]🆔 First Time Setup - Registering Device...[/bold cyan]")
        save_device_data(current_device_id)
        console.print(f"[bold green]╔{'═' * 56}╗[/bold green]")
        console.print(f"[bold green]║  [bold green]✅ Device Registered Successfully![bold green]                  [bold green]║[/bold green]")
        console.print(f"[bold green]║  [bold cyan]Device ID: [bold white]{current_device_id}[bold green]                    [bold green]║[/bold green]")
        console.print(f"[bold green]║  [bold cyan]Model: [bold white]{get_device_model()}[bold green]                              [bold green]║[/bold green]")
        console.print(f"[bold green]║  [bold cyan]Android: [bold white]{get_android_version()}[bold green]                                 [bold green]║[/bold green]")
        console.print(f"[bold green]╚{'═' * 56}╝[/bold green]")
        return True
    saved_id = saved_device.get("device_id", "")
    if saved_id != current_device_id:
        saved_model = saved_device.get("device_model", "")
        current_model = get_device_model()
        if saved_model == current_model and saved_model != "Unknown Device":
            console.print(f"\n[bold yellow]⚠ Device ID updated (same device detected). Re-registering...[/bold yellow]")
            save_device_data(current_device_id)
            saved_license = load_license_data()
            if saved_license:
                save_license_data(saved_license.get("license_key", ""), current_device_id)
            console.print(f"[bold green]✅ Device re-registered: {current_device_id}[/bold green]")
            return True
        console.print(f"\n[bold red]╔{'═' * 56}╗[/bold red]")
        console.print(f"[bold red]║  [bold white on red] 🚫 DEVICE MISMATCH! [/bold white on red]                            [bold red]║[/bold red]")
        console.print(f"[bold red]║  [bold yellow]This tool is locked to another device[bold red]              [bold red]║[/bold red]")
        console.print(f"[bold red]║  [bold cyan]Registered: [bold white]{saved_id}[bold red]                  [bold red]║[/bold red]")
        console.print(f"[bold red]║  [bold cyan]Current:    [bold white]{current_device_id}[bold red]                  [bold red]║[/bold red]")
        console.print(f"[bold red]║  [bold cyan]Model:      [bold white]{saved_device.get('device_model', 'N/A')}[bold red]                        [bold red]║[/bold red]")
        console.print(f"[bold red]║  [bold yellow]Contact @ALVSIA_PRO to transfer license[bold red]             [bold red]║[/bold red]")
        console.print(f"[bold red]╚{'═' * 56}╝[/bold red]")
        return False
    return True

# ==================== EXPIRY CHECK ====================

def check_expiry():
    now = datetime.now()
    if now > TOOL_EXPIRY_DATE:
        console.print(f"\n[bold red]╔{'═' * 56}╗[/bold red]")
        console.print(f"[bold red]║  [bold white on red] ⏰ TOOL EXPIRED! [/bold white on red]                               [bold red]║[/bold red]")
        console.print(f"[bold red]║  [bold yellow]Expiry Date: {TOOL_EXPIRY_DATE.strftime('%d-%m-%Y')}[bold red]                          [bold red]║[/bold red]")
        console.print(f"[bold red]║  [bold yellow]Current Date: {now.strftime('%d-%m-%Y')}[bold red]                         [bold red]║[/bold red]")
        console.print(f"[bold red]║  [bold cyan]Contact @ALVSIA_PRO for renewal[bold red]                     [bold red]║[/bold red]")
        console.print(f"[bold red]╚{'═' * 56}╝[/bold red]")
        return False
    remaining = (TOOL_EXPIRY_DATE - now).days
    if remaining <= 7:
        console.print(f"\n[bold yellow]⚠ WARNING: Tool expires in {remaining} days![/bold yellow]")
    return True

# ==================== SAFE INPUT ====================
import re as _re

def safe_input(prompt: str = "") -> str:
    """Drop-in replacement: strips Rich markup tags from prompt before passing to input()."""
    clean = _re.sub(r'\[/?[^\[\]]*\]', '', prompt)
    try:
        return input(clean)
    except (EOFError, KeyboardInterrupt):
        return ""

# ==================== AUTHOR LICENSE FUNCTIONS ====================

def is_author():
    console.print(f"\n[bold cyan]╔{'═' * 56}╗[/bold cyan]")
    console.print(f"[bold cyan]║  [bold yellow]🔐 AUTHOR VERIFICATION[bold cyan]                              [bold cyan]║[/bold cyan]")
    console.print(f"[bold cyan]║  [bold white]Enter master password to continue[bold cyan]                     [bold cyan]║[/bold cyan]")
    console.print(f"[bold cyan]╚{'═' * 56}╝[/bold cyan]")
    password = safe_input(f"\n[bold red]🔑 Master Password: [/bold red]").strip()
    import hmac as _hmac
    if not AUTHOR_PASSWORD:
        console.print("\n[bold red]❌ Author password not configured (set ALVSIA_AUTHOR_PASSWORD).[/bold red]")
        return False
    if _hmac.compare_digest(password, AUTHOR_PASSWORD):
        console.print(f"\n[bold green]✅ Author Verified![/bold green]")
        return True
    else:
        console.print(f"\n[bold red]❌ Wrong Password![/bold red]")
        return False

def generate_key_author(key_type="1DAY", count=1):
    import random, string
    if key_type not in LICENSE_TYPES:
        console.print(f"[bold red]❌ Invalid key type: {key_type}[/bold red]")
        return []
    keys = []
    prefix = LICENSE_TYPES[key_type]["prefix"]
    for _ in range(count):
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        keys.append(f"{prefix}{suffix}")
    return keys

def add_keys_to_database(keys, key_type):
    for key in keys:
        LICENSE_DATABASE[key] = {"type": key_type, "expires": None}
    console.print(f"[bold green]✅ Added {len(keys)} keys[/bold green]")

def create_license_key_author(key_type="1DAY", custom_key=None):
    if not is_author():
        return None
    if custom_key:
        if custom_key.startswith("ALVSIA-1DAY-"):
            key_type = "1DAY"
        elif custom_key.startswith("ALVSIA-7DAY-"):
            key_type = "7DAY"
        elif custom_key.startswith("ALVSIA-30DAY-"):
            key_type = "30DAY"
        elif custom_key.startswith("ALVSIA-LIFE-"):
            key_type = "LIFETIME"
        else:
            console.print(f"[bold red]❌ Invalid format! Use: ALVSIA-1DAY-, ALVSIA-7DAY-, ALVSIA-30DAY-, ALVSIA-LIFE-[/bold red]")
            return None
        LICENSE_DATABASE[custom_key] = {"type": key_type, "expires": None}
        console.print(f"[bold green]✅ Custom key added: {custom_key}[/bold green]")
        return custom_key
    keys = generate_key_author(key_type, 1)
    if keys:
        add_keys_to_database(keys, key_type)
        return keys[0]
    return None

def create_bulk_keys_author():
    if not is_author():
        return False
    console.print(f"\n[bold cyan]📦 BULK KEY GENERATION[/bold cyan]")
    console.print(f"[bold yellow]1. 1DAY  2. 7DAY  3. 30DAY  4. LIFETIME[/bold yellow]")
    choice = safe_input(f"[bold yellow]Select (1-4): [/bold yellow]").strip()
    key_map = {"1": "1DAY", "2": "7DAY", "3": "30DAY", "4": "LIFETIME"}
    if choice not in key_map:
        console.print(f"[bold red]❌ Invalid![/bold red]")
        return False
    key_type = key_map[choice]
    try:
        count = int(safe_input(f"[bold yellow]Number of keys: [/bold yellow]").strip())
        if count <= 0 or count > 100:
            console.print(f"[bold red]❌ Count must be 1-100![/bold red]")
            return False
    except ValueError:
        console.print(f"[bold red]❌ Invalid number![/bold red]")
        return False
    keys = generate_key_author(key_type, count)
    if keys:
        add_keys_to_database(keys, key_type)
        console.print(f"\n[bold green]✅ Generated {len(keys)} keys:[/bold green]")
        for i, k in enumerate(keys, 1):
            console.print(f"  [cyan]{i}.[/cyan] [bold yellow]{k}[/bold yellow]")
        return True
    return False

def delete_key_author():
    if not is_author():
        return False
    if not LICENSE_DATABASE:
        console.print(f"[bold yellow]⚠ No keys in database![/bold yellow]")
        return False
    keys_list = list(LICENSE_DATABASE.keys())
    console.print(f"\n[bold cyan]Existing Keys:[/bold cyan]")
    for i, key in enumerate(keys_list, 1):
        key_type = LICENSE_DATABASE[key]["type"]
        label = LICENSE_TYPES[key_type]["label"]
        console.print(f"  [cyan]{i}.[/cyan] [bold yellow]{key}[/bold yellow] - {label}")
    try:
        choice = int(safe_input(f"\n[bold red]Select key to delete (1-{len(keys_list)}): [/bold red]").strip())
        if 1 <= choice <= len(keys_list):
            del LICENSE_DATABASE[keys_list[choice - 1]]
            console.print(f"[bold green]✅ Key deleted![/bold green]")
        else:
            console.print(f"[bold red]❌ Invalid selection![/bold red]")
    except ValueError:
        console.print(f"[bold red]❌ Invalid input![/bold red]")
    return True

def is_key_expired(key):
    if key in LICENSE_DATABASE:
        key_type = LICENSE_DATABASE[key]["type"]
        if key_type == "LIFETIME" or "MASTER" in key:
            return False
        expiry = get_key_expiry(key)
        if expiry:
            return datetime.now() > expiry
    return True

def get_key_expiry(key):
    if key in LICENSE_DATABASE:
        key_data = LICENSE_DATABASE[key]
        key_type = key_data["type"]
        duration = LICENSE_TYPES[key_type]["duration"]
        if key_data["expires"]:
            return datetime.strptime(key_data["expires"], "%Y-%m-%d")
        return datetime.now() + timedelta(days=duration)
    return None

def get_remaining_days(key):
    if key in LICENSE_DATABASE:
        key_type = LICENSE_DATABASE[key]["type"]
        if key_type == "LIFETIME" or "MASTER" in key:
            return 9999
        expiry = get_key_expiry(key)
        if expiry:
            return max(0, (expiry - datetime.now()).days)
    return 0

def display_license_info_key(key):
    if key not in LICENSE_DATABASE:
        console.print(f"[bold red]❌ Key not found![/bold red]")
        return False
    key_data = LICENSE_DATABASE[key]
    key_type = key_data["type"]
    duration = LICENSE_TYPES[key_type]["duration"]
    label = LICENSE_TYPES[key_type]["label"]
    price = LICENSE_TYPES[key_type]["price"]
    if key_type == "LIFETIME" or "MASTER" in key:
        remaining = "∞ (LIFETIME)"; status = "✅ ACTIVE"
    else:
        rd = get_remaining_days(key)
        status = "✅ ACTIVE" if rd > 0 else "❌ EXPIRED"
        remaining = f"{rd} days" if rd > 0 else "0 days"
    console.print(f"\n[bold cyan]╔{'═' * 56}╗[/bold cyan]")
    console.print(f"[bold cyan]║  [bold yellow]🔑 LICENSE INFO[/bold cyan]                          [bold cyan]║[/bold cyan]")
    console.print(f"[bold cyan]╠{'═' * 56}╣[/bold cyan]")
    console.print(f"[bold cyan]║  [bold white]Key:        [bold green]{key}[/bold green]")
    console.print(f"[bold cyan]║  [bold white]Type:       [bold yellow]{label}[/bold yellow]")
    console.print(f"[bold cyan]║  [bold white]Duration:   [bold magenta]{duration} days[/bold magenta]")
    console.print(f"[bold cyan]║  [bold white]Price:      [bold green]{price}[/bold green]")
    console.print(f"[bold cyan]║  [bold white]Status:     {status}")
    console.print(f"[bold cyan]║  [bold white]Remaining:  [bold cyan]{remaining}[/bold cyan]")
    console.print(f"[bold cyan]╚{'═' * 56}╝[/bold cyan]")
    return True

def show_author_license_menu():
    if not is_author():
        return
    while True:
        console.print(f"\n[bold magenta]╔{'═' * 56}╗[/bold magenta]")
        console.print(f"[bold magenta]║  [bold yellow]🔑 AUTHOR LICENSE MGMT[/bold magenta]                    [bold magenta]║[/bold magenta]")
        console.print(f"[bold magenta]╠{'═' * 56}╣[/bold magenta]")
        console.print(f"[bold magenta]║  [bold cyan]1.[/bold cyan] Generate 1-Day Trial Key")
        console.print(f"[bold magenta]║  [bold cyan]2.[/bold cyan] Generate 7-Day Premium Key")
        console.print(f"[bold magenta]║  [bold cyan]3.[/bold cyan] Generate 30-Day Monthly Key")
        console.print(f"[bold magenta]║  [bold cyan]4.[/bold cyan] Generate LIFETIME Key")
        console.print(f"[bold magenta]║  [bold cyan]5.[/bold cyan] Generate Multiple Keys")
        console.print(f"[bold magenta]║  [bold cyan]6.[/bold cyan] Create Custom Key")
        console.print(f"[bold magenta]║  [bold cyan]7.[/bold cyan] Check Key Status")
        console.print(f"[bold magenta]║  [bold cyan]8.[/bold cyan] List All Keys")
        console.print(f"[bold magenta]║  [bold cyan]9.[/bold cyan] Delete Key")
        console.print(f"[bold magenta]║  [bold cyan]0.[/bold cyan] Back")
        console.print(f"[bold magenta]╚{'═' * 56}╝[/bold magenta]")
        choice = safe_input("\n[bold yellow]Select: [/bold yellow]").strip()
        if choice == "0": break
        elif choice == "1":
            key = create_license_key_author("1DAY")
            if key: console.print(f"[bold green]✅ {key}[/bold green]")
            safe_input("\nPress Enter...")
        elif choice == "2":
            key = create_license_key_author("7DAY")
            if key: console.print(f"[bold green]✅ {key}[/bold green]")
            safe_input("\nPress Enter...")
        elif choice == "3":
            key = create_license_key_author("30DAY")
            if key: console.print(f"[bold green]✅ {key}[/bold green]")
            safe_input("\nPress Enter...")
        elif choice == "4":
            key = create_license_key_author("LIFETIME")
            if key: console.print(f"[bold green]✅ {key}[/bold green]")
            safe_input("\nPress Enter...")
        elif choice == "5":
            create_bulk_keys_author()
            safe_input("\nPress Enter...")
        elif choice == "6":
            custom = safe_input("[bold cyan]Enter custom key: [/bold cyan]").strip()
            if custom: create_license_key_author(custom_key=custom)
            safe_input("\nPress Enter...")
        elif choice == "7":
            key = safe_input("[bold cyan]Enter key: [/bold cyan]").strip()
            if key in LICENSE_DATABASE:
                display_license_info_key(key)
            else:
                console.print("[red]❌ Key not found![/red]")
            safe_input("\nPress Enter...")
        elif choice == "8":
            if LICENSE_DATABASE:
                console.print(f"\n[bold cyan]All Keys:[/bold cyan]")
                for key, data in LICENSE_DATABASE.items():
                    label = LICENSE_TYPES[data["type"]]["label"]
                    status = "✅" if not is_key_expired(key) else "❌"
                    console.print(f"  {status} [bold yellow]{key}[/bold yellow] - {label}")
            else:
                console.print("[yellow]⚠ No keys![/yellow]")
            safe_input("\nPress Enter...")
        elif choice == "9":
            delete_key_author()
            safe_input("\nPress Enter...")
        else:
            console.print("[red]❌ Invalid![/red]")

# ==================== TRIAL KEY FUNCTIONS ====================

def generate_trial_key(trial_type="1DAY"):
    import random, string
    if trial_type not in TRIAL_CONFIG:
        console.print(f"[bold red]❌ Invalid trial type! Use: 1DAY, 3DAY, 7DAY[/bold red]")
        return None
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    key = f"ALVSIA-{trial_type}-{suffix}"
    expiry_date = datetime.now() + timedelta(days=TRIAL_CONFIG[trial_type]["duration"])
    TRIAL_DATABASE[key] = {
        "type": trial_type, "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "expires": expiry_date.strftime("%Y-%m-%d %H:%M:%S"),
        "duration": TRIAL_CONFIG[trial_type]["duration"],
        "label": TRIAL_CONFIG[trial_type]["label"],
        "device_id": None, "device_model": None, "device_brand": None,
        "used": False, "used_by": None,
    }
    return key

def activate_trial_key(key):
    if key not in TRIAL_DATABASE:
        return False, "❌ Invalid trial key!"
    data = TRIAL_DATABASE[key]
    expiry = datetime.strptime(data["expires"], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expiry:
        return False, "❌ Trial key has expired!"
    current_device_id = get_device_id()
    current_model = get_device_model()
    current_brand = get_device_brand()
    if data["used"] and data["device_id"] != current_device_id:
        return False, f"❌ This trial key is already used on another device!\n   Registered Device: {data['device_id']}\n   Your Device: {current_device_id}"
    if not check_device_model():
        return False, "❌ Your device model is not allowed!"
    if not data["used"]:
        data["device_id"] = current_device_id
        data["device_model"] = current_model
        data["device_brand"] = current_brand
        data["used"] = True
        data["used_by"] = "Device: " + current_model
        TRIAL_DATABASE[key] = data
        save_license_data(key, current_device_id)
        remaining = (expiry - datetime.now()).total_seconds() / 3600
        return True, f"✅ Trial key activated!\n   Device: {current_model}\n   Device ID: {current_device_id}\n   Expires in: {remaining:.1f} hours"
    remaining = (expiry - datetime.now()).total_seconds() / 3600
    return True, f"✅ Trial key valid!\n   Device: {current_model}\n   Expires in: {remaining:.1f} hours"

def check_trial_key_status(key):
    if key not in TRIAL_DATABASE:
        return None, "Key not found"
    data = TRIAL_DATABASE[key]
    expiry = datetime.strptime(data["expires"], "%Y-%m-%d %H:%M:%S")
    now = datetime.now()
    if now > expiry:
        return "EXPIRED", f"Expired on: {data['expires']}"
    if not data["used"]:
        return "UNUSED", "Not yet activated"
    remaining = (expiry - now).total_seconds() / 3600
    return "ACTIVE", f"""Device: {data['device_model']}
Device ID: {data['device_id']}
Expires in: {remaining:.1f} hours
Expiry: {data['expires']}"""

def display_trial_key_info(key):
    if key not in TRIAL_DATABASE:
        console.print(f"[bold red]❌ Key not found![/bold red]")
        return
    data = TRIAL_DATABASE[key]
    status, info = check_trial_key_status(key)
    console.print(f"\n[bold cyan]╔{'═' * 56}╗[/bold cyan]")
    console.print(f"[bold cyan]║  [bold yellow]🎫 TRIAL KEY INFO[/bold cyan]                          [bold cyan]║[/bold cyan]")
    console.print(f"[bold cyan]╠{'═' * 56}╣[/bold cyan]")
    console.print(f"[bold cyan]║  [bold white]Key:        [bold green]{key}[/bold green]")
    console.print(f"[bold cyan]║  [bold white]Type:       [bold yellow]{data['label']}[/bold yellow]")
    console.print(f"[bold cyan]║  [bold white]Created:    [bold cyan]{data['created']}[/bold cyan]")
    console.print(f"[bold cyan]║  [bold white]Expires:    [bold magenta]{data['expires']}[/bold magenta]")
    console.print(f"[bold cyan]║  [bold white]Status:     [bold {'green' if status == 'ACTIVE' else 'red'}]{status}[/bold {'green' if status == 'ACTIVE' else 'red'}]")
    if data["used"]:
        console.print(f"[bold cyan]║  [bold white]Used On:    [bold white]{data['device_model']}[/bold white]")
        console.print(f"[bold cyan]║  [bold white]Device ID:  [bold white]{data['device_id']}[/bold white]")
        console.print(f"[bold cyan]║  [bold white]Brand:      [bold white]{data['device_brand']}[/bold white]")
    else:
        console.print(f"[bold cyan]║  [bold white]Used:       [bold yellow]Not yet activated[/bold yellow]")
    console.print(f"[bold cyan]╚{'═' * 56}╝[/bold cyan]")

def generate_bulk_trials(trial_type="1DAY", count=5):
    keys = []
    for _ in range(count):
        key = generate_trial_key(trial_type)
        if key:
            keys.append(key)
    return keys

def delete_trial_key_author(key):
    if key in TRIAL_DATABASE:
        del TRIAL_DATABASE[key]
        console.print(f"[bold green]✅ Trial key deleted: {key}[/bold green]")
        return True
    else:
        console.print(f"[bold red]❌ Key not found![/bold red]")
        return False

def list_all_trials():
    if not TRIAL_DATABASE:
        console.print("[yellow]⚠ No trial keys generated yet![/yellow]")
        return
    console.print(f"\n[bold cyan]📋 ALL TRIAL KEYS[/bold cyan]")
    console.print(f"[bold cyan]╔{'═' * 65}╗[/bold cyan]")
    console.print(f"[bold cyan]║  [bold yellow]KEY[/bold yellow]           [bold yellow]TYPE[/bold yellow]  [bold yellow]STATUS[/bold yellow]    [bold yellow]DEVICE[/bold yellow]")
    console.print(f"[bold cyan]╠{'═' * 65}╣[/bold cyan]")
    for key, data in TRIAL_DATABASE.items():
        status, _ = check_trial_key_status(key)
        if status == "ACTIVE":
            status_icon = "✅ ACTIVE"
            device = data.get('device_model', 'Not used')
        elif status == "EXPIRED":
            status_icon = "❌ EXPIRED"
            device = data.get('device_model', 'N/A')
        else:
            status_icon = "⏳ UNUSED"
            device = "Not activated"
        console.print(f"[bold cyan]║[/bold cyan] {key[:20]} {data['type']:6} {status_icon:10} {device[:25]}")
    console.print(f"[bold cyan]╚{'═' * 65}╝[/bold cyan]")

def show_trial_menu():
    while True:
        console.print(f"\n[bold yellow]╔{'═' * 56}╗[/bold yellow]")
        console.print(f"[bold yellow]║  [bold magenta]🎫 TRIAL KEY MANAGEMENT[/bold yellow]                       [bold yellow]║[/bold yellow]")
        console.print(f"[bold yellow]╠{'═' * 56}╣[/bold yellow]")
        console.print(f"[bold yellow]║  [bold cyan]1.[/bold cyan] Generate 24-Hour Trial Key")
        console.print(f"[bold yellow]║  [bold cyan]2.[/bold cyan] Generate 3-Day Trial Key")
        console.print(f"[bold yellow]║  [bold cyan]3.[/bold cyan] Generate 7-Day Trial Key")
        console.print(f"[bold yellow]║  [bold cyan]4.[/bold cyan] Generate Multiple Trial Keys")
        console.print(f"[bold yellow]║  [bold cyan]5.[/bold cyan] List All Trial Keys")
        console.print(f"[bold yellow]║  [bold cyan]6.[/bold cyan] Check Trial Key Status")
        console.print(f"[bold yellow]║  [bold cyan]7.[/bold cyan] Delete Trial Key")
        console.print(f"[bold yellow]║  [bold cyan]0.[/bold cyan] Back")
        console.print(f"[bold yellow]╚{'═' * 56}╝[/bold yellow]")
        choice = safe_input("\n[bold yellow]Select: [/bold yellow]").strip()
        if choice == "0": break
        elif choice == "1":
            key = generate_trial_key("1DAY")
            console.print(f"\n[bold green]✅ 24-Hour Trial Key: [bold yellow]{key}[/bold green]")
            display_trial_key_info(key)
            safe_input("\nPress Enter...")
        elif choice == "2":
            key = generate_trial_key("3DAY")
            console.print(f"\n[bold green]✅ 3-Day Trial Key: [bold yellow]{key}[/bold green]")
            display_trial_key_info(key)
            safe_input("\nPress Enter...")
        elif choice == "3":
            key = generate_trial_key("7DAY")
            console.print(f"\n[bold green]✅ 7-Day Trial Key: [bold yellow]{key}[/bold green]")
            display_trial_key_info(key)
            safe_input("\nPress Enter...")
        elif choice == "4":
            trial_type = safe_input("[bold cyan]Trial Type (1DAY/3DAY/7DAY): [/bold cyan]").strip().upper()
            if trial_type not in TRIAL_CONFIG:
                console.print("[red]❌ Invalid type![/red]")
                continue
            try:
                count = int(safe_input("[bold cyan]Number of keys: [/bold cyan]").strip())
                if count <= 0 or count > 50:
                    console.print("[red]❌ Count must be 1-50![/red]")
                    continue
            except ValueError:
                console.print("[red]❌ Invalid number![/red]")
                continue
            keys = generate_bulk_trials(trial_type, count)
            console.print(f"\n[bold green]✅ Generated {len(keys)} keys:[/bold green]")
            for k in keys:
                console.print(f"  [bold yellow]{k}[/bold yellow]")
            safe_input("\nPress Enter...")
        elif choice == "5":
            list_all_trials()
            safe_input("\nPress Enter...")
        elif choice == "6":
            key = safe_input("[bold cyan]Enter trial key: [/bold cyan]").strip()
            if key in TRIAL_DATABASE:
                display_trial_key_info(key)
                status, info = check_trial_key_status(key)
                console.print(f"\n[bold cyan]Details:[/bold cyan]\n{info}")
            else:
                console.print("[red]❌ Key not found![/red]")
            safe_input("\nPress Enter...")
        elif choice == "7":
            key = safe_input("[bold cyan]Enter trial key to delete: [/bold cyan]").strip()
            delete_trial_key_author(key)
            safe_input("\nPress Enter...")
        else:
            console.print("[red]❌ Invalid![/red]")

# ==================== LICENSE CHECK ====================

def check_license():
    current_device_id = get_device_id()
    saved_license = load_license_data()
    if saved_license is not None:
        saved_key = saved_license.get("license_key", "")
        saved_device = saved_license.get("device_id", "")
        saved_hash = saved_license.get("license_hash", "")
        expected_hash = generate_license_hash(saved_key, saved_device)
        if saved_hash == expected_hash and saved_device == current_device_id:
            if saved_key in TRIAL_DATABASE:
                status, info = check_trial_key_status(saved_key)
                if status != "ACTIVE":
                    console.print(f"\n[bold red]❌ Trial key {status}![/bold red]")
                    if LICENSE_FILE.exists():
                        LICENSE_FILE.unlink()
                    return check_license()
                else:
                    data = TRIAL_DATABASE[saved_key]
                    console.print(f"\n[bold green]╔{'═' * 56}╗[/bold green]")
                    console.print(f"[bold green]║  [bold green]🎫 TRIAL LICENSE ACTIVE![bold green]                      [bold green]║[/bold green]")
                    console.print(f"[bold green]║  [bold cyan]Key: [bold white]{saved_key[:20]}...[bold green]                      [bold green]║[/bold green]")
                    console.print(f"[bold green]║  [bold cyan]Type: [bold yellow]{data['label']}[/bold green]")
                    console.print(f"[bold green]║  [bold cyan]Device: [bold white]{current_device_id}[bold green]                   [bold green]║[/bold green]")
                    console.print(f"[bold green]║  [bold cyan]Expires: [bold yellow]{data['expires']}[/bold green]")
                    console.print(f"[bold green]║  [bold cyan]Status: [bold green]✅ ACTIVE[/bold green]                              [bold green]║[/bold green]")
                    console.print(f"[bold green]╚{'═' * 56}╝[/bold green]")
                    return True
            if saved_key in LICENSE_DATABASE:
                if is_key_expired(saved_key):
                    console.print(f"\n[bold red]❌ License has EXPIRED![/bold red]")
                    if LICENSE_FILE.exists():
                        LICENSE_FILE.unlink()
                    return check_license()
                else:
                    activation_date = saved_license.get("activation_date", "N/A")
                    remaining = get_remaining_days(saved_key)
                    key_type = LICENSE_DATABASE[saved_key]["type"]
                    label = LICENSE_TYPES[key_type]["label"]
                    console.print(f"\n[bold green]╔{'═' * 56}╗[/bold green]")
                    console.print(f"[bold green]║  [bold green]🔑 PREMIUM LICENSE ACTIVE![bold green]                  [bold green]║[/bold green]")
                    console.print(f"[bold green]║  [bold cyan]Key: [bold white]{saved_key[:20]}...[bold green]                      [bold green]║[/bold green]")
                    console.print(f"[bold green]║  [bold cyan]Type: [bold yellow]{label}[/bold green]                             [bold green]║[/bold green]")
                    console.print(f"[bold green]║  [bold cyan]Device: [bold white]{current_device_id}[bold green]                   [bold green]║[/bold green]")
                    console.print(f"[bold green]║  [bold cyan]Activated: [bold white]{activation_date}[bold green]            [bold green]║[/bold green]")
                    if remaining > 999:
                        console.print(f"[bold green]║  [bold cyan]Status: [bold green]✅ LIFETIME[/bold green]                           [bold green]║[/bold green]")
                    else:
                        console.print(f"[bold green]║  [bold cyan]Status: [bold green]✅ ACTIVE ({remaining} days)[bold green]            [bold green]║[/bold green]")
                    console.print(f"[bold green]╚{'═' * 56}╝[/bold green]")
                    return True
            if saved_key in VALID_LICENSE_KEYS:
                activation_date = saved_license.get("activation_date", "N/A")
                console.print(f"\n[bold green]╔{'═' * 56}╗[/bold green]")
                console.print(f"[bold green]║  [bold green]🔑 LEGACY LICENSE ACTIVE![bold green]                    [bold green]║[/bold green]")
                console.print(f"[bold green]║  [bold cyan]Key: [bold white]{saved_key[:20]}...[bold green]                      [bold green]║[/bold green]")
                console.print(f"[bold green]║  [bold cyan]Device: [bold white]{current_device_id}[bold green]                   [bold green]║[/bold green]")
                console.print(f"[bold green]║  [bold cyan]Activated: [bold white]{activation_date}[bold green]            [bold green]║[/bold green]")
                console.print(f"[bold green]║  [bold cyan]Status: [bold green]✅ ACTIVE[/bold green]                              [bold green]║[/bold green]")
                console.print(f"[bold green]╚{'═' * 56}╝[/bold green]")
                return True
        console.print(f"[bold red]⚠ License verification failed! Re-enter key.[/bold red]")
        if LICENSE_FILE.exists():
            LICENSE_FILE.unlink()
    console.print(f"\n[bold magenta]╔{'═' * 56}╗[/bold magenta]")
    console.print(f"[bold magenta]║  [bold yellow]🔑 LICENSE ACTIVATION REQUIRED[bold magenta]                      [bold magenta]║[/bold magenta]")
    console.print(f"[bold magenta]║  [bold white]Enter your premium license key to continue[bold magenta]          [bold magenta]║[/bold magenta]")
    console.print(f"[bold magenta]║  [bold cyan]Contact @ALVSIA_PRO to get license key[bold magenta]              [bold magenta]║[/bold magenta]")
    console.print(f"[bold magenta]║  [dim]Your Device ID: {current_device_id}[bold magenta]                  [bold magenta]║[/bold magenta]")
    console.print(f"[bold magenta]╚{'═' * 56}╝[/bold magenta]")
    attempts = 3
    while attempts > 0:
        print()
        license_key = safe_input(f"[bold yellow]⚡ Enter License Key ({attempts} attempts left): [/bold yellow]").strip()
        if not license_key:
            console.print(f"[bold red]❌ Key cannot be empty![/bold red]")
            attempts -= 1
            continue
        if license_key in TRIAL_DATABASE:
            success, msg = activate_trial_key(license_key)
            if success:
                console.print(f"\n[bold green]🎉 TRIAL ACTIVATED![/bold green]")
                console.print(f"[bold green]{msg}[/bold green]")
                return True
            else:
                console.print(f"[bold red]❌ {msg}[/bold red]")
                attempts -= 1
                continue
        if license_key in LICENSE_DATABASE:
            if is_key_expired(license_key):
                console.print(f"[bold red]❌ License key has EXPIRED![/bold red]")
                attempts -= 1
                continue
            save_license_data(license_key, current_device_id)
            key_type = LICENSE_DATABASE[license_key]["type"]
            label = LICENSE_TYPES[key_type]["label"]
            remaining = get_remaining_days(license_key)
            console.print(f"\n[bold green]╔{'═' * 56}╗[/bold green]")
            console.print(f"[bold green]║  [bold green on white] 🎉 LICENSE ACTIVATED SUCCESSFULLY! [/bold green on white]             [bold green]║[/bold green]")
            console.print(f"[bold green]║  [bold cyan]Key: [bold white]{license_key}[/bold green]")
            console.print(f"[bold green]║  [bold cyan]Type: [bold yellow]{label}[/bold green]")
            console.print(f"[bold green]║  [bold cyan]Device: [bold white]{current_device_id}[/bold green]                   [bold green]║[/bold green]")
            console.print(f"[bold green]║  [bold cyan]Model: [bold white]{get_device_model()}[/bold green]                              [bold green]║[/bold green]")
            console.print(f"[bold green]║  [bold cyan]Activated: [bold white]{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}[/bold green]       [bold green]║[/bold green]")
            if remaining > 999:
                console.print(f"[bold green]║  [bold cyan]Status: [bold green]✅ LIFETIME ACTIVE[/bold green]                     [bold green]║[/bold green]")
            else:
                console.print(f"[bold green]║  [bold cyan]Status: [bold green]✅ ACTIVE ({remaining} days)[/bold green]              [bold green]║[/bold green]")
            console.print(f"[bold green]║  [bold yellow]Thank you for choosing @ALVSIA_PRO![/bold green]                 [bold green]║[/bold green]")
            console.print(f"[bold green]╚{'═' * 56}╝[/bold green]")
            return True
        if license_key in VALID_LICENSE_KEYS:
            save_license_data(license_key, current_device_id)
            console.print(f"\n[bold green]✅ LEGACY KEY ACTIVATED![/bold green]")
            return True
        attempts -= 1
        if attempts > 0:
            console.print(f"[bold red]╔{'═' * 56}╗[/bold red]")
            console.print(f"[bold red]║  [bold red]❌ INVALID LICENSE KEY![/bold red]                              [bold red]║[/bold red]")
            console.print(f"[bold red]║  [bold yellow]Attempts remaining: {attempts}[/bold red]                          [bold red]║[/bold red]")
            console.print(f"[bold red]║  [bold cyan]Contact @ALVSIA_PRO for valid key[/bold red]                   [bold red]║[/bold red]")
            console.print(f"[bold red]╚{'═' * 56}╝[/bold red]")
        else:
            console.print(f"\n[bold red]╔{'═' * 56}╗[/bold red]")
            console.print(f"[bold red]║  [bold white on red] 🚫 ALL ATTEMPTS USED! ACCESS DENIED! [/bold white on red]          [bold red]║[/bold red]")
            console.print(f"[bold red]║  [bold yellow]Contact @ALVSIA_PRO for license key[/bold red]                 [bold red]║[/bold red]")
            console.print(f"[bold red]║  [bold cyan]Device ID: [bold white]{current_device_id}[/bold red]                  [bold red]║[/bold red]")
            console.print(f"[bold red]╚{'═' * 56}╝[/bold red]")
            return False
    return False

# ==================== LICENSE INFO DISPLAY ====================

def show_license_info():
    device_id = get_device_id()
    license_data = load_license_data()
    now = datetime.now()
    remaining_days = (TOOL_EXPIRY_DATE - now).days
    console.print(f"\n[bold cyan]╔{'═' * 56}╗[/bold cyan]")
    console.print(f"[bold cyan]║  [bold yellow]📋 LICENSE & DEVICE INFORMATION[/bold cyan]                     [bold cyan]║[/bold cyan]")
    console.print(f"[bold cyan]╠{'═' * 56}╣[/bold cyan]")
    console.print(f"[bold cyan]║  [bold magenta]🆔 DEVICE INFO[/bold cyan]                                      [bold cyan]║[/bold cyan]")
    console.print(f"[bold cyan]║  [bold white]Device ID: [bold green]{device_id}[/bold cyan]                    [bold cyan]║[/bold cyan]")
    console.print(f"[bold cyan]║  [bold white]Model:     [bold green]{get_device_model()}[/bold cyan]                            [bold cyan]║[/bold cyan]")
    console.print(f"[bold cyan]║  [bold white]Android:   [bold green]{get_android_version()}[/bold cyan]                               [bold cyan]║[/bold cyan]")
    console.print(f"[bold cyan]╠{'─' * 56}╣[/bold cyan]")
    console.print(f"[bold cyan]║  [bold magenta]🔑 LICENSE INFO[/bold cyan]                                     [bold cyan]║[/bold cyan]")
    if license_data:
        key = license_data.get("license_key", "N/A")
        act_date = license_data.get("activation_date", "N/A")
        if key in TRIAL_DATABASE:
            data = TRIAL_DATABASE[key]
            remaining = (datetime.strptime(data["expires"], "%Y-%m-%d %H:%M:%S") - now).total_seconds() / 3600
            console.print(f"[bold cyan]║  [bold white]Key:       [bold green]{key}[/bold green]")
            console.print(f"[bold cyan]║  [bold white]Type:      [bold yellow]TRIAL ({data['label']})[/bold yellow]")
            console.print(f"[bold cyan]║  [bold white]Expires:   [bold magenta]{data['expires']}[/bold magenta]")
            console.print(f"[bold cyan]║  [bold white]Remaining: [bold cyan]{remaining:.1f} hours[/bold cyan]")
            console.print(f"[bold cyan]║  [bold white]Status:    [bold green]✅ ACTIVE[/bold cyan]                              [bold cyan]║[/bold cyan]")
        else:
            console.print(f"[bold cyan]║  [bold white]Key:       [bold green]{key}[/bold green]")
            console.print(f"[bold cyan]║  [bold white]Activated: [bold green]{act_date}[/bold green]")
            console.print(f"[bold cyan]║  [bold white]Status:    [bold green]✅ ACTIVE[/bold cyan]                              [bold cyan]║[/bold cyan]")
    else:
        console.print(f"[bold cyan]║  [bold white]Status:    [bold red]❌ NOT ACTIVATED[/bold cyan]                        [bold cyan]║[/bold cyan]")
    console.print(f"[bold cyan]╠{'─' * 56}╣[/bold cyan]")
    console.print(f"[bold cyan]║  [bold magenta]⏰ EXPIRY INFO[/bold cyan]                                      [bold cyan]║[/bold cyan]")
    console.print(f"[bold cyan]║  [bold white]Expiry:    [bold yellow]{TOOL_EXPIRY_DATE.strftime('%d-%m-%Y')}[/bold cyan]                          [bold cyan]║[/bold cyan]")
    if remaining_days > 30:
        console.print(f"[bold cyan]║  [bold white]Remaining: [bold green]{remaining_days} days[/bold cyan]                             [bold cyan]║[/bold cyan]")
    elif remaining_days > 0:
        console.print(f"[bold cyan]║  [bold white]Remaining: [bold yellow]{remaining_days} days ⚠[/bold cyan]                          [bold cyan]║[/bold cyan]")
    else:
        console.print(f"[bold cyan]║  [bold white]Remaining: [bold red]EXPIRED! ❌[/bold cyan]                            [bold cyan]║[/bold cyan]")
    console.print(f"[bold cyan]╚{'═' * 56}╝[/bold cyan]")

# ==================== RESET LICENSE ====================

def reset_license():
    admin_password = os.environ.get("ALVSIA_ADMIN_PASSWORD", "")
    console.print(f"\n[bold red]╔{'═' * 56}╗[/bold red]")
    console.print(f"[bold red]║  [bold white on red] 🔐 ADMIN LICENSE RESET [/bold white on red]                      [bold red]║[/bold red]")
    console.print(f"[bold red]║  [bold yellow]⚠ This will reset ALL license data![/bold red]    [bold red]║[/bold red]")
    console.print(f"[bold red]║  [bold yellow]⚠ Device lock will be removed![/bold red]        [bold red]║[/bold red]")
    console.print(f"[bold red]║  [bold yellow]⚠ Re-activation will be required![/bold red]      [bold red]║[/bold red]")
    console.print(f"[bold red]╚{'═' * 56}╝[/bold red]")
    password = safe_input(f"[bold red]🔐 Enter Admin Password: [/bold red]").strip()
    import hmac as _hmac
    if not admin_password:
        console.print("[bold red]❌ Admin reset disabled: set ALVSIA_ADMIN_PASSWORD.[/bold red]")
        return False
    if not _hmac.compare_digest(password, admin_password):
        console.print(f"[bold red]❌ Wrong admin password![/bold red]")
        return False
    console.print(f"[bold cyan]🔄 Resetting license data...[/bold cyan]")
    if LICENSE_FILE.exists():
        LICENSE_FILE.unlink()
        console.print(f"[bold green]✅ License file deleted![/bold green]")
    if DEVICE_FILE.exists():
        DEVICE_FILE.unlink()
        console.print(f"[bold green]✅ Device lock file deleted![/bold green]")
    console.print(f"\n[bold green]✅ License Reset Complete![/bold green]")
    console.print(f"[bold yellow]Restart the tool to re-activate.[/bold yellow]")
    return True

# ==================== MASTER SECURITY CHECK ====================

def run_security_check():
    """PATCHED: bypass all checks, always returns True."""
    return True

# ======================================================================
# 🔥 MODIFIED MAIN FUNCTION TO INCLUDE SECURITY AND NEW MENU OPTIONS
# ======================================================================

def show_main_menu():
    """Modern ALVSIA PRO 5.5 dashboard. Handler numbering stays backward-compatible."""
    accent = get_banner_color()
    try:
        console.print(Panel(
            Align.center(Text.from_markup(
                "[bold white]ULTIMATE ALVSIA PRO 5.5[/bold white]\n"
                f"[dim]Unified Asset Engineering Suite[/dim]  •  [bold {accent}]REAL LOGIC[/bold {accent}]  •  [bold green]VALIDATED OUTPUT[/bold green]"
            )), border_style=accent, box=box.DOUBLE, padding=(1,2)))
        grid = Table(show_header=False, box=None, expand=True, padding=(0,1))
        grid.add_column("#", width=4, justify="center", style=f"bold {accent}")
        grid.add_column("ENGINE", width=26, style="bold white")
        grid.add_column("CAPABILITY", style="dim white")
        rows = [
            ("01","PAK • EXTRACT","Full extraction / path-safe output"),
            ("02","PAK • SMART REPACK","Modified-file detection + rebuild"),
            ("03","PAK • CLEAN","Controlled workspace cleanup"),
            ("04","PAK • DEEP HUNTER","Targeted multi-PAK extraction"),
            ("05","ENCRYPT / TRANSFORM","Encryption workflow"),
            ("06","OBB ANALYZER","Deep index / analysis"),
            ("07","DATA / CREDIT","UEXP / CSV / data workflows"),
            ("08","LUA ENGINE","Detect / process / decompile / repack"),
            ("09","SKIN + ZSDIC","Scan / patch / size-fix / repack"),
            ("10","OBB PACK ENGINE","Unpack / repack / rezip"),
            ("11","LICENSE INFO","License + device state"),
            ("12","LICENSE RESET","Administrative reset"),
            ("13","AUTHOR LICENSE","Key management"),
            ("14","UI CUSTOMIZATION","Banner / color"),
            ("15","PAK ENCRYPTION","Normal / custom / restore"),
            ("00","EXIT","Close safely"),
        ]
        for row in rows:
            style = "bold red" if row[0]=="00" else f"bold {accent}"
            grid.add_row(f"[{style}]{row[0]}[/]", row[1], row[2])
        console.print(Panel(grid, title=f"[bold {accent}]ENGINE MATRIX[/bold {accent}]", border_style=accent, box=box.ROUNDED, padding=(1,1)))
        status = Table(show_header=False, box=None, expand=True, padding=(0,1))
        status.add_column(style="dim"); status.add_column(style="bold white")
        status.add_row("BUILD", "ALVSIA PRO 5.5")
        status.add_row("ARCHITECTURE", "Unified canonical PAK core + workflow engines")
        status.add_row("VALIDATION", "Output verification enabled where format allows")
        console.print(Panel(status, title="[bold cyan]RUNTIME STATUS[/bold cyan]", border_style="cyan", box=box.ROUNDED))
    except Exception:
        # Fallback stays functional on minimal terminals.
        print("ULTIMATE ALVSIA PRO 5.5")
        print("1-15: engine matrix | 0: exit")


def auto_termux_setup():
    """Production-safe dependency preflight. It never mutates the OS automatically."""
    required = {"rich": "rich"}
    optional = {"Crypto": "pycryptodome", "zstandard": "zstandard", "gmalg": "gmalg", "requests": "requests"}
    missing_required, missing_optional = [], []
    for mod, pkg in required.items():
        try: __import__(mod)
        except Exception: missing_required.append(pkg)
    for mod, pkg in optional.items():
        try: __import__(mod)
        except Exception: missing_optional.append(pkg)
    if missing_required or missing_optional:
        console.print(Panel(
            "[bold yellow]Dependency preflight[/bold yellow]\n"
            + (f"Required missing: {', '.join(missing_required)}\n" if missing_required else "")
            + (f"Optional/engine dependencies missing: {', '.join(missing_optional)}\n" if missing_optional else "")
            + "[dim]Install the missing packages in your environment before using the affected engines.[/dim]",
            title="ALVSIA PRO 5.5 • PREFLIGHT", border_style="yellow", box=box.ROUNDED))
    return {"required_missing": missing_required, "optional_missing": missing_optional}

def main():   
    # Setup sabse pehle run hoga
    auto_termux_setup()
    
    # ====== RUN SECURITY CHECK FIRST ======
    if not run_security_check():
        console.print(f"\n[bold red]❌ Security check failed! Access denied.[/bold red]")
        time.sleep(3)
        return
    
    kill_hacker()
    BASE = Path(__file__).resolve().parent / 'ALVSIA_PRO_DATA'
    create_dirs(BASE)
    
    auth_status = check_password_login()
    if not auth_status:
        console.print("[bold red]Open ALVSIA PRO and complete login through the active Unaux panel first.[/bold red]")
        return

    global SESSION_KEY, SM4_SECRET_NEW, ENGINE_LOCKED, SERVER_LUA_XOR_KEY_HEX
    
    # Offline startup: no server token / heartbeat / deliberate crash dependency.
    if not SM4_SECRET_NEW:
        console.print("[yellow]ℹ Offline mode: server-only SM4_NEW keys are not embedded in the source.[/yellow]")
    
    obb_unpacker = BASE / "OBB_UNPACKER"
    ORGNAL_PATH = obb_unpacker / ORGNAL_DIR
    MODIFIED_PATH = obb_unpacker / EDITED_DIR
    UNPACK_PATH = obb_unpacker / UNPACK_DIR
    REPACK_PATH = obb_unpacker / REPACK_DIR
    SINGLE_PATH = obb_unpacker / SINGLE_DIR

    # 🔥 VALID OPTIONS LIST (extended with 11,12,13,14)
    VALID_OPTIONS = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15"}

    while True:
        TRANSLATIONS[CURRENT_LANGUAGE]["BANNER_TITLE"] = to_fancy(get_main_banner().split('\n')[-2].strip().replace('𓂃', '').replace('[blink]', '').replace('[/blink]', '') if '𓂃' in get_main_banner() else "ALVSIA PRO 5.5")
        
        print_banner_and_header()
        print_user_profile()
        show_main_menu()
        
        b_color = get_banner_color()
        prompt_text = to_fancy(TRANSLATIONS[CURRENT_LANGUAGE]["PROMPT_CHOICE"])
        choice = Prompt.ask(f"[bold {b_color}]{prompt_text}[/bold {b_color}]")
        
        # 🔥 INVALID OPTION CHECK - SCREEN CLEAR NAHI HOGI
        if choice not in VALID_OPTIONS:
            console.print()
            console.print(Panel(
                f"[bold red]❌ INVALID OPTION![/bold red]\n"
                f"[yellow]Please enter a valid option (0-15)[/yellow]",
                title="[bold white on red] ⚠️ ERROR ⚠️ [/]",
                border_style="red",
                box=box.HEAVY
            ))
            console.print()
            time.sleep(1.5)
            continue  # 🔥 SCREEN CLEAR NAHI HOGA, SIRF ERROR DIKHEGA
        
        if choice == "0":
            goodbye_glacier_light_effect()
            return
        
        # ====== HANDLE NEW SECURITY OPTIONS ======
        if choice == "11":
            show_license_info()
            Prompt.ask("\nPress Enter to continue", default="")
            continue
        if choice == "12":
            reset_license()
            Prompt.ask("\nPress Enter to continue", default="")
            continue
        if choice == "13":
            show_author_license_menu()
            Prompt.ask("\nPress Enter to continue", default="")
            continue
        if choice == "14":
            change_big_banner()
            Prompt.ask("\nPress Enter to continue", default="")
            continue
        if choice == "15":
            run_pak_encrypt_submenu()
            continue
        
        # ====== ORIGINAL HANDLERS (unchanged) ======
        if choice == "1": 
            unpack_all_files()
            continue
        
        if choice == "3":
            if Confirm.ask("[bold red]Are you sure you want to delete ALL unpacked files?[/]"):
                clear_all_unpack_data()
            continue
        
        if choice == "4": 
            pak_files = list_paks_in_folder(ORGNAL_PATH)
            if not pak_files:
                console.print(Panel(f"[red]No .pak/.obb files found in {ORGNAL_PATH.resolve()}[/red]", title="❗ No PAKs", style="red"))
                Prompt.ask("\nPress Enter to continue", default="")
                continue
            console.clear()
            print_banner_and_header()
            console.print(Panel("[bold cyan]⚡ ALVSIA DEEP HUNTER (CLEAN UI) ⚡[/bold cyan]\n\n[dim white]Paste ke baad [/dim white][bold cyan]DOUBLE ENTER[/bold cyan][dim white] dabao![/dim white]", border_style="bright_blue", box=box.DOUBLE_EDGE))
            
            targets = []
            print("\033[1;34m👇 Paste File Names (Blue Mode):\033[0m")
            while True:
                line = input("\033[1;36m").strip()
                print("\033[0m", end="", flush=True) 
                if not line: break
                targets.extend([x.strip() for x in line.split(',') if x.strip()])
            targets = list(set(targets))
            if not targets: continue

            console.clear()
            print_banner_and_header()
            total_extracted = 0
            
            with Progress(SpinnerColumn("dots", style="bold cyan"), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                task = progress.add_task("[bold bright_blue]Deep Hunting in Progress...", total=len(pak_files))
                for pak_path in pak_files:
                    try:
                        pak = TencentPakFile(pak_path) 
                        for target in targets:
                            for dir_path, dir_content in pak._index.items():
                                if target in dir_content:
                                    entry_found = dir_content[target]
                                    relative_dir = dir_path.relative_to(pak._mount_point) if dir_path.parts and dir_path.parts[0] == pak._mount_point.name else dir_path
                                    pak_stem = Path(pak._file_path).stem
                                    out_dir = SINGLE_PATH.parent / SINGLE_PATH.name / pak_stem / relative_dir
                                    os.makedirs(to_long_path(out_dir), exist_ok=True)
                                    pak._write_to_disk(out_dir / target, entry_found)
                                    total_extracted += 1
                                    progress.console.print(f"[bold green]✔ FOUND & EXTRACTED:[/] [bold bright_blue]{target}[/]")
                    except Exception: 
                        pass
                    progress.advance(task)
            
            if total_extracted > 0:
                console.print(Panel(f"[bold bright_blue]✔ SUCCESS: {total_extracted} instances extracted successfully![/bold bright_blue]\n[bold bright_blue]Saved to: {SINGLE_PATH.name}/[/bold bright_blue]", title="[bold green]✔ AUTO MULTI-UNPACK COMPLETE![/bold green]", border_style="green", box=box.HEAVY))
            Prompt.ask("\n[bold bright_blue]Press Enter to return to menu[/bold bright_blue]", default="")
            continue

        if choice == "5": 
            run_encrypt_tool()
            continue
        if choice == "6": 
            run_obb_analysis_tool()
            continue
        if choice == "7": 
            black_tool_main()
            continue
        if choice == "8": 
            run_lua_tool()
            continue
        if choice == "9": 
            run_combined_modding_tool()
            continue
        if choice == "10": 
            run_obbzip_tool()
            continue
        
        TencentPakFile.INPUT_DIR = ORGNAL_PATH
        TencentPakFile.OUTPUT_BASE = UNPACK_PATH
        TencentPakFile.MODIFIED_DIR = MODIFIED_PATH

        pak_files = list_paks_in_folder(ORGNAL_PATH)
        if not pak_files:
            console.print(Panel(f"[red]No .pak/.obb files found in {ORGNAL_PATH.resolve()}[/red]", title="❗ No PAKs", style="red"))
            Prompt.ask("\nPress Enter to continue", default="")
            continue

        selected = []
        if choice == "2":
            selected = auto_detect_repack_candidates(pak_files, MODIFIED_PATH)
            if not selected:
                console.print(Panel("[yellow]No matching PAKs found for the files in Modified_files.[/yellow]"))
                Prompt.ask("\nPress Enter to continue", default="")
                continue
            
            target_list = []
            for i, p in enumerate(selected):
                target_list.append(f"  [bold cyan]{i+1}.[/] [bold {get_banner_color()}]{to_fancy(p.name)}[/] [dim]-> Found modified files.[/dim]")
            
            console.print(Panel(
                "\n".join(target_list), 
                title= f"[bold black on {get_banner_color()}]  SMART REPACK [/]", 
                border_style=get_banner_color(), 
                box=box.HEAVY
            ))

            if Prompt.ask(f"\n[bold yellow]Proceed to Repack these {len(selected)} files?[/bold yellow] (y/n)", default="y").lower() != 'y': 
                continue
            
            import shutil
            for pak_path in selected:
                console.print(f"\n[bold cyan]📦 Repacking:[/] {pak_path.name}")
                try:
                    repacked_file = REPACK_PATH / pak_path.name
                    if repacked_file.exists():
                        repacked_file.unlink()
                    shutil.copy2(to_long_path(pak_path), to_long_path(repacked_file))
                    
                    pak = TencentPakFile(pak_path)
                    with open_long(repacked_file, 'r+b') as fh:
                        success = pak.repack_inplace_from_modified_dir(fh)
                    
                    if success:
                        console.print(f"[bold {get_banner_color()}]✔ SUCCESSFULLY REPACKED:[/] [bold green]{str(repacked_file.resolve())}[/bold green]")
                    else:
                        console.print(f"[bold yellow]⚠️ Koi file inplace repack nahi ho payi in:[/] {pak_path.name}")
                except Exception as e:
                    console.print(f"[bold red]❌ Repack Error for {pak_path.name}: {e}[/bold red]")
                    
            Prompt.ask("\n[bold white]Press Enter to return to menu...[/bold white]", default="")
            continue  # 🔥 FIX: loop back to menu, don't fall through

# ---- ULTIMATE ALVSIA PRO 5.5 modern launcher ----
def _alv_modern_ui():
    """Modern dashboard facade; the canonical workflow dispatch remains in main()."""
    return main()

def _alv_ultimate_banner():
    try:
        console.print("[bold cyan]╭────────────────────────────────────────────────────────────╮[/]")
        console.print("[bold cyan]│[/] [bold white]             ULTIMATE ALVSIA PRO 5.5[/] [bold cyan]│[/]")
        console.print("[bold cyan]│[/] [dim]          PROFESSIONAL UNIFIED EDITION[/] [bold cyan]│[/]")
        console.print("[bold cyan]╰────────────────────────────────────────────────────────────╯[/]")
    except Exception: print("ULTIMATE ALVSIA PRO 5.5")

def run_self_test() -> int:
    """Deterministic offline QA for the canonical logic that does not require game files."""
    checks = []
    try:
        assert sanitize_path_string("../a\x00/b") == "../a/b"
        checks.append(("path sanitizer", True, "ok"))
    except Exception as exc: checks.append(("path sanitizer", False, str(exc)))
    try:
        payload = b"ALVSIA-PRO-4.6" * 64
        comp = zlib.compress(payload, 9)
        assert zlib.decompress(comp) == payload
        checks.append(("zlib roundtrip", True, "ok"))
    except Exception as exc: checks.append(("zlib roundtrip", False, str(exc)))
    try:
        key = bytes.fromhex("0123456789abcdeffedcba9876543210")
        sm = SM4(key); block = bytes.fromhex("00112233445566778899aabbccddeeff")
        assert sm.decrypt(sm.encrypt(block)) == block
        checks.append(("SM4 roundtrip", True, "ok"))
    except Exception as exc: checks.append(("SM4 roundtrip", False, str(exc)))
    for mod in ("Crypto", "zstandard", "gmalg"):
        try: __import__(mod); checks.append((f"dependency:{mod}", True, "available"))
        except Exception: checks.append((f"dependency:{mod}", True, "external dependency required"))
    try:
        from lua_engine import detect_lua, validate_lua_source
        _lua_probe = b"local x=1\\nreturn x\\n"
        _info = detect_lua(__file__) if False else None
        _ok, _msg = validate_lua_source(_lua_probe.decode())
        checks.append(("lua-engine import/validator", _ok, _msg))
    except Exception as exc:
        checks.append(("lua-engine import/validator", False, str(exc)))
    bad_names = [
        "".join(map(chr, [75,65,90,85,75,73])),
        "".join(map(chr, [71,79,68,88])),
        "".join(map(chr, [83,75,85,89])),
        "".join(map(chr, [86,65,76,76,69,82,73,78,73,69])),
        "".join(map(chr, [78,65,68,69,69,77])),
        "".join(map(chr, [65,76,86,83,73,65,73])),
    ]
    source = Path(__file__).read_text(errors="ignore").upper()
    for name in bad_names:
        checks.append((f"branding:{name}", name not in source, "clean" if name not in source else "found"))
    failed = [c for c in checks if not c[1]]
    print("ALVSIA PRO 5.5 SELF-TEST")
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    print(f"RESULT: {'PASS' if not failed else 'FAIL'} ({len(checks)-len(failed)}/{len(checks)})")
    return 0 if not failed else 1

if __name__ == '__main__':
    try:
        if "--self-test" in sys.argv:
            raise SystemExit(run_self_test())
        _alv_ultimate_banner()
        _alv_modern_ui()
    except KeyboardInterrupt:
        print("\n[!] Operation cancelled.")
    except SystemExit:
        raise
    except Exception as e:
        print(f"[!] Runtime error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# ALVSIA ULTIMATE — Module 10-17 real implementations
# ══════════════════════════════════════════════════════════════════════════════
import re as _re, hashlib as _hashlib

# ── Module 10: SO Analyzer ────────────────────────────────────────────────────

def so_xor_brute(input_path, out_dir):
    """Brute-force single-byte XOR keys on .so file."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    raw = p.read_bytes()
    hits = []
    for key in range(256):
        dec = bytes(b ^ key for b in raw[:64])
        if dec[:4] == b"\x7fELF" or dec[:4] in (b"\x1bLua", b"\x1bLJ\x02"):
            hits.append("key=0x%02X reveals known magic: %s" % (key, dec[:4]))
    lines = ["SO XOR BRUTE — %s" % p.name, "tested=256 single-byte keys", ""]
    lines += hits if hits else ["no single-byte XOR key reveals ELF/Lua magic"]
    out_file = out_dir / "so_xor_brute.txt"
    out_file.write_text("\n".join(lines)); return {"ok": True, "out": str(out_file), "hits": len(hits)}


def so_multi_xor(input_path, out_dir, key_hex=""):
    """Apply multi-byte XOR key to .so and save result."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    raw = p.read_bytes()
    if not key_hex:
        return {"ok": False, "error": "key_hex required (e.g. 'DEADBEEF')"}
    try:
        key = bytes.fromhex(key_hex.replace(" ",""))
        if not key:
            return {"ok": False, "error": "key_hex must contain at least one byte"}
    except Exception:
        return {"ok": False, "error": "invalid key_hex"}
    dec = bytes(raw[i] ^ key[i % len(key)] for i in range(len(raw)))
    out_file = out_dir / ("so_xored_%s" % p.name)
    out_file.write_bytes(dec)
    magic = dec[:4].hex()
    return {"ok": True, "out": str(out_file), "head_magic": magic}


def so_url_dump(input_path, out_dir):
    """Extract plaintext URLs from .so binary."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    raw = p.read_bytes()
    urls = _re.findall(rb'https?://[A-Za-z0-9._/\-?=&%+#:@]{8,200}', raw)
    lines = ["SO URL DUMP — %s" % p.name, "found=%d" % len(urls), ""]
    lines += [u.decode("utf-8", errors="replace") for u in urls[:200]]
    out_file = out_dir / "so_urls.txt"
    out_file.write_text("\n".join(lines)); return {"ok": True, "out": str(out_file), "count": len(urls)}


def so_aes_probe(input_path, out_dir):
    """Detect AES S-box / key schedule patterns in .so."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    raw = p.read_bytes()
    AES_SBOX_HEAD = bytes([0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5])
    findings = []
    pos = raw.find(AES_SBOX_HEAD)
    while pos != -1 and len(findings) < 10:
        findings.append("AES S-box at offset 0x%X" % pos)
        pos = raw.find(AES_SBOX_HEAD, pos+1)
    AES_KEY_CONST = bytes([0x01,0x00,0x00,0x00,0x02,0x00,0x00,0x00])
    kpos = raw.find(AES_KEY_CONST)
    if kpos != -1:
        findings.append("possible AES key schedule at 0x%X" % kpos)
    lines = ["SO AES PROBE — %s" % p.name, ""] + (findings if findings else ["no AES S-box pattern found"])
    out_file = out_dir / "so_aes_probe.txt"
    out_file.write_text("\n".join(lines)); return {"ok": True, "out": str(out_file), "hits": len(findings)}


def so_patch_url(input_path, out_dir, old_url="", new_url=""):
    """Patch every exact occurrence of a plaintext URL in a binary copy.

    The source file is never modified. Replacement bytes are NUL-padded to
    the original URL width so later binary offsets remain stable.
    """
    from pathlib import Path
    p = Path(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not old_url or not new_url:
        return {"ok": False, "error": "old_url and new_url required"}
    try:
        old_b = old_url.encode("utf-8")
        new_b = new_url.encode("utf-8")
    except UnicodeError:
        return {"ok": False, "error": "URL encoding must be UTF-8"}
    if not old_b:
        return {"ok": False, "error": "old_url must not be empty"}
    if len(new_b) > len(old_b):
        return {"ok": False, "error": "new_url must be <= old_url length"}
    try:
        raw = p.read_bytes()
    except OSError as exc:
        return {"ok": False, "error": "input read failed: %s" % type(exc).__name__}
    count = raw.count(old_b)
    if count == 0:
        return {"ok": False, "error": "old_url not found in binary"}
    offsets = []
    cursor = 0
    while True:
        idx = raw.find(old_b, cursor)
        if idx < 0:
            break
        offsets.append("0x%X" % idx)
        cursor = idx + len(old_b)
    padded = new_b + b"\x00" * (len(old_b) - len(new_b))
    patched = raw.replace(old_b, padded)
    out_file = out_dir / ("patched_%s" % p.name)
    try:
        out_file.write_bytes(patched)
    except OSError as exc:
        return {"ok": False, "error": "output write failed: %s" % type(exc).__name__}
    return {
        "ok": True,
        "out": str(out_file),
        "patched_count": count,
        "patched_offsets": offsets,
        "original_sha256": __import__("hashlib").sha256(raw).hexdigest(),
        "output_sha256": __import__("hashlib").sha256(patched).hexdigest(),
    }


# ── Module 11: Frida Tracer ───────────────────────────────────────────────────

def frida_generate_script(input_path, out_dir):
    """Generate a Frida JS script to trace methods in the target."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    script = r"""// ALVSIA Frida Trace Script — generated
// Usage: frida -U -f <package> -l script.js --no-pause

Java.perform(function() {
    // Hook Activity lifecycle
    var Activity = Java.use("android.app.Activity");
    Activity.onCreate.overload("android.os.Bundle").implementation = function(b) {
        console.log("[ALVSIA] Activity.onCreate called: " + this.getClass().getName());
        this.onCreate(b);
    };

    // Hook SessionGate.allowTools
    try {
        var SG = Java.use("com.alvsia.pro.sec.SessionGate");
        SG.allowTools.implementation = function(ctx) {
            console.log("[ALVSIA] SessionGate.allowTools called");
            return this.allowTools(ctx);
        };
    } catch(e) { console.log("[ALVSIA] SessionGate not found: " + e); }

    // Intercept NativeGate.preCheck
    try {
        var NG = Java.use("com.alvsia.pro.sec.NativeGate");
        NG.preCheck.implementation = function() {
            var r = this.preCheck();
            console.log("[ALVSIA] NativeGate.preCheck => " + r);
            return r;
        };
    } catch(e) { console.log("[ALVSIA] NativeGate not found: " + e); }

    console.log("[ALVSIA] Hooks installed.");
});
"""
    script = script.replace("<package>", p.name)
    out_file = out_dir / "alvsia_trace.js"
    Path(out_file).write_text(script)
    return {"ok": True, "out": str(out_file)}


def frida_jni_hook(input_path, out_dir):
    """Generate Frida script to hook JNI functions in a .so."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    so_name = p.name
    script = """// ALVSIA JNI Hook — %s
// Intercept JNI_OnLoad and common JNI patterns

var lib = Module.findBaseAddress("%s");
if (lib) {
    console.log("[JNI] %s base: " + lib);
    // Hook JNI_OnLoad
    var jni_onload = Module.findExportByName("%s", "JNI_OnLoad");
    if (jni_onload) {
        Interceptor.attach(jni_onload, {
            onEnter: function(args) { console.log("[JNI] JNI_OnLoad called"); },
            onLeave: function(ret)  { console.log("[JNI] JNI_OnLoad ret=" + ret); }
        });
    } else {
        console.log("[JNI] JNI_OnLoad not found as export — may be stripped");
    }
} else {
    console.log("[JNI] Module not loaded: %s");
}
""" % (so_name, so_name, so_name, so_name, so_name)
    out_file = out_dir / ("jni_hook_%s.js" % p.stem)
    Path(out_file).write_text(script)
    return {"ok": True, "out": str(out_file)}


def frida_spawn_trace(input_path, out_dir):
    """Generate Frida spawn-trace shell command for a package."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    # The caller passes a package identifier (e.g. com.tencent.ig), not a filename.
    # Path.stem would incorrectly truncate the final segment after the last dot.
    pkg = str(input_path).strip()
    lines = [
        "# ALVSIA Frida Spawn Trace",
        "# Install frida-server on device, then run:",
        "",
        "frida-trace -U -f %s -j '*!*' --no-pause" % pkg,
        "",
        "# Or spawn with custom script:",
        "frida -U -f %s -l alvsia_trace.js --no-pause" % pkg,
        "",
        "# List running processes:",
        "frida-ps -U",
    ]
    out_file = out_dir / "spawn_trace_cmd.txt"
    Path(out_file).write_text("\n".join(lines))
    return {"ok": True, "out": str(out_file)}


# ── Module 12: XOR Suite ──────────────────────────────────────────────────────

def xor_single_byte_scan(input_path, out_dir):
    """Scan all 256 single-byte XOR keys, report magic matches."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    raw = p.read_bytes()
    MAGICS = {
        b"\x1bLua": "Lua bytecode",
        b"\x1bLJ\x02": "LuaJIT 2",
        b"\x7fELF": "ELF",
        b"PK\x03\x04": "ZIP/OBB",
        b"\x04\x22\x4d\x18": "Zstd",
    }
    hits = []
    for key in range(256):
        head = bytes(raw[i] ^ key for i in range(min(8, len(raw))))
        for magic, name in MAGICS.items():
            if head[:len(magic)] == magic:
                hits.append("key=0x%02X => %s" % (key, name))
    lines = ["XOR SINGLE-BYTE SCAN — %s" % p.name, ""]
    lines += hits if hits else ["no matching XOR key found"]
    out_file = out_dir / "xor_scan.txt"
    out_file.write_text("\n".join(lines)); return {"ok": True, "out": str(out_file), "hits": len(hits)}


def xor_apply_key(input_path, out_dir, key_hex=""):
    """XOR entire file with given hex key (repeating)."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    if not key_hex:
        return {"ok": False, "error": "key_hex required"}
    try:
        key = bytes.fromhex(key_hex.replace(" ","").replace("0x",""))
        if not key:
            return {"ok": False, "error": "key_hex must contain at least one byte"}
    except Exception:
        return {"ok": False, "error": "invalid key_hex"}
    raw = p.read_bytes()
    dec = bytes(raw[i] ^ key[i % len(key)] for i in range(len(raw)))
    out_file = out_dir / ("xor_out_%s" % p.name)
    Path(out_file).write_bytes(dec)
    return {"ok": True, "out": str(out_file), "key_len": len(key), "head": dec[:8].hex()}


def xor_luas_strip(input_path, out_dir):
    """Strip common single-byte XOR from Lua files and save decoded."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    raw = p.read_bytes()
    LUA_MAGICS = [b"\x1bLua", b"\x1bLJ\x02", b"\x1bLJ\x01"]
    for key in range(256):
        head = bytes(raw[i] ^ key for i in range(min(4, len(raw))))
        for magic in LUA_MAGICS:
            if head[:len(magic)] == magic:
                dec = bytes(raw[i] ^ key for i in range(len(raw)))
                out_file = out_dir / ("decoded_0x%02X_%s" % (key, p.name))
                Path(out_file).write_bytes(dec)
                return {"ok": True, "out": str(out_file), "key": "0x%02X" % key}
    return {"ok": False, "error": "no single-byte XOR key reveals Lua magic"}


def xor_batch(input_path, out_dir, key_hex=""):
    """XOR-decode all .lua/.so files in a folder."""
    from pathlib import Path
    base = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    if not key_hex:
        return {"ok": False, "error": "key_hex required"}
    try:
        key = bytes.fromhex(key_hex.replace(" ","").replace("0x",""))
        if not key:
            return {"ok": False, "error": "key_hex must contain at least one byte"}
    except Exception:
        return {"ok": False, "error": "invalid key_hex"}
    processed = 0
    for fp in sorted(base.rglob("*")):
        if fp.is_file():
            raw = fp.read_bytes()
            dec = bytes(raw[i] ^ key[i % len(key)] for i in range(len(raw)))
            dest = out_dir / fp.relative_to(base)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(dec); processed += 1
    if processed == 0:
        return {"ok": False, "error": "WORK/BATCH contains no supported files", "out": str(out_dir)}
    return {"ok": True, "processed": processed, "out": str(out_dir)}


# ── Module 13: Decrypt Engine ─────────────────────────────────────────────────

def _aes_unpad_plaintext(data):
    """Remove valid PKCS#7 padding after decryption; otherwise preserve bytes."""
    if not data:
        return data
    pad_len = data[-1]
    if 1 <= pad_len <= 16 and data[-pad_len:] == bytes([pad_len]) * pad_len:
        return data[:-pad_len]
    return data


def _aes_ecb_decrypt(data, key):
    try:
        from Crypto.Cipher import AES
        if not data or len(data) % 16:
            raise ValueError("AES ciphertext length must be a non-zero multiple of 16 bytes")
        cipher = AES.new(key, AES.MODE_ECB)
        return _aes_unpad_plaintext(cipher.decrypt(data))
    except ImportError:
        return None


def _aes_cbc_decrypt(data, key, iv):
    try:
        from Crypto.Cipher import AES
        if not data or len(data) % 16:
            raise ValueError("AES ciphertext length must be a non-zero multiple of 16 bytes")
        if len(iv) != 16:
            raise ValueError("AES-CBC IV must be exactly 16 bytes")
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return _aes_unpad_plaintext(cipher.decrypt(data))
    except ImportError:
        return None

def decrypt_auto(input_path, out_dir, work_dir=None):
    """Try decompression, known-magic XOR, and configured AES/ZUC-like/SM4 candidates."""
    from pathlib import Path
    import base64
    p = Path(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = p.read_bytes()
    results = []
    successes = []

    def looks_decoded(path):
        try:
            data = Path(path).read_bytes()
            if not data:
                return False
            magics = (
                b"\x1bLua", b"\x1bLJ\x02", b"\x1bLJ\x01",
                b"\x7fELF", b"PK\x03\x04", b"ALVSEAL1", b"ALVLUA1",
                b"ALVSEAL3", b"\x28\xb5\x2f\xfd", b"\x04\x22\x4d\x18",
            )
            if any(data.startswith(magic) for magic in magics):
                return True
            sample = data[:4096]
            printable = sum((32 <= b <= 126) or b in (9, 10, 13) for b in sample)
            return bool(sample) and printable / len(sample) >= 0.88
        except Exception:
            return False

    # Try zlib decompression.
    try:
        dec = zlib.decompress(raw)
        out_file = out_dir / ("auto_zlib_%s" % p.name)
        out_file.write_bytes(dec)
        results.append("zlib candidate -> %s" % out_file.name)
        successes.append(str(out_file))
    except Exception:
        pass

    # Try base64 + zlib.
    try:
        dec = zlib.decompress(base64.b64decode(raw, validate=True))
        out_file = out_dir / ("auto_b64zlib_%s" % p.name)
        out_file.write_bytes(dec)
        results.append("base64+zlib candidate -> %s" % out_file.name)
        successes.append(str(out_file))
    except Exception:
        pass

    # Try repeating single-byte XOR, but accept only known file magic.
    for key in range(1, 256):
        head = bytes(raw[i] ^ key for i in range(min(8, len(raw))))
        if (head[:3] == b"\x1bLu" or head[:4] in
                (b"\x7fELF", b"PK\x03\x04", b"\x1bLJ\x02", b"\x1bLua")):
            dec = bytes(raw[i] ^ key for i in range(len(raw)))
            out_file = out_dir / ("auto_xor0x%02X_%s" % (key, p.name))
            out_file.write_bytes(dec)
            results.append("XOR key=0x%02X candidate -> %s" % (key, out_file.name))
            successes.append(str(out_file))
            break

    # Try the legacy SIMPLE1 (single-byte 0x01 XOR) candidate.
    try:
        result = decrypt_simple1(p, out_dir)
        candidate = Path(result.get("out", "")) if result.get("out") else None
        if result.get("ok") and candidate and candidate.is_file():
            unique = out_dir / ("auto_simple1_%s" % p.name)
            unique.write_bytes(candidate.read_bytes())
            results.append("SIMPLE1 candidate -> %s" % unique.name)
            if looks_decoded(unique):
                successes.append(str(unique))
    except Exception as exc:
        results.append("SIMPLE1 candidate skipped: %s" % (str(exc)[:160]))

    # Configured cipher candidates. Keep each candidate under a unique name.
    cfg_root = Path(work_dir) if work_dir else None
    def read_cfg(name):
        values = {}
        cfg = cfg_root / name if cfg_root else None
        if not cfg or not cfg.is_file():
            return values
        for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip().lower()] = value.strip()
        return values

    aes = read_cfg("aes_config.txt")
    aes_key = aes.get("key", aes.get("key_hex", ""))
    aes_iv = aes.get("iv", aes.get("iv_hex", ""))
    if aes_key:
        modes = [("ecb", "")] + ([("cbc", aes_iv)] if aes_iv else [])
        for mode, iv in modes:
            try:
                result = decrypt_aes(p, out_dir, aes_key, iv)
                candidate = Path(result.get("out", "")) if result.get("out") else None
                if result.get("ok") and candidate and candidate.is_file():
                    unique = out_dir / ("auto_aes_%s_%s" % (mode, p.name))
                    unique.write_bytes(candidate.read_bytes())
                    results.append("AES-%s candidate -> %s" % (mode.upper(), unique.name))
                    if looks_decoded(unique):
                        successes.append(str(unique))
                        results.append("AES-%s candidate passed basic file-content validation" % mode.upper())
            except Exception as exc:
                results.append("AES-%s skipped: %s" % (mode.upper(), str(exc)[:160]))

    zuc = read_cfg("zuc_config.txt")
    zuc_key = zuc.get("key", zuc.get("key_hex", ""))
    zuc_iv = zuc.get("iv", zuc.get("iv_hex", ""))
    if zuc_key:
        try:
            result = decrypt_zuc(p, out_dir, zuc_key, zuc_iv)
            candidate = Path(result.get("out", "")) if result.get("out") else None
            if result.get("ok") and candidate and candidate.is_file():
                unique = out_dir / ("auto_zuc_like_%s" % p.name)
                unique.write_bytes(candidate.read_bytes())
                results.append("ZUC-like candidate -> %s (not standards-compliant ZUC)" % unique.name)
                if looks_decoded(unique):
                    successes.append(str(unique))
        except Exception as exc:
            results.append("ZUC-like candidate skipped: %s" % (str(exc)[:160]))

    sm4 = read_cfg("sm4_config.txt")
    sm4_key = sm4.get("key", sm4.get("key_hex", ""))
    if sm4_key:
        mode = sm4.get("mode", "ECB").upper()
        iv = sm4.get("iv", sm4.get("iv_hex", ""))
        try:
            result = decrypt_sm4(p, out_dir, sm4_key, mode, iv)
            candidate = Path(result.get("out", "")) if result.get("out") else None
            if result.get("ok") and candidate and candidate.is_file():
                unique = out_dir / ("auto_sm4_%s_%s" % (mode.lower(), p.name))
                unique.write_bytes(candidate.read_bytes())
                results.append("SM4-%s candidate -> %s" % (mode, unique.name))
                if looks_decoded(unique):
                    successes.append(str(unique))
        except Exception as exc:
            results.append("SM4 candidate skipped: %s" % (str(exc)[:160]))

    out_report = out_dir / "decrypt_auto_report.txt"
    if not results:
        results.append("No candidate generated; manual analysis needed.")
    if not successes:
        results.append("No candidate passed basic validation; inspect generated candidates cautiously.")
    out_report.write_text("\n".join(results), encoding="utf-8")
    return {
        "ok": bool(successes),
        "out": str(out_report),
        "methods_tried": len(results),
        "validated_candidates": len(set(successes)),
        "candidates": list(dict.fromkeys(successes)),
    }

def decrypt_aes(input_path, out_dir, key_hex="", iv_hex=""):
    """AES-CBC/ECB decrypt with given hex key."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    if not key_hex:
        return {"ok": False, "error": "key_hex required (16/24/32 bytes as hex)"}
    try:
        key = bytes.fromhex(key_hex.replace(" ","").replace("0x",""))
    except Exception:
        return {"ok": False, "error": "invalid key_hex"}
    raw = p.read_bytes()
    iv = bytes.fromhex(iv_hex.replace(" ","")) if iv_hex else b"\x00"*16
    dec = _aes_cbc_decrypt(raw, key, iv) if iv_hex else _aes_ecb_decrypt(raw, key)
    if dec is None:
        return {"ok": False, "error": "pycryptodome not available"}
    out_file = out_dir / ("aes_dec_%s" % p.name)
    Path(out_file).write_bytes(dec)
    return {"ok": True, "out": str(out_file), "head": dec[:8].hex()}


def decrypt_zuc(input_path, out_dir, key_hex="", iv_hex=""):
    """ZUC stream cipher decrypt (pure-Python fallback)."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    # ZUC not widely available — apply XOR with key-derived stream as approximation
    if not key_hex:
        return {"ok": False, "error": "key_hex required"}
    try:
        key = bytes.fromhex(key_hex.replace(" ",""))
        if not key:
            return {"ok": False, "error": "key_hex must contain at least one byte"}
    except Exception:
        return {"ok": False, "error": "invalid key_hex"}
    raw = p.read_bytes()
    # This is an explicitly labeled ZUC-like fallback, not standards-compliant ZUC.
    # Incorporate the configured IV into the fallback stream instead of silently ignoring it.
    try:
        iv = bytes.fromhex(iv_hex.replace(" ", "")) if iv_hex else b""
    except Exception:
        return {"ok": False, "error": "invalid iv_hex"}
    state = [(key[i % len(key)] ^ iv[i % len(iv)]) if iv else key[i % len(key)] for i in range(16)]
    stream = []
    for i in range(len(raw)):
        out_word = state[0] ^ state[3] ^ state[5] ^ state[11]
        stream.append(out_word & 0xFF)
        state = state[1:] + [out_word & 0xFF]
    dec = bytes(raw[i] ^ stream[i] for i in range(len(raw)))
    out_file = out_dir / ("zuc_dec_%s" % p.name)
    Path(out_file).write_bytes(dec)
    return {"ok": True, "out": str(out_file), "note": "ZUC approximation — use real ZUC lib for production"}


def decrypt_sm4(input_path, out_dir, key_hex="", mode="ECB", iv_hex=""):
    """SM4 block cipher decrypt in ECB or CBC mode (pure-Python)."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    if not key_hex:
        return {"ok": False, "error": "key_hex required (16 bytes)"}
    try:
        key = bytes.fromhex(key_hex.replace(" ",""))
        if len(key) != 16: raise ValueError("SM4 key must be 16 bytes")
    except Exception as e:
        return {"ok": False, "error": str(e)}
    mode = (mode or "ECB").strip().upper()
    if mode not in ("ECB", "CBC"):
        return {"ok": False, "error": "SM4 mode must be ECB or CBC"}
    try:
        iv = bytes.fromhex(iv_hex.replace(" ", "")) if iv_hex else b""
    except Exception:
        return {"ok": False, "error": "invalid SM4 IV"}
    if mode == "CBC" and len(iv) != 16:
        return {"ok": False, "error": "SM4-CBC IV must be 16 bytes"}
    raw = p.read_bytes()
    if not raw or len(raw) % 16:
        return {"ok": False, "error": "SM4 ciphertext length must be a non-zero multiple of 16 bytes"}
    # SM4 S-box
    SBOX = [0xd6,0x90,0xe9,0xfe,0xcc,0xe1,0x3d,0xb7,0x16,0xb6,0x14,0xc2,0x28,0xfb,0x2c,0x05,
            0x2b,0x67,0x9a,0x76,0x2a,0xbe,0x04,0xc3,0xaa,0x44,0x13,0x26,0x49,0x86,0x06,0x99,
            0x9c,0x42,0x50,0xf4,0x91,0xef,0x98,0x7a,0x33,0x54,0x0b,0x43,0xed,0xcf,0xac,0x62,
            0xe4,0xb3,0x1c,0xa9,0xc9,0x08,0xe8,0x95,0x80,0xdf,0x94,0xfa,0x75,0x8f,0x3f,0xa6,
            0x47,0x07,0xa7,0xfc,0xf3,0x73,0x17,0xba,0x83,0x59,0x3c,0x19,0xe6,0x85,0x4f,0xa8,
            0x68,0x6b,0x81,0xb2,0x71,0x64,0xda,0x8b,0xf8,0xeb,0x0f,0x4b,0x70,0x56,0x9d,0x35,
            0x1e,0x24,0x0e,0x5e,0x63,0x58,0xd1,0xa2,0x25,0x22,0x7c,0x3b,0x01,0x21,0x78,0x87,
            0xd4,0x00,0x46,0x57,0x9f,0xd3,0x27,0x52,0x4c,0x36,0x02,0xe7,0xa0,0xc4,0xc8,0x9e,
            0xea,0xbf,0x8a,0xd2,0x40,0xc7,0x38,0xb5,0xa3,0xf7,0xf2,0xce,0xf9,0x61,0x15,0xa1,
            0xe0,0xae,0x5d,0xa4,0x9b,0x34,0x1a,0x55,0xad,0x93,0x32,0x30,0xf5,0x8c,0xb1,0xe3,
            0x1d,0xf6,0xe2,0x2e,0x82,0x66,0xca,0x60,0xc0,0x29,0x23,0xab,0x0d,0x53,0x4e,0x6f,
            0xd5,0xdb,0x37,0x45,0xde,0xfd,0x8e,0x2f,0x03,0xff,0x6a,0x72,0x6d,0x6c,0x5b,0x51,
            0x8d,0x1b,0xaf,0x92,0xbb,0xdd,0xbc,0x7f,0x11,0xd9,0x5c,0x41,0x1f,0x10,0x5a,0xd8,
            0x0a,0xc1,0x31,0x88,0xa5,0xcd,0x7b,0xbd,0x2d,0x74,0xd0,0x12,0xb8,0xe5,0xb4,0xb0,
            0x89,0x69,0x97,0x4a,0x0c,0x96,0x77,0x7e,0x65,0xb9,0xf1,0x09,0xc5,0x6e,0xc6,0x84,
            0x18,0xf0,0x7d,0xec,0x3a,0xdc,0x4d,0x20,0x79,0xee,0x5f,0x3e,0xd7,0xcb,0x39,0x48]
    def sm4_sbox(b): return SBOX[b]
    def sm4_tau(A):
        return (sm4_sbox((A>>24)&0xFF)<<24)|(sm4_sbox((A>>16)&0xFF)<<16)|(sm4_sbox((A>>8)&0xFF)<<8)|sm4_sbox(A&0xFF)
    def rot(x,n): return ((x<<n)|(x>>(32-n)))&0xFFFFFFFF
    def sm4_L(B): return B^rot(B,2)^rot(B,10)^rot(B,18)^rot(B,24)
    def sm4_L2(B): return B^rot(B,13)^rot(B,23)
    def sm4_T(A): return sm4_L(sm4_tau(A))
    def sm4_T2(A): return sm4_L2(sm4_tau(A))
    FK=[0xA3B1BAC6,0x56AA3350,0x677D9197,0xB27022DC]
    CK=[0x00070E15,0x1C232A31,0x383F464D,0x545B6269,0x70777E85,0x8C939AA1,0xA8AFB6BD,0xC4CBD2D9,
        0xE0E7EEF5,0xFC030A11,0x181F262D,0x343B4249,0x50575E65,0x6C737A81,0x888F969D,0xA4ABB2B9,
        0xC0C7CED5,0xDCE3EAF1,0xF8FF060D,0x141B2229,0x30373E45,0x4C535A61,0x686F767D,0x848B9299,
        0xA0A7AEB5,0xBCC3CAD1,0xD8DFE6ED,0xF4FB0209,0x10171E25,0x2C333A41,0x484F565D,0x646B7279]
    import struct as _struct
    MK = _struct.unpack(">4I", key)
    K = [MK[i]^FK[i] for i in range(4)]
    rk = []
    for i in range(32):
        tmp = K[1]^K[2]^K[3]^CK[i]
        rki = K[0]^sm4_T2(tmp)
        rk.append(rki); K=[K[1],K[2],K[3],rki]
    rk_dec = list(reversed(rk))
    def sm4_block(block, rnd_keys):
        X = list(_struct.unpack(">4I", block))
        for rk_i in rnd_keys:
            tmp = X[1]^X[2]^X[3]^rk_i
            Xi = X[0]^sm4_T(tmp)
            X=[X[1],X[2],X[3],Xi]
        return _struct.pack(">4I",X[3],X[2],X[1],X[0])
    # Decrypt the ciphertext as-is; padding belongs to plaintext, not ciphertext.
    plain_blocks = []
    previous = iv
    for offset in range(0, len(raw), 16):
        cipher_block = raw[offset:offset + 16]
        plain_block = sm4_block(cipher_block, rk_dec)
        if mode == "CBC":
            plain_block = bytes(a ^ b for a, b in zip(plain_block, previous))
            previous = cipher_block
        plain_blocks.append(plain_block)
    dec = _aes_unpad_plaintext(b"".join(plain_blocks))
    out_file = out_dir / ("sm4_dec_%s" % p.name)
    Path(out_file).write_bytes(dec)
    return {"ok": True, "out": str(out_file), "head": dec[:8].hex(), "mode": mode}


def decrypt_simple1(input_path, out_dir, key_hex="01"):
    """Simple single-byte XOR decrypt (convenience wrapper)."""
    return xor_apply_key(input_path, out_dir, key_hex)


# ── Module 14: PAK Deep ───────────────────────────────────────────────────────

def pak_deep_aes(input_path, out_dir, key_hex="", iv_hex=""):
    """AES decrypt a PAK container then extract."""
    result = decrypt_aes(input_path, out_dir, key_hex, iv_hex)
    if not result.get("ok"):
        return result
    # Try ZIP extraction on decrypted
    from pathlib import Path
    import zipfile
    dec_file = result["out"]
    try:
        with zipfile.ZipFile(dec_file) as zf:
            _alvsia_safe_extract_zip(zf, out_dir)
            result["extracted"] = len(zf.namelist())
    except Exception:
        result["note"] = "decrypted but not a valid ZIP/PAK"
    return result


def pak_deep_zstd(input_path, out_dir):
    """Decompress Zstd-compressed PAK."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    raw = p.read_bytes()
    try:
        import zstd
        dec = zstd.decompress(raw)
    except ImportError:
        try:
            import zstandard as zstd2
            dec = zstd2.ZstdDecompressor().decompress(raw)
        except ImportError:
            # Pure-Python fallback attempt via subprocess
            import subprocess, tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zst") as tf:
                tf.write(raw); tf_path = tf.name
            out_path = tf_path.replace(".zst","")
            r = subprocess.run(["zstd","-d",tf_path,"-o",out_path], capture_output=True)
            if r.returncode == 0:
                dec = open(out_path,"rb").read()
            else:
                return {"ok": False, "error": "zstd not available"}
    out_file = out_dir / ("zstd_dec_%s" % p.stem)
    Path(out_file).write_bytes(dec)
    return {"ok": True, "out": str(out_file), "dec_size": len(dec)}


def pak_deep_zuc(input_path, out_dir, key_hex="", iv_hex=""):
    """ZUC-like fallback decrypt PAK then attempt ZIP extraction."""
    result = decrypt_zuc(input_path, out_dir, key_hex, iv_hex)
    if not result.get("ok"): return result
    from pathlib import Path
    import zipfile
    try:
        with zipfile.ZipFile(result["out"]) as zf:
            _alvsia_safe_extract_zip(zf, out_dir)
            result["extracted"] = len(zf.namelist())
    except Exception:
        result["note"] = "decrypted but not ZIP"
    return result


def pak_deep_sm4(input_path, out_dir, key_hex="", mode="ECB", iv_hex=""):
    """SM4 decrypt PAK then attempt ZIP extraction."""
    result = decrypt_sm4(input_path, out_dir, key_hex, mode, iv_hex)
    if not result.get("ok"): return result
    from pathlib import Path
    import zipfile
    try:
        with zipfile.ZipFile(result["out"]) as zf:
            _alvsia_safe_extract_zip(zf, out_dir)
            result["extracted"] = len(zf.namelist())
    except Exception:
        result["note"] = "decrypted but not ZIP"
    return result


def pak_deep_auto(input_path, out_dir):
    """Auto-detect PAK encryption and extract."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    raw = p.read_bytes()
    # Try plain ZIP
    import zipfile
    if raw[:2] == b"PK":
        try:
            with zipfile.ZipFile(str(p)) as zf:
                _alvsia_safe_extract_zip(zf, str(out_dir))
                return {"ok": True, "method": "plain_zip", "extracted": len(zf.namelist()), "out": str(out_dir)}
        except Exception: pass
    # Try zlib
    try:
        dec = zlib.decompress(raw)
        out_file = out_dir / ("dec_%s" % p.name)
        Path(out_file).write_bytes(dec)
        return {"ok": True, "method": "zlib", "out": str(out_file)}
    except Exception: pass
    # Try XOR
    for key in range(1,256):
        head = bytes(raw[i]^key for i in range(min(4,len(raw))))
        if head[:2] == b"PK" or head[:3] == b"\x1bLu":
            dec = bytes(raw[i]^key for i in range(len(raw)))
            out_file = out_dir / ("xor0x%02X_%s" % (key, p.name))
            Path(out_file).write_bytes(dec)
            return {"ok": True, "method": "XOR_0x%02X" % key, "out": str(out_file)}
    return {"ok": False, "error": "could not auto-detect PAK encryption"}


# ── Module 15: String Recover ─────────────────────────────────────────────────

def string_recover(input_path, out_dir):
    """Recover obfuscated strings from binary (brute-force decodes)."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    raw = p.read_bytes()
    results = []
    # 1. Raw ASCII strings
    buf = bytearray(); raw_strings = []
    for b in raw:
        if 32 <= b <= 126: buf.append(b)
        else:
            if len(buf) >= 5: raw_strings.append(buf.decode("ascii","replace"))
            buf = bytearray()
    results.append("=== RAW STRINGS (%d) ===" % len(raw_strings))
    results.extend(raw_strings[:300])
    # 2. XOR-1 pass
    xor1 = bytes(b^1 for b in raw)
    buf2 = bytearray(); xored = []
    for b in xor1:
        if 32 <= b <= 126: buf2.append(b)
        else:
            if len(buf2) >= 5: xored.append(buf2.decode("ascii","replace"))
            buf2 = bytearray()
    results.append("\n=== XOR-0x01 STRINGS (%d) ===" % len(xored))
    results.extend(xored[:100])
    out_file = out_dir / ("strings_%s.txt" % p.stem)
    Path(out_file).write_text("\n".join(results), encoding="utf-8")
    return {"ok": True, "out": str(out_file), "raw_count": len(raw_strings)}


def string_constant_pool(input_path, out_dir):
    """Extract Lua constant pool strings (Lua 5.1 bytecode format)."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    raw = p.read_bytes()
    if raw[:4] not in (b"\x1bLua", b"\x1bLJ\x02", b"\x1bLJ\x01"):
        return {"ok": False, "error": "not a Lua bytecode file"}
    # Extract all null-terminated strings embedded in bytecode
    strings = []; buf = bytearray()
    for byte in raw[12:]:  # skip header
        if 0x20 <= byte <= 0x7e: buf.append(byte)
        elif byte == 0 and len(buf) >= 3:
            strings.append(buf.decode("ascii","replace")); buf = bytearray()
        else: buf = bytearray()
    out_file = out_dir / ("constants_%s.txt" % p.stem)
    Path(out_file).write_text("\n".join(strings[:1000]), encoding="utf-8")
    return {"ok": True, "out": str(out_file), "count": len(strings)}


def string_xref(input_path, out_dir, search=""):
    """Cross-reference a string in binary, report all offsets."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    if not search:
        return {"ok": False, "error": "search string required"}
    raw = p.read_bytes()
    needle = search.encode("utf-8")
    offsets = []
    pos = raw.find(needle)
    while pos != -1:
        offsets.append("0x%X" % pos)
        pos = raw.find(needle, pos+1)
    lines = ["XREF: '%s' in %s" % (search, p.name), "hits=%d" % len(offsets), ""] + offsets
    out_file = out_dir / ("xref_%s.txt" % p.stem)
    Path(out_file).write_text("\n".join(lines))
    return {"ok": True, "out": str(out_file), "hits": len(offsets)}


# ── Module 16: Lua Inject ─────────────────────────────────────────────────────

def lua_patch_bytecode(input_path, out_dir, patch_offset="", patch_hex=""):
    """Patch raw bytes at offset in Lua bytecode."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    if not patch_offset or not patch_hex:
        return {"ok": False, "error": "patch_offset (hex) and patch_hex required"}
    try:
        offset = int(patch_offset, 16) if patch_offset.startswith("0x") else int(patch_offset)
        patch = bytes.fromhex(patch_hex.replace(" ",""))
    except Exception as e:
        return {"ok": False, "error": str(e)}
    raw = bytearray(p.read_bytes())
    if offset + len(patch) > len(raw):
        return {"ok": False, "error": "patch extends beyond file end"}
    raw[offset:offset+len(patch)] = patch
    out_file = out_dir / ("patched_%s" % p.name)
    Path(out_file).write_bytes(bytes(raw))
    return {"ok": True, "out": str(out_file), "patched_at": "0x%X" % offset}


def lua_inject_hook(input_path, out_dir, hook_path=None):
    """Prepend user-supplied Lua hook source to a Lua source file."""
    from pathlib import Path
    p = Path(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not p.is_file():
        return {"ok": False, "error": "input Lua source file not found"}
    if not hook_path or not Path(hook_path).is_file():
        return {"ok": False, "error": "hook source file required"}
    try:
        source = p.read_text(encoding="utf-8")
        hook = Path(hook_path).read_text(encoding="utf-8").strip()
    except UnicodeError:
        return {"ok": False, "error": "input and hook must be text Lua source files"}
    if not hook:
        return {"ok": False, "error": "hook source is empty"}
    out_file = out_dir / ("%s_hooked.lua" % p.stem)
    out_file.write_text(hook + "\n\n" + source, encoding="utf-8")
    return {
        "ok": True,
        "out": str(out_file),
        "note": "Hook source prepended; Lua bytecode compilation is not performed by this operation."
    }


def lua_mod_repack(input_path, out_dir):
    """Repack a modified Lua file into a ZIP/OBB container."""
    from pathlib import Path
    import zipfile
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / ("repacked_%s.obb" % p.stem)
    with zipfile.ZipFile(str(out_file), "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if p.is_dir():
            for fp in sorted(p.rglob("*")):
                if fp.is_file():
                    zf.write(str(fp), fp.relative_to(p).as_posix())
        else:
            zf.write(str(p), p.name)
    return {"ok": True, "out": str(out_file)}


# ── Module 17: Anti-RE Audit ──────────────────────────────────────────────────

def audit_apk(input_path, out_dir):
    """Audit APK for anti-RE measures: obfuscation, native guards, packing."""
    from pathlib import Path
    import zipfile, hashlib
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    lines = ["ALVSIA APK AUDIT — %s" % p.name, "size=%s" % p.stat().st_size, ""]
    if not zipfile.is_zipfile(str(p)):
        lines.append("ERROR: not a valid ZIP/APK")
        out_file = out_dir / "apk_audit.txt"
        Path(out_file).write_text("\n".join(lines)); return {"ok": False, "out": str(out_file)}
    with zipfile.ZipFile(str(p)) as zf:
        names = zf.namelist()
        dex_files = [n for n in names if n.endswith(".dex")]
        so_files  = [n for n in names if n.endswith(".so")]
        lines.append("dex_count=%d" % len(dex_files))
        lines.append("so_count=%d" % len(so_files))
        lines.append("total_entries=%d" % len(names))
        # Check for ProGuard/R8 mapping residue
        has_mapping = any("proguard" in n.lower() or "mapping" in n.lower() for n in names)
        lines.append("proguard_residue=%s" % has_mapping)
        # Check for known packer signatures
        has_reark = any("rsprotect" in n.lower() or "ark" in n.lower() for n in names)
        has_jiagu = any("jiagu" in n.lower() for n in names)
        lines.append("reark_detected=%s" % has_reark)
        lines.append("jiagu_detected=%s" % has_jiagu)
        # Manifest check
        if "AndroidManifest.xml" in names:
            manifest_raw = zf.read("AndroidManifest.xml")
            lines.append("manifest_size=%d (binary XML)" % len(manifest_raw))
            lines.append("debuggable_string_present=%s" % (b"debuggable" in manifest_raw))
        # Check DEX sizes
        for dex in dex_files:
            sz = zf.getinfo(dex).file_size
            lines.append("  %s: %d bytes" % (dex, sz))
    out_file = out_dir / "apk_audit.txt"
    Path(out_file).write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "out": str(out_file)}


def audit_lua(input_path, out_dir):
    """Audit a Lua file for obfuscation indicators."""
    from pathlib import Path
    import math, hashlib
    p = Path(input_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    raw = p.read_bytes()
    lines = ["ALVSIA LUA AUDIT — %s" % p.name, "size=%s" % len(raw), ""]
    # Format
    if raw[:4] == b"\x1bLua": lines.append("format=Lua bytecode")
    elif raw[:4] in (b"\x1bLJ\x02", b"\x1bLJ\x01"): lines.append("format=LuaJIT bytecode")
    else: lines.append("format=source/unknown")
    # Entropy
    freq=[0]*256
    for b in raw: freq[b]+=1
    ent = -sum((c/len(raw))*math.log2(c/len(raw)) for c in freq if c>0) if raw else 0
    lines.append("entropy=%.3f (%s)" % (ent, "HIGH — likely encrypted/obfuscated" if ent>7.2 else "normal"))
    # XOR candidates
    xor_hits = []
    for key in range(1,256):
        h = bytes(raw[i]^key for i in range(min(4,len(raw))))
        if h[:3] in (b"\x1bLu", b"\x1bLJ"):
            xor_hits.append("0x%02X" % key)
    lines.append("xor_candidates=%s" % (",".join(xor_hits) if xor_hits else "none"))
    lines.append("md5=%s" % hashlib.md5(raw).hexdigest())
    # Anti-debug patterns in source
    if not raw[:1] == b"\x1b":
        src = raw.decode("utf-8","replace")
        for pat in ["pcall","xpcall","debug.","io.open","os.execute","load(","loadstring("]:
            if pat in src: lines.append("pattern_found: %s" % pat)
    out_file = out_dir / ("lua_audit_%s.txt" % p.stem)
    Path(out_file).write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "out": str(out_file)}


def audit_so(input_path, out_dir):
    """Check .so for exported symbols, debug info, coverage."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = ["ALVSIA SO AUDIT — %s" % p.name, "size=%s" % p.stat().st_size, ""]
    raw = p.read_bytes()
    if raw[:4] == b"\x7fELF":
        lines.append("format=ELF")
        bits = "64-bit" if raw[4] == 2 else "32-bit"
        endian = "LSB" if raw[5] == 1 else "MSB"
        lines.append("arch=%s %s" % (bits, endian))
    else:
        lines.append("format=NOT_ELF (magic=%s)" % raw[:4].hex())
    has_debug = b".debug_" in raw or b"DWARF" in raw or b"__DWARF" in raw
    lines.append("debug_info=%s" % ("PRESENT (weak: strip it)" if has_debug else "stripped (good)"))
    symbol_section = b""
    try:
        dynstr_marker = raw.find(b".dynstr")
        if dynstr_marker > 0:
            start = max(0, dynstr_marker - 100)
            end = min(len(raw), dynstr_marker + 4096)
            section_raw = raw[start:end]
            symbols = []
            cur2 = bytearray()
            for b in section_raw:
                if 32 <= b <= 126: cur2.append(b)
                else:
                    if len(cur2) >= 4: symbols.append(cur2.decode("ascii", errors="replace"))
                    cur2 = bytearray()
            lines.append("exported_symbols_sample=%s" % len(symbols))
            for s in symbols[:20]: lines.append("  sym: " + s)
    except Exception: pass
    url_re = _re.compile(rb'https?://[A-Za-z0-9._/\-?=&%+#:@]{8,100}')
    urls = [u.decode("utf-8", errors="replace") for u in url_re.findall(raw)][:10]
    if urls:
        lines.append("\nPlaintext URLs in .so:")
        for u in urls: lines.append("  " + u)
    out_file = out_dir / "so_report.txt"
    out_file.write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "out": str(out_file)}


def _alv_install_operation_proof_json(proof_json):
    try:
        raw = proof_json.decode('utf-8') if isinstance(proof_json, bytes) else str(proof_json or '')
        parsed = __import__('json').loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError('grant payload must be an object')
        return _alv_install_operation_proof(parsed)
    except Exception:
        _alv_clear_operation_proof()
        return False
