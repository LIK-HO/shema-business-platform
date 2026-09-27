# Phase 1-B — Intelligence Benchmark & Source Registry

## Purpose

Phase 1-B establishes a permanent measurement boundary before broader intelligence-source automation.

It deliberately does not add:
- a new database;
- new canonical identity semantics;
- automatic source lookup;
- ranking authority;
- automatic qualification;
- a new system of record.

## Source registry

architecture/intelligence_source_registry_contract.json is the declarative registry.

It separates source class, default source reliability, supported identifiers, supported claim types, freshness requirements, access mode and automation status.

The registry is contextual metadata, not a universal source ranking.

## Benchmark corpus

architecture/intelligence_benchmark_contract.json contains ten permanent synthetic cases covering exact identifier match, same-name different entity, old identifier, changed registration, duplicate sources, contradictory claims, stale claims, missing identifiers and misleading near-match.

The corpus uses synthetic identifiers and names only.

## Metrics

The pure evaluator in src/shema_platform/application/intelligence_benchmark.py provides precision, recall, false-positive rate, false-negative rate, provenance completeness, freshness correctness and operator correction rate.

Metrics are measurements, not authority. Benchmark output cannot mutate canonical identity state.

## Exit condition

Phase 1-B closes only when the registry and corpus are explicitly validated, negative paths are tested, reliability dimensions remain separate, and the full CI/release gate is green.

Broader automated research remains deferred until this measurement boundary is closed.