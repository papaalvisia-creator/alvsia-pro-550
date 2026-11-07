from __future__ import annotations
from pathlib import Path
import ast
import re
import shutil
import subprocess
import tempfile
from .detector import detect_lua, LuaInfo
from .container import unwrap_lua_container

def _find_java():
    for name in ("java", "/system/bin/java", "/data/data/com.alvsia.pro/files/java/bin/java"):
        if shutil.which(name) or Path(name).is_file():
            return name
    return None

def _lua_code_without_literals(text: str) -> str:
    """Blank Lua strings/comments before structural keyword checks."""
    out = list(text)
    i = 0
    n = len(text)

    def blank(a: int, b: int) -> None:
        for pos in range(a, b):
            if out[pos] not in "\r\n":
                out[pos] = " "

    def long_bracket_end(pos: int):
        if pos >= n or text[pos] != "[":
            return None
        j = pos + 1
        while j < n and text[j] == "=":
            j += 1
        if j < n and text[j] == "[":
            return j - pos - 1, j + 1
        return None

    while i < n:
        if text[i] in ("'", '"'):
            quote, start = text[i], i
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                elif text[i] == quote:
                    i += 1
                    break
                else:
                    i += 1
            blank(start, min(i, n))
            continue
        if text.startswith("--", i):
            start = i
            long = long_bracket_end(i + 2)
            if long:
                eq_count, body_start = long
                close = "]" + ("=" * eq_count) + "]"
                end = text.find(close, body_start)
                i = n if end < 0 else end + len(close)
            else:
                end = text.find("\n", i + 2)
                i = n if end < 0 else end
            blank(start, i)
            continue
        long = long_bracket_end(i)
        if long:
            eq_count, body_start = long
            close = "]" + ("=" * eq_count) + "]"
            end = text.find(close, body_start)
            stop = n if end < 0 else end + len(close)
            blank(i, stop)
            i = stop
            continue
        i += 1
    return "".join(out)


def _looks_like_lua_source(text: str) -> bool:
    if not text.strip():
        return False
    sample = text[:8192]
    bad = sum(1 for c in sample if ord(c) < 9 or (13 < ord(c) < 32))
    if bad > max(2, len(sample)//100):
        return False
    code = _lua_code_without_literals(sample)
    return bool(re.search(r"\b(?:local|function|return|if|for|while|repeat|do|end)\b", code))


def _find_lua_parser(expected_version=None):
    """Find a matching PUC Lua compiler for syntax-only validation."""
    version = str(expected_version or "").lower()
    candidates = {
        "lua 5.1": ("luac5.1", "luac51"),
        "lua 5.2": ("luac5.2", "luac52"),
        "lua 5.3": ("luac5.3", "luac53"),
        "lua 5.4": ("luac5.4", "luac54"),
        "lua 5.5": ("luac5.5", "luac55"),
    }
    names = candidates.get(version, ())
    if not expected_version:
        names = ("luac", "luac5.5", "luac5.4", "luac5.3", "luac5.2", "luac5.1")
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def validate_lua_source(path_or_text, expected_version=None) -> tuple[bool, str]:
    source_path = None
    temporary = None
    if isinstance(path_or_text, Path):
        source_path = path_or_text
    elif isinstance(path_or_text, str):
        try:
            candidate_path = Path(path_or_text)
            if "\\n" not in path_or_text and candidate_path.is_file():
                source_path = candidate_path
        except (OSError, ValueError):
            source_path = None

    if source_path is not None:
        from .detector import read_lua_text_strict
        try:
            text = read_lua_text_strict(source_path)
        except ValueError as exc:
            return False, f"not decodable as Lua source: {exc}"
    else:
        text = str(path_or_text)

    if not _looks_like_lua_source(text):
        return False, "output does not look like Lua source"

    # Prefer a real parser whenever the matching compiler is installed.
    # Never claim parser validation when only the structural fallback ran.
    parser = _find_lua_parser(expected_version)
    if parser:
        try:
            if source_path is None:
                temporary = tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", suffix=".lua", delete=False
                )
                temporary.write(text)
                temporary.close()
                parse_path = temporary.name
            else:
                parse_path = str(source_path)
            proc = subprocess.run(
                [parser, "-p", parse_path],
                capture_output=True, text=True, timeout=8,
            )
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout or "syntax rejected").strip()
                return False, "Lua parser rejected source: " + detail[:500]
            return True, f"{expected_version or 'Lua'} parser accepted source"
        except subprocess.TimeoutExpired:
            return False, "Lua parser validation timed out"
        except Exception as exc:
            return False, f"Lua parser validation failed: {type(exc).__name__}: {exc}"
        finally:
            if temporary is not None:
                try:
                    Path(temporary.name).unlink(missing_ok=True)
                except Exception:
                    pass

    code = _lua_code_without_literals(text)
    tokens = re.findall(r'(?<![%\\w_])(function|if|for|while|repeat|do|end|until)(?![\\w_])', code)
    stack = []
    for tok in tokens:
        if tok in ("function", "if", "repeat"):
            stack.append({"kind": tok, "awaiting_do": False})
        elif tok in ("for", "while"):
            stack.append({"kind": tok, "awaiting_do": True})
        elif tok == "do":
            pending = next((entry for entry in reversed(stack)
                            if entry["kind"] in ("for", "while") and entry["awaiting_do"]), None)
            if pending is not None:
                pending["awaiting_do"] = False
            else:
                stack.append({"kind": "do", "awaiting_do": False})
        elif tok == "until":
            if not stack or stack[-1]["kind"] != "repeat":
                return False, "unmatched until"
            stack.pop()
        elif tok == "end":
            if not stack:
                return False, "unmatched end"
            stack.pop()
    if stack:
        return False, "unclosed Lua block(s): " + ",".join(
            entry["kind"] for entry in stack[-8:]
        )
    return True, "structural heuristic accepted; matching Lua parser unavailable"


def _extract_strings(data: bytes, minimum=4):
    out=[]; cur=bytearray()
    for b in data:
        if 32 <= b < 127 or b in (9,):
            cur.append(b)
        else:
            if len(cur)>=minimum:
                out.append(cur.decode("ascii","ignore"))
            cur.clear()
    if len(cur)>=minimum:
        out.append(cur.decode("ascii","ignore"))
    seen=set(); uniq=[]
    for s in out:
        if s not in seen:
            seen.add(s); uniq.append(s)
    return uniq

def _xor_candidate(data: bytes, key: bytes, offset: int):
    if not key or offset >= len(data): return b"", 0.0
    body=bytearray(data[offset:])
    for i in range(len(body)): body[i] ^= key[i % len(key)]
    printable=sum(1 for b in body if b in (9,10,13) or 32 <= b < 127)
    magic=1.0 if body.startswith((b"\x1bLua", b"\x1bLJ")) else 0.0
    ratio=printable/max(1,len(body))
    score=ratio*0.35 + magic*0.65
    return bytes(body), score

def _normalized_input(path: Path, out: Path):
    """Normalize known wrappers without ever modifying the original input."""
    raw = path.read_bytes()
    out.mkdir(parents=True, exist_ok=True)
    def _is_zlib_header(d: bytes) -> bool:
        return len(d) >= 2 and d[0] == 0x78 and (d[0] * 256 + d[1]) % 31 == 0

    payload = raw
    ci = None
    if _is_zlib_header(raw):
        payload, ci = unwrap_lua_container(raw)
    else:
        payload, ci = raw, None

    # Only remove a prefix that detector.py has classified as textual
    # comment/shebang lines; arbitrary binary prefixes remain untouched.
    from .detector import detect_bytes
    inner_info = detect_bytes(payload)
    offset = None
    for note in inner_info.notes:
        if note.startswith("comment_prefix_offset="):
            try:
                offset = int(note.split("=", 1)[1])
            except ValueError:
                offset = None
            break
    if offset is not None:
        payload = payload[offset:]
        from .container import ContainerInfo
        ci = ContainerInfo(True, "comment-prefix" if ci is None else ci.format,
                           1 if ci is None else ci.chunks, len(payload),
                           (f"comment prefix removed at offset {offset}",))
    elif not payload.startswith((b"\x1bLua", b"\x1bLJ")):
        if ci is None:
            return path, None
        raise ValueError("compressed container recovered, but payload is not Lua/LuaJIT")

    if ci is None:
        return path, None
    norm = out / (path.stem + "_normalized.luac")
    norm.write_bytes(payload)
    return norm, ci

def analyze_lua(path, out_dir=None, keys=None):
    p=Path(path); out=Path(out_dir) if out_dir else p.parent; out.mkdir(parents=True,exist_ok=True)
    raw=p.read_bytes(); container=None; work=p
    def _is_zlib_header(d: bytes) -> bool:
        return len(d) >= 2 and d[0] == 0x78 and (d[0] * 256 + d[1]) % 31 == 0

    try:
        if _is_zlib_header(raw):
            work, container = _normalized_input(p, out)
    except Exception as exc:
        return {"ok": False, "file": str(p), "format": "container-unknown",
                "size": len(raw), "error": str(exc)}
    info=detect_lua(work)
    result={"ok": info.kind != "unknown", "file": str(p), "format": info.format,
            "version": info.version, "size": len(raw), "confidence": info.confidence,
            "notes": list(info.notes), "obfuscation": []}
    if container:
        result["container"] = container.format
        result["container_chunks"] = container.chunks
        result["normalized_file"] = str(work)
    if info.kind == "unknown":
        result["error"]="not recognized as Lua source or bytecode"
        return result
    if info.kind == "source":
        from .detector import read_lua_text_strict
        try:
            text = read_lua_text_strict(work)
        except ValueError as exc:
            result["error"] = str(exc)
            return result
        patterns={
            "loadstring": r"\bloadstring\s*\(",
            "load": r"\bload\s*\(",
            "debug-library": r"\bdebug\.",
            "getfenv/setfenv": r"\b(?:getfenv|setfenv)\s*\(",
            "goto": r"\bgoto\b",
            "long-escaped-string": r"(?:\\x[0-9A-Fa-f]{2}){4,}",
            "dynamic-code": r"\b(?:assert|pcall|xpcall)\s*\(\s*(?:load|string\.dump)",
        }
        for name,pat in patterns.items():
            if re.search(pat,text): result["obfuscation"].append(name)
        result["source_lines"]=text.count("\n")+1
        return result
    result["strings_count"]=len(_extract_strings(work.read_bytes()))
    if info.format=="luajit": result["obfuscation"].append("LuaJIT-bytecode")
    if keys:
        candidates=[]
        for key in keys:
            if isinstance(key,str):
                try:key=bytes.fromhex(key)
                except ValueError:continue
            body,score=_xor_candidate(work.read_bytes(),key,0)
            candidates.append({"key":key.hex(),"score":round(score,4),
                               "lua_magic":body.startswith((b"\x1bLua",b"\x1bLJ"))})
        result["xor_candidates"]=sorted(candidates,key=lambda x:-x["score"])[:8]
    return result

def _pick_unluac_jar(jars_dir):
    """Find a supported unluac JAR without assuming a host-specific path."""
    if not jars_dir:
        return None
    root = Path(jars_dir)
    if not root.is_dir():
        return None
    preferred = ("unluac_2025_12_23.jar", "unluac_pro.jar",
                 "unluac_patched.jar", "unluac.jar")
    for name in preferred:
        candidate = root / name
        if candidate.is_file() and candidate.stat().st_size > 1000:
            return candidate
    for candidate in sorted(root.glob("unluac*.jar")):
        if candidate.is_file() and candidate.stat().st_size > 1000:
            return candidate
    return None


def decompile_lua(path, out_dir, jars_dir=None, timeout=120):
    p=Path(path); out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    if not p.is_file():
        return {"ok": False, "error": "input file not found", "file": str(p)}
    # Always initialize the destination: the bytecode fallback path must not
    # depend on the input being detected as source first.
    dest=out/(p.stem+"_decompiled.lua")
    info=detect_lua(p)
    normalized=p; container=None
    jar = _pick_unluac_jar(jars_dir)
    java = _find_java()
    jar_error = None if jar is not None else "unluac JAR not found in configured jars directory"
    try:
        raw_head = p.read_bytes()[:2]
        is_zlib = len(raw_head) == 2 and raw_head[0] == 0x78 and (raw_head[0] * 256 + raw_head[1]) % 31 == 0
        has_comment_prefix = any(note.startswith("comment_prefix_offset=") for note in info.notes)
        if is_zlib or has_comment_prefix:
            normalized, container = _normalized_input(p, out)
            info=detect_lua(normalized)
    except Exception as exc:
        return {"ok":False,"error":str(exc),"format":"container-unknown"}
    if info.kind == "source":
        # Preserve source inputs byte-for-byte at the text layer; this path is
        # not a bytecode decompilation and must not reject short valid scripts.
        # Byte-exact copy: a text round-trip here would rewrite line endings
        # and destroy any non-UTF-8 byte in the payload.
        dest.write_bytes(normalized.read_bytes())
        return {"ok": True, "mode": "source_passthrough", "out": str(dest),
                "format": info.format}

    if info.kind != "bytecode":
        return {"ok": False, "error": "input is not recognized Lua bytecode",
                "format": info.format, "version": info.version}

    def _try_streaming_fallback(reason):
        if info.format != "luac" or info.version != "Lua 5.3":
            return None
        try:
            from .streaming_decompiler import stream_decompile_lua53
            ok, msg = stream_decompile_lua53(normalized, dest)
            if ok:
                valid, validation = validate_lua_source(dest)
                if valid:
                    return {"ok": True, "mode": "decompiler53", "out": str(dest),
                            "format": info.format, "validation": validation,
                            "unluac_fallback_reason": reason,
                            **({"unwrapped": str(normalized), "container": container.format}
                               if container else {})}
                dest.unlink(missing_ok=True)
                return {"ok": False, "error": "streaming fallback output failed validation: " + validation}
            return {"ok": False, "error": "streaming fallback: " + str(msg)[:700]}
        except Exception as exc:
            dest.unlink(missing_ok=True)
            return {"ok": False, "error": "streaming fallback exception: " + str(exc)[:500]}

    if jar is None or not java:
        fallback = _try_streaming_fallback(jar_error or "Unluac unavailable")
        if fallback and fallback.get("ok"):
            return fallback
        if fallback:
            jar_error = (jar_error or "") + "; " + fallback.get("error", "")
        return {"ok": False, "error": jar_error or "no compatible decompiler backend",
                "format": info.format, "unluac_jar_error": jar_error,
                **({"unwrapped": str(normalized)} if container else {})}
    with tempfile.TemporaryDirectory(prefix="alv_lua_") as td:
        safe_in=Path(td)/"input.luac"; safe_jar=Path(td)/"unluac.jar"
        shutil.copy2(normalized,safe_in); shutil.copy2(jar,safe_jar)
        try:
            proc=subprocess.run([java,"-jar",str(safe_jar),str(safe_in)],
                                capture_output=True,text=True,errors="replace",timeout=timeout)
        except subprocess.TimeoutExpired:
            fallback = _try_streaming_fallback("Unluac timed out")
            if fallback and fallback.get("ok"):
                return fallback
            return {"ok":False,"error":"decompiler timeout" + ("; " + fallback.get("error", "") if fallback else ""),
                    "format":info.format, **({"unwrapped":str(normalized)} if container else {})}
    text=proc.stdout or ""
    stderr=(proc.stderr or "").strip()
    if proc.returncode != 0 or not text.strip():
        reason = stderr[:700] or "decompiler returned no source"
        fallback = _try_streaming_fallback("Unluac failed: " + reason)
        if fallback and fallback.get("ok"):
            return fallback
        return {"ok":False,"error":reason + ("; " + fallback.get("error", "") if fallback else ""),
                "returncode":proc.returncode,"format":info.format,
                **({"unwrapped":str(normalized),"container":container.format,
                    "container_chunks":container.chunks} if container else {})}
    dest.write_text(text,encoding="utf-8")
    valid,msg=validate_lua_source(dest)
    if not valid:
        dest.unlink(missing_ok=True)
        fallback = _try_streaming_fallback("Unluac output failed validation: " + msg)
        if fallback and fallback.get("ok"):
            return fallback
        return {"ok":False,"error":"decompiler output failed Lua structural validation: "+msg +
                ("; " + fallback.get("error", "") if fallback else ""),
                "returncode":proc.returncode,"format":info.format,
                **({"unwrapped":str(normalized)} if container else {})}
    return {"ok":True,"out":str(dest),"returncode":proc.returncode,
            "format":info.format,"validation":msg,
            **({"unwrapped":str(normalized),"container":container.format,
                "container_chunks":container.chunks} if container else {})}

def _safe_fold_numeric(text):
    # Only fold simple numeric-only expressions; never eval arbitrary Lua.
    pat=re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*([+\-*\/])\s*(\d+(?:\.\d+)?)(?![\w.])")
    def repl(m):
        a=float(m.group(1)); b=float(m.group(3)); op=m.group(2)
        try:
            v={"+":a+b,"-":a-b,"*":a*b,"/":a/b}[op]
        except (ZeroDivisionError,KeyError):
            return m.group(0)
        return str(int(v)) if v.is_integer() else repr(v)
    return pat.sub(repl,text)

def clean_lua_source(path, out_path):
    from .detector import read_lua_text_strict
    try:
        src = read_lua_text_strict(path)
    except ValueError as exc:
        return {"ok": False, "out": "", "validation": str(exc),
                "error": "refusing lossy text decode of binary input"}
    # Conservative transformations: comments/whitespace are preserved enough
    # for readability; no unsafe control-flow rewriting.
    cleaned=_safe_fold_numeric(src)
    cleaned=re.sub(r"[ \t]+\n","\n",cleaned)
    Path(out_path).parent.mkdir(parents=True,exist_ok=True)
    Path(out_path).write_text(cleaned,encoding="utf-8")
    ok,msg=validate_lua_source(out_path)
    return {"ok":ok,"out":str(out_path),"validation":msg}
