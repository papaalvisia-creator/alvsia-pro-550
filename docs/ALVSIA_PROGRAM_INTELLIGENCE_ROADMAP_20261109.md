# ALVSIA Program Intelligence Roadmap

This roadmap turns the long-term architecture into measurable engineering gates.

## Gate 1 — Foundation
- recursive artifact graph
- provenance and SHA-256 identity
- bounded resource budgets
- deterministic fingerprints
- knowledge registry
- regression tests
- CI

**State:** implemented on the active feature branch.

## Gate 2 — Universal Program IR
- dialect-neutral program IR
- adapters from each supported decoder/decompiler
- CFG/data-flow representations
- source mapping and uncertainty
- serialized IR fixtures

**State:** IR schema + conservative source/header adapters implemented; deep bytecode structural evidence is now attached to the recursive artifact graph. Full instruction-level adapters remain a required acceptance item.

## Gate 3 — Multi-Hypothesis Recovery
- candidate outputs from independent engines
- evidence scoring
- parser/compiler validation
- semantic comparison
- no false SUCCESS

**State:** candidate evidence/ranking, deterministic multi-engine fusion, parser/compiler oracle hooks, and bounded semantic differential validation are implemented. Deep-scan success now requires semantic consensus when multiple engines produce outputs. Compiler-backed acceptance and corpus-wide differential validation remain required.

## Gate 4 — Differential Runtime Lab
- reference fixtures
- deterministic runtime probes
- cross-dialect behavioral fingerprints
- regression corpus

## Gate 5 — Smart Protector
- parser/AST transforms
- scope-aware transforms
- genuine compiler adapters
- authenticated encryption
- optional VM backend
- differential protection verification

**Current implementation:** source-level protection profiles and atomic publishing exist; the publish gate now requires semantic differential validation. Full AST/scope transforms and compiler-backed verification remain required.

## Gate 6 — Product Integration
- Android file-backed execution
- large-file cancellation/progress
- provenance UI
- final signed APK only after all release gates are green.

The project must not claim a gate is complete until its automated acceptance tests pass.
