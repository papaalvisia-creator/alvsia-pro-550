# ALVSIA Smart Lua — Universal Coverage Research Addendum

Research date: 2026-11-09  
Repository: `papaalvisia-creator/alvsia-pro-550`  
Working branch: `feat/lua-intelligence-orchestrator-20261107`

## Product requirement

Smart Lua is one universal workflow, not a collection of game-specific tools. It must identify and process Lua-family inputs by evidence: container, dialect, bytecode version, VM/compiler traits, wrapper/protector family, and confidence. Known examples are regression fixtures, not the product's supported-input boundary.

"Universal" means extensible format and engine coverage with honest outcomes. It does **not** mean promising recovery of every unknown or cryptographically protected payload. The tool must never fabricate source or call a disassembly/constants dump a full decompile.

## Research findings

### Dialect coverage

The official Lua reference manuals cover PUC Lua 5.1–5.5. These are distinct compiler/bytecode generations and require version-aware parsing and validation:
- https://lua.org/manual/
- https://lua.org/source/5.4/

Other Lua-family dialects must remain separate compatibility families:
- LuaJIT 2.0 and 2.1
- Luau bytecode, with version/build-specific opcode behavior
- GLua / Garry's Mod dialect extensions
- Embedded or vendor-patched Lua VMs, which may change headers, opcodes, constants, serialization, or runtime semantics.

A file extension or game name is never sufficient evidence of a dialect.

### Candidate engines and research references

1. **x3zvawq/unluac-rs** — upstream advertises automatic detection and decompilation for PUC Lua 5.1–5.5, LuaJIT 2.1 and Luau v3–v7. The pinned v1.4.4 Android ARM64 candidate has now passed the branch's host fixture suite and ELF validation. It remains a candidate until the binary is packaged into an app build and exercised on Android.
   - https://github.com/x3zvawq/unluac-rs
   - License: MIT; preserve upstream notice and exact pinned provenance.
2. **PumbaaDev/luau-decompiler** — separate Luau engine, pinned in the candidate workflow; branch CI generated and tested genuine Luau v7/v9 fixtures and built Android ABI candidates. It is not a PUC Lua decompiler.
   - https://github.com/PumbaaDev/luau-decompiler
   - License and pinned commit are verified in the candidate workflow.
3. **zhangjiequan/luadec** — potential additional Lua 5.1 native engine and experimental 5.2/5.3 path. Keep separate until revision, license, Android build, and version-specific fixtures are verified.
   - https://github.com/zhangjiequan/luadec
4. **Disrobe** — useful public documentation reference for layered unpacking, family catalogs, fidelity labels, and explicit per-family evidence. **Do not copy, bundle, adapt, or use its source as an implementation base.** Its current Source-Available License 1.1 is proprietary, requires paid written permission for use by/for a for-profit organization, and includes a competing-development restriction.
   - https://github.com/1-3-7/disrobe
   - https://github.com/1-3-7/disrobe/blob/main/LICENSE
5. **Lua Obfuscator Corpus** — research dataset with 26,357 Lua/Luau samples across 17 obfuscator labels. Its CC BY-SA 4.0 terms require attribution and share-alike for derivatives. Do not bundle corpus files or derive a proprietary product dataset from it without resolving those obligations. It may be used only after a deliberate legal/data-use review.
   - https://huggingface.co/datasets/bartholomort/lua-obfuscator-corpus

### Important fidelity limit

Compiled bytecode often omits comments, original formatting, and debug/local-name metadata. A correct decompiler can reconstruct semantically equivalent Lua while not recovering the exact original source text. Reports must distinguish:
- `LOSSLESS`: evidence supports byte-/structure-preserving recovery for the relevant transformation.
- `SEMANTIC`: valid source with equivalent behavior, but formatting/comments/names may differ.
- `PARTIAL`: some layers, functions, or VM structure recovered; source remains incomplete.
- `DISASSEMBLY`: instructions/IR only, not reconstructed source.
- `STRINGS_ONLY`, `UNSUPPORTED`, and `FAILED`.

## Required architecture

### 1. Evidence-based intake and detection
- Preserve the original input and compute its hash before processing.
- Inspect bounded headers and signatures first; do not load a multi-megabyte file repeatedly just to identify it.
- Return a structured detection record: format, dialect, version/build if known, wrapper candidates, confidence, byte offsets, and evidence.
- Keep PUC Lua, LuaJIT, Luau, GLua, containers, and unknown/custom VM families distinct.

### 2. Recursive layer graph, not a single linear unwrap
Represent every recovered artifact as a node with parent hash, transform/engine, detected format, output hash, byte sizes, and validation. Each successful transform becomes a new candidate input and is re-detected. Continue while a supported transformation makes measurable progress, with:
- cycle detection by content hash;
- maximum depth and total expanded-byte budgets;
- per-engine time and memory ceilings;
- isolated temporary outputs and atomic publication;
- preservation of intermediate layers and diagnostics;
- no execution of the target script by default.

This supports chains such as container → encrypted/wrapped payload → custom VM bytecode → standard Lua bytecode → reconstructed source, without assuming every file follows that order.

### 3. Pluggable engine contract
Every engine adapter must declare:
- stable engine ID, version, source URL/revision, license and notice;
- supported dialects, bytecode versions, wrapper/protector families, and ABI;
- detection evidence and confidence;
- input/output artifact types;
- invocation contract, timeout, memory and output budgets;
- whether it produces source, bytecode, IR, disassembly, constants, or diagnostics;
- validation method and known limitations.

Engines must not be selected only because their names contain "Lua". A LuaJIT disassembler cannot be registered as a source decompiler.

### 4. Recursive recovery and VM analysis
- Re-detect every extracted/decrypted/decompressed candidate.
- Re-run compatible standard decompilers on each newly exposed bytecode layer.
- For custom VMs, use a separate static-analysis route: identify dispatcher/handler structure, instruction encoding, opcode mapping, operand/constant representation, control flow, and nested prototypes. Preserve uncertainty; only emit lifted source when the mapping and output pass independent validation.
- Do not claim generic L1/L2/L3 support from layer numbering alone. Layer labels are user observations, not a known universal format.

### 5. Large-file design
- Stream file copies, hashes, decompression, scans, and report generation.
- Avoid `Path.read_bytes()` for large inputs and avoid simultaneous full-size copies.
- Use file-backed intermediate artifacts and explicit expansion limits.
- Measure peak RSS, elapsed time, input/output bytes, and layer count.
- Test both 5.4 MB input and generated 50 MB+ output, then scale tests separately.
- Never truncate or silently drop output to satisfy memory limits.

### 6. Validation and selection
- Prefer the matching official compiler/parser for the detected dialect and bytecode version.
- Where possible, compile recovered source and compare behavior against a safe fixture/original known source; never run an unknown target as the default validation mechanism.
- Validate syntax, prototype/function structure, constants, control flow, and output completeness.
- Compare independent engine results; preserve alternatives when useful.
- Structural token balancing alone is not release-grade validation.

## Immediate engineering gates

1. **Package and runtime-test native candidates.** Current candidate workflow success proves host fixtures and Android ELF shape, not Android execution or APK inclusion.
2. **Prove actual bridge-to-binary dispatch.** Verify executable permissions, linker invocation, ABI selection, process output/exit handling, and app-private paths on Android ARM64.
3. **Fix large-file memory duplication.** Audit `detect_lua`, `stream_decompile_lua53`, `decompile_large`, and every engine adapter for full-file copies.
4. **Implement recursive artifact graph.** A single deobfuscator return value must not end the run until its output is re-detected and processed.
5. **Expand dialect fixtures and engine registry.** Add Lua 5.1–5.5, LuaJIT 2.0/2.1, Luau version/build fixtures, malformed files, stripped debug info, wrappers, and unknown VM cases.
6. **Add authorized multi-layer regression fixtures.** Test L1/L2-style chains using ALVSIA-owned synthetic fixtures and user-authorized samples; assert every intermediate hash and final fidelity grade.
7. **Do not build/release an APK yet.** First pass source tests, host engine fixtures, Android native runtime tests, the uploaded 5.4 MB regression sample, and a 50 MB+ generated-output stress test.

## Verified candidate workflow checkpoint

On 2026-11-09, commit `d824f3bc3094b56591f6721c982fcda54cece6af` passed:
- Smart Lua Python Validation
- Smart Lua Native Engines Android ARM64 Candidate
- Lua 5.1–5.5, LuaJIT 2.1 and Luau v7/v9 host fixture checks
- Android ARM64/x86_64 ELF validation and SHA-256 manifest checks

Candidate artifact:
https://github.com/papaalvisia-creator/alvsia-pro-550/actions/runs/42598839152/artifacts/13665751430

This checkpoint does not establish on-device execution, packaged APK integration, universal obfuscator recovery, or successful decompilation of the user's 5.4 MB sample.

## References

- Lua official manuals: https://lua.org/manual/
- Lua 5.4 official source: https://lua.org/source/5.4/
- unluac-rs: https://github.com/x3zvawq/unluac-rs
- PumbaaDev Luau decompiler: https://github.com/PumbaaDev/luau-decompiler
- luadec: https://github.com/zhangjiequan/luadec
- Disrobe documentation and license (reference only; do not reuse implementation): https://github.com/1-3-7/disrobe
- Lua Obfuscator Corpus terms: https://huggingface.co/datasets/bartholomort/lua-obfuscator-corpus
