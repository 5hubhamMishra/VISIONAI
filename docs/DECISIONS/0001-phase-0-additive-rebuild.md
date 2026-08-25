# Decision 0001: Additive Phase 0 Rebuild

## Status

Accepted.

## Context

The workspace contains a previous JARVIS prototype with direct system execution and documentation that overstates production readiness. The target VisionAI design requires typed contracts, policy gates, confirmation, testing, and neutral documentation before powerful features are added.

## Decision

Create a new `visionai/` package as an additive foundation and leave `../jarvis` untouched until individual features can be migrated safely.

## Consequences

- Existing prototype behavior remains available for reference but is not trusted runtime code.
- Phase 1 can focus on capability manifests, policy checks, confirmations, and security tests before any OS mutation features are migrated.
