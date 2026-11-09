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

**State:** IR schema introduced; adapters remain a required next gate.

## Gate 3 — Multi-Hypothesis Recovery
- candidate outputs from independent engines
- evidence scoring
- parser/compiler validation
- semantic comparison
- no false SUCCESS

**State:** candidate evidence/ranking primitive introduced; compiler/semantic oracles remain required.

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

## Gate 6 — Product Integration
- Android file-backed execution
- large-file cancellation/progress
- provenance UI
- final signed APK only after all release gates are green.

The project must not claim a gate is complete until its automated acceptance tests pass.
