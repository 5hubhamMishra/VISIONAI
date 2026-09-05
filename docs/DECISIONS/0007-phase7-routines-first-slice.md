# 0007: Phase 7 first slice -- routines restricted to read-only/reversible steps

## Status

Accepted.

## Context

Section 19 of the master development prompt blocks Phase 7 (Advanced: routines,
macro preview/dry-run, plugin manifests, multimodal input, personalization, a
local LLM model manager) from starting without explicit human approval, and
warns against generating a large feature in one uncontrolled pass. The user
approved starting Phase 7 and asked for the smallest, lowest-risk first slice
rather than a large routines system.

The most obvious "routine" feature -- a named sequence of arbitrary commands,
run on request -- immediately raises a real design question this project has
not yet answered: what happens when one step in the sequence is a Risk 2+
capability that needs a permission grant or a fresh confirmation? Section 9
requires confirmation to "display exact normalized action, target and effect"
and to "bind to exact request", and `--text`'s existing direct-dispatch path
(the only precedent for CLI command execution with no interactive confirmation
loop) simply lets the dispatcher deny anything that still needs confirmation,
rather than prompting for it. Building a real multi-step confirmation UX for
routines is a legitimate future slice, but it is exactly the kind of new
security-relevant design decision this project's own pattern says to plan
carefully, not bundle into a "smallest first slice."

## Decision

The first Phase 7 slice sidesteps that open question entirely: a routine may
only contain phrases that already plan to a Risk 0 (read-only) or Risk 1
(reversible) capability -- exactly the tier that already executes with no
permission grant or confirmation when run individually via `--text`. This is
enforced twice, not once: at `--routine-save` time (rejecting the whole save if
any phrase fails) and again at `--routine-run` time (re-checking each step's
live risk level immediately before dispatch, in case a capability's manifest
changed between save and run). A routine step is otherwise dispatched through
the completely unmodified `TextCommandPlanner`/`SerializedDispatcher` path
`--text` already uses -- a routine carries no authority of its own; it is
nothing more than replaying already-individually-safe phrases in order.

`visionai.config.routines.RoutineStore` mirrors `UserSettingsStore`'s
atomic-write JSON pattern and has no opinion on which phrases are safe --
that judgment lives in `app.py`, which has the real planner. New CLI surface:
`--routine-save NAME PHRASE [PHRASE ...]`, `--routine-run NAME`,
`--routine-list`, `--routine-delete NAME`.

## Consequences

A routine cannot yet chain a permission-gated or confirmation-gated action --
by construction, not by a runtime check that could be bypassed. Real
multi-step confirmation UX (Section 9), routine scheduling, macro preview/
dry-run, and a desktop UI surface for routines are all deliberately deferred
to a later slice. No desktop `MainWindow` control exists for this yet,
matching this project's established CLI-first-then-UI precedent.
