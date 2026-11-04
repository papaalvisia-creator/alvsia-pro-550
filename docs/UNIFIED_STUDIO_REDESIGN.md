# ALVSIA PRO — Seven Studio Navigation & Connected Workspace Plan

## Decision

The client-facing navigation uses seven Studios while preserving the existing 19-module catalog and all legacy module IDs. This is a presentation/navigation layer, not a rewrite of the tool engines.

## Studio-to-module mapping

| Studio | Existing module IDs | Existing modules |
|---|---:|---|
| PAK Studio | 1, 2, 3, 14 | PAK Unpack, PAK Rebuild, PAK Compact, PAK Deep |
| OBB Studio | 4 | OBB Tools |
| Lua Studio | 5, 15, 16, 18 | LUA Tools, String Recover, Lua Inject, Lua Protector |
| File Studio | 6, 7 | File Scan, Workspace |
| Security Studio | 10, 11, 17 | SO Analyzer, Frida Tracer, Anti-RE Audit |
| Crypto Studio | 12, 13, 19 | XOR Suite, Decrypt Engine, ALVSIA PRIVATE TOOL |
| Project Studio | 8, 9 | Export Report, Rebrand |

The catalog must cover IDs 1 through 19 exactly once. The private module remains the existing module 19 and must continue to use its current sealed-runtime/authorization gate; grouping it in a Studio does not broaden its access.

## Navigation behavior

1. Dashboard displays seven Studio cards instead of nineteen top-level module cards.
2. Opening a Studio lists its existing modules.
3. Selecting a module enters the existing SubMenuScreen.
4. Selecting a sub-tool enters the existing ToolWorkspaceScreen.
5. Back navigation returns to the originating Studio; Quick Actions return to the Dashboard.
6. Dashboard search continues to find legacy modules directly.

## Connected-workspace target (subsequent implementation phases)

- Quick Tools Mode: launch a module directly without creating a project.
- Project Mode: create a named project and associate inputs, outputs, reports and task history.
- Shared Workspace: pass an explicit output artifact to another compatible Studio without re-selecting or silently rewriting it.
- Workflow handoff: each step records source hash, output hash, tool ID, parameters (excluding secrets), status and validation result.
- Safety: never mutate the original input by default; stage work in a dedicated output/work area; reject unsupported formats rather than reporting success.

## Unified process-page target

All tools should share a consistent interaction shell: input selection, format detection, only relevant configuration fields, Run/Cancel state, progress/status, output actions and logs. Simple mode explains outcomes in client language; Advanced mode exposes technical logs and parameters. Existing sub-tool-specific configuration and authorization checks remain authoritative.

## Non-negotiable compatibility rules

- Do not renumber or remove the 19 existing module IDs or sub-tool IDs.
- Do not bypass SessionGate, signed operation grants, private-module sealing, permission checks or file-safety checks.
- Do not change package identity, Android permissions, panel endpoints, TLS pins, or release signing configuration as part of UI regrouping.
- Keep binary/bytecode operations byte-preserving; never route binary payloads through lossy UTF-8 text conversion.
- A UI grouping or CI success is not proof that every tool works on a physical device.

## Acceptance gates

1. Unit/static test proves exactly seven Studios and a unique mapping of all module IDs 1..19.
2. Android debug unit tests and assembleDebug pass.
3. Existing Python dispatch, Lua, crypto, PAK/OBB, private-tool and release-safety tests pass.
4. Each of the 19 modules is smoke-tested with valid and invalid fixtures; expected output, input preservation and error reporting are checked.
5. Signed release APK passes package/version, signature, ZIP integrity and native-library alignment checks.
6. Physical-device install and runtime smoke tests pass before calling the redesign production-ready.
