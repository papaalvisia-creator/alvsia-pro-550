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

def _looks_like_lua_source(text: str) -> bool:
    if not text.strip():
        return False
    # Reject obvious binary garbage while allowing UTF-8 source/comments.
    sample = text[:8192]
    bad = sum(1 for c in sample if ord(c) < 9 or (13 < ord(c) < 32))
    if bad > max(2, len(sample)//100):
        return False
    return bool(re.search(r"\b(?:local|function|return|if|for|while|repeat|do|end)\b", sample))

def validate_lua_source(path_or_text) -> tuple[bool, str]:
    if isinstance(path_or_text, (str, Path)) and Path(str(path_or_text)).is_file():
        text = Path(path_or_text).read_text(encoding="utf-8", errors="replace")
    else:
        text = str(path_or_text)
    if not _looks_like_lua_source(text):
        return False, "output does not look like Lua source"
    # Lightweight structural validation; Lua grammar is not Python grammar.
    pairs = {"end": 0, "function": 0, "if": 0, "for": 0, "while": 0, "do": 0}
    tokens = re.findall(r'(?<![%\w_])(function|if|for|while|repeat|do|end|until)(?![\w_])', text)
    stack = []
    for tok in tokens:
        if tok in ("function", "if", "for", "while", "do", "repeat"):
            stack.append(tok)
        elif tok == "until":
            if not stack or stack[-1] != "repeat":
                return False, "unmatched until"
            stack.pop()
        elif tok == "end":
            if not stack:
                return False, "unmatched end"
            stack.pop()
    if stack:
        return False, "unclosed Lua block(s): " + ",".join(stack[-8:])
    return True, "syntax structure looks consistent"

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
    elif not payload.startswith((b"\\x1bLua", b"\\x1bLJ")):
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
        text=work.read_text(encoding="utf-8",errors="replace")
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

def decompile_lua(path, out_dir, jars_dir=None, timeout=120):
    p=Path(path); out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    info=detect_lua(p)
    normalized=p; container=None
    try:
        raw_head = p.read_bytes()[:2]
        is_zlib = len(raw_head) == 2 and raw_head[0] == 0x78 and (raw_head[0] * 256 + raw_head[1]) % 31 == 0
        has_comment_prefix = any(note.startswith("comment_prefix_offset=") for note in info.notes)
        if is_zlib or has_comment_prefix:
            normalized, container = _normalized_input(p, out)
            info=detect_lua(normalized)
    except Exception as exc:
        return {"ok":False,"error":str(exc),"format":"container-unknown"}
    if info.kind=="source":
        dest=out/(p.stem+"_decompiled.lua")

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
    src=Path(path).read_text(encoding="utf-8",errors="replace")
    # Conservative transformations: comments/whitespace are preserved enough
    # for readability; no unsafe control-flow rewriting.
    cleaned=_safe_fold_numeric(src)
    cleaned=re.sub(r"[ \t]+\n","\n",cleaned)
    Path(out_path).parent.mkdir(parents=True,exist_ok=True)
    Path(out_path).write_text(cleaned,encoding="utf-8")
    ok,msg=validate_lua_source(out_path)
    return {"ok":ok,"out":str(out_path),"validation":msg}
