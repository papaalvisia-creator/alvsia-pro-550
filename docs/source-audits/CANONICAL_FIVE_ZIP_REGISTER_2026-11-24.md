# Canonical ALVSIA SMART TOOL source archive register

Date: 2026-11-24  
Repository: https://github.com/papaalvisia-creator/ALVSIA_ORIGINAL_TOOL_ARCHIVES_2026  
Commit inspected: 19d344063109c73c36a3ab419a387a57093864cc

These are the five canonical source archives specified by the project owner. They supersede any earlier mistaken archive-name mapping in working notes.

| # | Canonical archive | Owner-reported file count | GitHub blob SHA | Size (bytes) |
|---:|---|---:|---|---:|
| 1 | `IkramTool_V130_4.7.zip` | 1,585 | `6f4e8feb86648500d6cb5c03f3cad87d314de868` | 46,371,828 |
| 2 | `TOOL.zip` | 61 | `b22efa3081b5013a6c4aa64a2dcb83d1cc79bca7` | 1,124,058 |
| 3 | `RegulerResault_ALVSIA_tool_no_on_vip_engine.zip` | 2,080 | `bde701a0365cd63ed55da718178c5ce532fa4b48` | 30,503,921 |
| 4 | `MANKS-TOOL_ALVSIA.zip` | 11 | `594f141fe19ea208751a77f523b2d946d03773f8` | 1,068,904 |
| 5 | `_workspace_ALVSIA_TOOL_PREMIUM_v4.0.1.zip` | 52 | `13ecc72c3c6f14c74c564062b4bd6e4f9029fe52` | 10,191,730 |
| | **Total** | **3,789** | | **89,260,441** |

## Owner-reported contents

- IkramTool: 1,272 Python files, 19 Lua files, plus binaries, JARs and dependencies.
- TOOL.zip: includes `tool.py` (~1.22 MB) and PAK/Lua test examples.
- RegulerResault: 750 Lua, 580 UEXP, 558 UASSET, 129 LOCRES and 21 UMAP files.
- MANKS-TOOL: `MANKS.py`, two JAR decompilers, `luadec`, `luac5.3`, and SM4.
- Workspace Premium: 52 files.

The owner-reported type counts above are retained as supplied. They have not been independently recalculated from raw archive contents in this commit.

## Verification boundary

Verified from GitHub metadata:
- The archive repository exists and is accessible.
- Its main-branch tree contains exactly these five archive paths.
- Each archive's Git blob SHA and byte size match the table above.

Not yet verified in this runner:
- Downloading and opening the binary ZIP payloads.
- Recomputing SHA-256/ZIP CRC from downloaded bytes.
- Recursive extraction and independent recount of every nested file.

The GitHub connector exposes the archive names, sizes, and blob IDs, but the binary payloads were not available as mounted local files in this runner. Do not claim a full byte-level audit until the ZIP bytes are actually extracted and checked.

## Integration rules

1. Preserve all useful functions from the five canonical archives.
2. Compare implementations by behavior and test vectors before deduplicating.
3. Port only reviewed, safe components; do not execute opaque marshal/base64 payloads during inventory.
4. Do not port destructive routines, mass-delete behavior, or hard-crash behavior.
5. Do not treat Windows-only EXE/DLL components as Android ARM64 engines.
6. Map each verified capability into the approved 10-menu / 59-submenu contract, while strengthening the existing baseline features.
