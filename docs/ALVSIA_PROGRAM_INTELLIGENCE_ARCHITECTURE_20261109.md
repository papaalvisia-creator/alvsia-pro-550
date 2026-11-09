# ALVSIA Program Intelligence Architecture — 2026-11-09

## Objective

Evolve ALVSIA from a collection of Lua utilities into a versioned **Program Intelligence Platform**. The first implementation slice is deliberately conservative: static, file-backed analysis with content-addressed artifacts, recursive layer discovery for safe containers, bounded budgets, and a knowledge registry.

## Architecture

`input → forensic fingerprint → layer graph → dialect/format evidence → adapter candidates → validation → knowledge update`

### Core invariants

1. Unknown input is never executed by the intelligence core.
2. Every artifact is hashed with SHA-256 and linked to its parent.
3. Intermediate data is file-backed; the original input is never modified.
4. Recursive expansion is bounded by depth, artifact count, size and elapsed time.
5. A high entropy score is evidence only, never a decompile success condition.
6. Missing symbols/debug names are reported as unknown rather than invented.
7. New engines must be adapters with tests and provenance, not ad-hoc branches.

## Capability registry

The registry is versioned for future growth across:

- Lua 5.1–5.5
- LuaJIT
- Luau
- vendor/custom dialects
- bytecode/container formats
- obfuscation fingerprints
- VM patterns
- string/data encodings
- compiler/runtime oracles
- regression corpus

## Long-term layers

### Phase A — Foundation
- recursive layer graph
- deterministic fingerprints
- file-backed intermediates
- safety/resource budgets
- machine-readable reports

### Phase B — Recovery
- multiple decompiler candidates
- candidate scoring from structural evidence
- compiler/parser validation
- semantic equivalence checks
- dialect-specific adapters

### Phase C — Protection
- parser/AST transforms
- scope-aware transformations
- real compiler adapters
- authenticated encryption/key lifecycle
- optional VM backend
- differential protection tests

### Phase D — Research loop
- reproducible fixtures
- fuzzing and differential testing
- failure taxonomy
- benchmark dashboards
- reviewed knowledge updates

The system is intentionally designed so later research can add adapters without rewriting the orchestration layer.
