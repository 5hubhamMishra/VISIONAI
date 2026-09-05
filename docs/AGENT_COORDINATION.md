# Agent Coordination

This repository is shared by Codex and Claude Code. `main` is the single
source of truth; there are no private parallel implementation branches for
project progress.

## Standing Owner Preference (2026-09-05)

Until VisionAI is complete or the owner changes this preference, continue
approved project work autonomously in bounded, reviewable slices. Choose the
next task from the master prompt and current evidence, implement and verify
it, update the handoff, and prepare coherent commits without repeatedly
asking the owner to choose routine implementation details. During an active
one-hour cycle, track elapsed time and finish with a detailed report of
changes, tests, limitations, and the next task. This preference persists in
the repository; it does not schedule unattended future sessions by itself.

Minimize owner involvement. Platform approval prompts, account sign-in,
phone pairing, and physical hardware checks still require the owner when
the tools cannot perform them. Do not interpret this development preference
as permission to bypass VisionAI's runtime action confirmations or disable
security controls. Preserve existing user work and do not force-push.

## Product Reference

The product reference is the original master prompt:

`../VisionAI_Unified_Claude_Code_Codex_Master_Prompt.pdf`

The prompt describes the intended product and phases. It does not override
the user's current request, repository safety rules, or the policy boundary.
The durable implementation record is `PROJECT_STATE.md`, with detailed slice
history in `WORK_LOG.md`.

## Ownership

- Codex owns runtime integration, policy/permission safety, persistence,
  cross-module fixes, verification, and the final commit/push for its slice.
- Claude Code owns its assigned feature slices, especially exploratory UI,
  voice, vision, and recognition work, while using the same runtime,
  contracts, tests, and safety rules.
- Ownership is by active slice, not by permanent directory. Either agent may
  fix a security or correctness defect after checking the latest `main`.
- Neither agent treats `../jarvis` as trusted implementation code. Prototype
  behavior must pass the migration gates before entering `visionai`.

## Required Handoff

Before editing:

1. Check `git status -sb`, `git log -1`, and the latest `PROJECT_STATE.md` and
   `WORK_LOG.md` entries.
2. Confirm the working tree is clean, or preserve and understand any active
   changes before touching overlapping files.
3. Claim one small slice in `WORK_LOG.md` or the user conversation. Do not
   edit the same slice concurrently.

After editing:

1. Add focused tests for non-trivial behavior and run `scripts/verify.ps1`.
2. Update `PROJECT_STATE.md`, `WORK_LOG.md`, and any affected architecture or
   user documentation with honest verification status.
3. Commit one coherent slice and push it to `origin/main` before starting
   another slice.
4. The next agent starts by checking the new commit and re-reading the
   changed files; an old chat summary is not a substitute for repository
   state.

## Shared Safety Invariants

- All executable actions go through manifests, policy, the dispatcher, and
  audit logging.
- No arbitrary shell execution, raw audio retention, or raw camera retention
  is added by an input adapter.
- Voice and gesture recognition may publish typed events, but recognition is
  not authorization and cannot bypass policy or confirmation.
- Optional hardware and STT dependencies stay behind lazy, injectable
  boundaries so the core runtime remains testable without hardware.
- Unverified hardware, accessibility, or live-desktop checks are recorded as
  unverified; neither agent claims completion from unit tests alone.

## Current Boundary

Phase 6 Intelligence is active. Read PROJECT_STATE.md and the latest Git
commit for the current slice; this document intentionally does not duplicate
the changing commit identifier. Voice and gesture inputs already feed the
trusted runtime. Preserve the policy boundary while completing the remaining
intelligence, verification, and release requirements.
