# Friend Tool -> ALVSIA Capability Gap Audit

Date: 2026-11-14
Source: authorized friend-tool research archive (private research repository)
ALVSIA branch: feat/alvsia-unified-engine-7x19-20261113

## Decision

The friend tool is treated as an authorized research/reference source. We reuse technical concepts and implementation patterns where they improve ALVSIA, but we do not import its server/panel/authentication system, credentials, tokens, private keys, license secrets, telemetry endpoints, or game-specific secret material.

## Capability comparison

| Capability found in research source | ALVSIA before this pass | Decision |
|---|---|---|
| SM4 software implementation | Present through existing decrypt/PAK paths | Keep and strengthen as an internal provider; do not copy embedded secrets |
| Native SM4 acceleration | Partial/legacy provider coverage | Research candidate for internal acceleration layer |
| AES/SHA1 transforms | Present | Keep as adapters with validation |
| ZUC/custom stream transforms | Present as labelled compatibility paths | Keep, clearly distinguish standards-compliant vs compatibility transforms |
| zlib/zstd/ZSTD dictionaries | Present in PAK/deep paths | Consolidate into compression intelligence |
| Binary ASCII/UTF-16/context scanning | Partial | Strengthen as cross-domain capability |
| Entropy/pattern candidate ranking | Partial | Strengthen as fingerprint/scoring capability |
| UE-style asset/ID/context workflows | Missing as a dedicated visible Smart Engine | **Added SMART ASSET MODDING ENGINE (provider 20)** |
| Skin / hit / crate / atmosphere workflow concepts | Missing as one unified Smart Asset workflow | Keep as future internal profiles; no hardcoded game secrets |
| ZSDIC-style ID replacement | Missing as generic Smart capability | Added safe user-supplied equal-length mapping patch |
| Safe post-change validation | Partial | Added to Smart Asset provider |
| Runtime dependency auto-install | Not desired | Reject; ALVSIA remains bundled/pinned/offline-safe |
| Friend server/panel/login | Not part of ALVSIA architecture | Explicitly rejected |
| Friend license/credential material | Not part of ALVSIA architecture | Explicitly rejected |

## Smart Asset Engine v1

Visible submenu:
- SMART ASSET MODDING ENGINE

Internal operations:
- asset_fingerprint
- asset_scan_ids
- asset_context
- asset_patch
- asset_validate

Safety rules:
- source input is never overwritten;
- modification mappings must be user-supplied;
- old/new byte sequences must have identical lengths;
- output is written separately;
- SHA-256 evidence is emitted;
- input size is bounded;
- no server communication is used;
- no embedded game secret is required.

## What is intentionally not claimed yet

The friend tool contains game-specific workflows and hardcoded material. Their presence in the source is not proof that every menu path is universally functional. ALVSIA will not claim complete UE4/UAsset parsing, universal skin conversion, or game-specific repacking until real fixtures prove those paths.

## Next engineering targets

1. Build a common Crypto Fingerprint capability behind SMART DATA / SMART PAK DEEP.
2. Build a common Compression Intelligence capability behind PAK/DATA.
3. Upgrade binary context scanning and confidence scoring across Lua/SO/DATA/Asset workflows.
4. Add real UE asset fixtures before implementing deeper UAsset/UEXP mutation.
5. Run malformed-input, path-traversal, oversized-input, and output-integrity tests.
6. Only after these gates pass, consider additional visible submenu expansion.
