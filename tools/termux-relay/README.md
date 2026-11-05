# ALVSIA Termux Agent Relay

This branch contains a conservative first relay stage.

## Current adapter status

- OpenCode: supported by the worker when the `opencode` CLI is installed.
- Zro: launcher/router only at this stage; the inspected device did not have the native Claude or Codex binaries.
- Agent Zero: source exists in Debian, but no running instance was detected. It is not called by this worker.

## Run on Termux

From the existing repository checkout:

```bash
cd "$HOME/alvsia-pro-550" || exit 1
git fetch origin infra/termux-agent-relay || exit 1
mkdir -p "$HOME/.alvsia-agent-relay"
git show FETCH_HEAD:tools/termux-relay/relay.py > "$HOME/.alvsia-agent-relay/relay.py" || exit 1
chmod 700 "$HOME/.alvsia-agent-relay/relay.py"
python3 "$HOME/.alvsia-agent-relay/relay.py"
```

The first start records the current highest comment ID and waits for new tasks. Keep the process running while using the relay. Stop with Ctrl-C. It polls issue #97 every 20 seconds. GitHub CLI authentication and OpenCode must already work locally.

## Send a task

Post a new comment to [issue #97](https://github.com/ALVISIA8/alvsia-pro-550/issues/97) in this exact format:

```markdown
<!-- ALVSIA_TASK -->
```json
{
  "id": "audit-001",
  "agent": "opencode",
  "mode": "read_only",
  "prompt": "Inspect the requested area and report findings. Do not modify files."
}
```
```

Only comments authored by the repository owner account `ALVISIA8` are considered. Only the `opencode` adapter and `read_only` mode are accepted. The worker never treats task text as a shell command. Results are posted back as a new issue comment.

## Security and scope

- No passwords, API tokens, private keys, keystores, environment-variable values, or license data are read or transmitted by the worker.
- No arbitrary shell execution is exposed through GitHub.
- The worker instructs OpenCode to inspect/report only; this is a conservative first-stage policy, not a hardened OS sandbox.
- Do not use it for source edits, commits, builds, signing, or releases.
- Agent Zero and additional Zro adapters are intentionally not enabled until their actual runtime/CLI is installed and verified.
- The relay runs under the Termux user's home directory and does not modify ALVSIA services or ports.
