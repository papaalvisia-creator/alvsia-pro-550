#!/usr/bin/env python3
"""Read-only, non-executing audit for ALVSIA's five canonical source ZIPs."""
from __future__ import annotations
import ast, hashlib, io, os, tokenize, urllib.request, urllib.parse, zipfile
from collections import Counter, defaultdict
from pathlib import Path

ARCHIVES = [
 {"name":"IkramTool_V130_4.7.zip","expected":1585,"size":46371828,"blob":"6f4e8feb86648500d6cb5c03f3cad87d314de868"},
 {"name":"TOOL.zip","expected":61,"size":1124058,"blob":"b22efa3081b5013a6c4aa64a2dcb83d1cc79bca7"},
 {"name":"RegulerResault_ALVSIA_tool_no_on_vip_engine.zip","expected":2080,"size":30503921,"blob":"bde701a0365cd63ed55da718178c5ce532fa4b48"},
 {"name":"MANKS-TOOL_ALVSIA.zip","expected":11,"size":1068904,"blob":"594f141fe19ea208751a77f523b2d946d03773f8"},
 {"name":"_workspace_ALVSIA_TOOL_PREMIUM_v4.0.1.zip","expected":52,"size":10191730,"blob":"13ecc72c3c6f14c74c564062b4bd6e4f9029fe52"},
]
BASE="https://raw.githubusercontent.com/papaalvisia-creator/ALVSIA_ORIGINAL_TOOL_ARCHIVES_2026/main/"
REPORT=Path("reports/canonical-archive-audit.md")
MAX_ENTRY=256*1024*1024
MAX_TOTAL=1024*1024*1024
MAX_DEPTH=3
hashes=defaultdict(list)
py=Counter()
flags=[]
nested_count=0
uncompressed=0

def git_blob(data):
 return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()

def download(item):
 url=BASE+urllib.parse.quote(item["name"])
 req=urllib.request.Request(url,headers={"User-Agent":"ALVSIA-Archive-Audit/1.0"})
 with urllib.request.urlopen(req,timeout=120) as response: data=response.read()
 if len(data)!=item["size"]: raise RuntimeError(f"size mismatch: {len(data)} != {item['size']}")
 actual=git_blob(data)
 if actual!=item["blob"]: raise RuntimeError(f"Git blob mismatch: {actual}")
 return data

def parse_python(raw,label):
 py["files"]+=1
 if len(raw)>8*1024*1024:
  py["over_8mb"]+=1; return
 try:
  enc,_=tokenize.detect_encoding(io.BytesIO(raw).readline)
  tree=ast.parse(raw.decode(enc),filename=label)
  py["ast_pass"]+=1
 except (SyntaxError,UnicodeError,LookupError,tokenize.TokenError):
  py["ast_fail"]+=1; return
 for node in ast.walk(tree):
  if not isinstance(node,ast.Call): continue
  cur=node.func; parts=[]
  while isinstance(cur,ast.Attribute): parts.append(cur.attr); cur=cur.value
  if isinstance(cur,ast.Name): parts.append(cur.id)
  dotted=".".join(reversed(parts))
  if dotted in {"exec","eval","marshal.loads","pickle.loads","os.system","subprocess.Popen","subprocess.run","subprocess.call"}:
   flags.append((label,"manual review: "+dotted))

def inspect(data,label,depth=0):
 global nested_count,uncompressed
 out={"label":label,"files":0,"dirs":0,"crc":"PASS","ext":Counter(),"nested":[]}
 if depth>MAX_DEPTH: out["crc"]="SKIP: nested depth limit"; return out
 try:
  with zipfile.ZipFile(io.BytesIO(data)) as z:
   bad=z.testzip()
   if bad: out["crc"]="FAIL: "+bad
   for info in z.infolist():
    if info.is_dir(): out["dirs"]+=1; continue
    out["files"]+=1
    suffix=Path(info.filename).suffix.lower() or "[none]"
    out["ext"][suffix]+=1
    if info.file_size>MAX_ENTRY:
     flags.append((label+"!/"+info.filename,"entry over 256 MiB")); continue
    uncompressed+=info.file_size
    if uncompressed>MAX_TOTAL: raise RuntimeError("total uncompressed-size safety limit exceeded")
    try: raw=z.read(info)
    except Exception as exc:
     flags.append((label+"!/"+info.filename,"read error: "+str(exc))); continue
    if suffix==".py": parse_python(raw,label+"!/"+info.filename)
    if suffix==".zip":
     nested_count+=1
     if depth<MAX_DEPTH: out["nested"].append(inspect(raw,label+"!/"+info.filename,depth+1))
    hashes[hashlib.sha256(raw).hexdigest()].append(label+"!/"+info.filename)
 except (zipfile.BadZipFile,OSError,RuntimeError) as exc:
  out["crc"]="ERROR: "+str(exc)
 return out

def main():
 results=[]; failed=[]
 Path("build/archive-audit").mkdir(parents=True,exist_ok=True)
 for item in ARCHIVES:
  print("Downloading "+item["name"],flush=True)
  try:
   data=download(item)
   Path("build/archive-audit",item["name"]).write_bytes(data)
   r=inspect(data,item["name"])
   r.update(expected=item["expected"],size=len(data),sha256=hashlib.sha256(data).hexdigest())
   results.append(r)
   if not r["crc"].startswith("PASS"): failed.append(item["name"])
  except Exception as exc:
   results.append({"label":item["name"],"expected":item["expected"],"crc":"FAIL: "+str(exc)})
   failed.append(item["name"])
 duplicates=[v for v in hashes.values() if len(v)>1]
 lines=["# Canonical ALVSIA five-ZIP audit","","Read-only audit; no source or binary payload is executed.","",
 f"- Archives checked: {len(results)}/5",f"- Nested ZIPs found: {nested_count}",
 f"- Total uncompressed bytes read: {uncompressed}",f"- Python files parsed: {py['files']}",
 f"- Python AST pass: {py['ast_pass']}",f"- Python AST/encoding failures: {py['ast_fail']}",
 f"- Python files skipped over 8 MiB: {py['over_8mb']}",f"- Duplicate-content groups: {len(duplicates)}","",
 "| Archive | Actual files | Owner-reported | CRC | Bytes | SHA-256 |","|---|---:|---:|---|---:|---|"]
 for r in results:
  lines.append("| {} | {} | {} | {} | {} | {} |".format(r["label"],r.get("files","n/a"),r["expected"],r["crc"],r.get("size","n/a"),r.get("sha256","n/a")))
 lines+=["","## Extensions by archive",""]
 for r in results:
  lines += ["### "+r["label"],""]
  ext=r.get("ext",Counter())
  lines.append(", ".join(f"{k}: {v}" for k,v in sorted(ext.items(),key=lambda x:(-x[1],x[0]))[:30]) or "No entries counted.")
  for n in r.get("nested",[]): lines.append("- Nested "+n["label"]+": "+str(n.get("files","n/a"))+" files; CRC "+n["crc"])
  lines.append("")
 lines+=["","## Duplicate-content groups",""]
 lines += ["- "+" | ".join(v) for v in duplicates] if duplicates else ["None detected."]
 lines+=["","## Manual-review flags",""]
 lines += ["- "+name+": "+note for name,note in flags] if flags else ["No heuristic flags detected; this is not a safety certification."]
 lines+=["","## Safety notes","",
 "- ZIP entries are inspected in memory; archive paths are not extracted.",
 "- Python files are parsed with AST only; no imports, exec, eval, marshal or pickle payloads are run.",
 "- Calls to dynamic execution/deserialization/process launch are flagged for human review.",
 "- Owner-reported file counts are compared with direct ZIP entry counts; differences may reflect nested ZIPs or directory counting.",
 "- CRC PASS confirms ZIP integrity only, not correctness or safety.",
 "", "Overall archive download/CRC result: **"+("FAIL" if failed else "PASS")+"**."]
 REPORT.parent.mkdir(parents=True,exist_ok=True)
 REPORT.write_text("\n".join(lines)+"\n",encoding="utf-8")
 summary=os.environ.get("GITHUB_STEP_SUMMARY")
 if summary:
  with open(summary,"a",encoding="utf-8") as f: f.write(REPORT.read_text(encoding="utf-8"))
 print(REPORT.read_text(encoding="utf-8"))
 return 1 if failed else 0

if __name__=="__main__": raise SystemExit(main())
