#!/usr/bin/env python3
"""ALVSIA Termux issue relay: owner-authored, read-only OpenCode tasks only."""
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = "ALVISIA8/alvsia-pro-550"
ISSUE = 97
POLL_SECONDS = 20
MAX_PROMPT = 6000
STATE = Path.home() / ".alvsia-agent-relay-state.json"
MARKER = "<!-- ALVSIA_TASK -->"

def run(args, timeout=30):
    return subprocess.run(args, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout)

def gh_json(path):
    p = run(["gh", "api", "--paginate", "--slurp", path], timeout=45)
    if p.returncode:
        raise RuntimeError("GitHub API request failed: " + p.stderr[-500:])
    pages = json.loads(p.stdout)
    return [item for page in pages for item in page]

def post(body):
    p = run(["gh", "api", "--method", "POST",
             f"repos/{REPO}/issues/{ISSUE}/comments", "-f", "body=" + body], timeout=45)
    if p.returncode:
        raise RuntimeError("Could not post relay result: " + p.stderr[-500:])

def task_from(body):
    if MARKER not in body:
        return None
    match = re.search(r"```json\s*(\{.*?\})\s*```", body, re.S)
    if not match:
        return None
    try:
        obj = json.loads(match.group(1))
    except Exception:
        return None
    if not isinstance(obj, dict) or obj.get("agent") != "opencode" or obj.get("mode") != "read_only":
        return None
    task_id, prompt = obj.get("id"), obj.get("prompt")
    if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", task_id):
        return None
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_PROMPT:
        return None
    return task_id, prompt.strip()

def main():
    if not STATE.exists():
        comments = gh_json(f"repos/{REPO}/issues/{ISSUE}/comments?per_page=100")
        last = max((int(c["id"]) for c in comments), default=0)
        STATE.write_text(json.dumps({"last_id": last}))
        STATE.chmod(0o600)
        print(f"Relay ready. Baseline comment ID: {last}. Waiting for new owner tasks.", flush=True)
    state = json.loads(STATE.read_text())
    last_id = int(state.get("last_id", 0))
    print(f"Polling issue #{ISSUE} every {POLL_SECONDS}s. Ctrl-C to stop.", flush=True)
    while True:
        try:
            comments = gh_json(f"repos/{REPO}/issues/{ISSUE}/comments?per_page=100")
            for c in sorted(comments, key=lambda x: int(x["id"])):
                cid = int(c["id"])
                if cid <= last_id:
                    continue
                last_id = cid
                state["last_id"] = last_id
                STATE.write_text(json.dumps(state))
                STATE.chmod(0o600)
                if c.get("user", {}).get("login", "").lower() != "alvisia8":
                    continue
                parsed = task_from(c.get("body", ""))
                if not parsed:
                    continue
                task_id, prompt = parsed
                print(f"Running task {task_id} with OpenCode (read-only policy)...", flush=True)
                safe_prompt = (
                    "READ-ONLY AUDIT TASK. Do not create, edit, delete, rename, or execute files. "
                    "Do not run shell commands that modify state, install packages, access credentials, "
                    "or contact external services. Only inspect and report.\n\nTASK:\n" + prompt
                )
                try:
                    result = run(["opencode", "run", "--format", "json", safe_prompt], timeout=900)
                    output = (result.stdout or "") + (("\nSTDERR:\n" + result.stderr) if result.stderr else "")
                    status = "completed" if result.returncode == 0 else f"failed (exit {result.returncode})"
                except subprocess.TimeoutExpired:
                    output, status = "Timed out after 15 minutes.", "timed out"
                output = output.strip()[-12000:] or "(No textual output.)"
                output = output.replace("```", "` ` `")
                post(f"## ALVSIA relay result — {task_id}\n\n**Status:** {status}\n\n"
                     f"```text\n{output}\n```")
                print(f"Task {task_id}: {status}; result posted.", flush=True)
        except KeyboardInterrupt:
            print("\nRelay stopped.", flush=True)
            return
        except Exception as exc:
            print("Relay warning: " + str(exc), flush=True)
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    if not shutil.which("gh") or not shutil.which("opencode"):
        print("Missing required CLI: gh and opencode must be installed.", file=sys.stderr)
        sys.exit(2)
    main()
