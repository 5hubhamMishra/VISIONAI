# Decision 0004: LLM Provider Choice and Secret Storage for Phase 6's First Slice

## Status

Accepted.

## Context

Phases 0-5's approved scope are all closed (see `docs/PROJECT_STATE.md`). The master
prompt (`../VisionAI_Unified_Claude_Code_Codex_Master_Prompt.pdf`, Section 19) names
Phase 6 (Intelligence) as the next required phase, and `docs/DECISIONS/0002-package-layout-deviation.md`
already reserved the `intelligence` package name for exactly this moment. The user was
asked and explicitly chose to start Phase 6.

Section 5 says "do not hard-code one LLM provider or obsolete model; make
provider/model configuration-driven," and Section 12 requires supporting "cloud,
optional local, and deterministic fallback providers." Section 19's Phase 6 exit
criteria ("no invented tools, policy authority, no malformed-output side effect")
apply to the whole phase, not this first slice -- this slice adds no capability
invocation at all, so those criteria are trivially satisfied by construction rather
than needing dedicated tests yet.

## Decision

- **First real provider: Anthropic**, via the official `anthropic` Python SDK
  (`requirements/intelligence.txt`, pinned `anthropic==1.2.0`; MIT-licensed, actively
  maintained, confirmed Python 3.12-compatible by installing and importing it during
  this slice). `visionai.intelligence.provider.LLMProvider` is a small `Protocol`
  (`respond(query: LLMQuery) -> LLMReply`), so this is not a commitment to Anthropic
  specifically -- a second provider can be added behind the same interface with no
  change to `LLMQuery`/`LLMReply` or anything that calls `LLMProvider`.
- **Default model: `claude-opus-5`**, fully overridable via `VISIONAI_LLM_MODEL`. A
  default is not the same as a hard-coded choice -- Section 5's requirement is that the
  model be configuration-driven, which it is.
- **Default provider: `none`** (`Settings.llm_provider`, `VISIONAI_LLM_PROVIDER`). The
  app makes zero network calls unless a provider is explicitly configured --
  `DeterministicFallbackProvider` is what "none" resolves to, matching Section 2's "do
  not add powerful functionality before the safety and validation architecture is
  complete" and mirroring how `vision`/`voice` are opt-in extras rather than defaults.
- **Secrets: environment variable only, for now.** `Settings.anthropic_api_key` is a
  `pydantic.SecretStr` read from `VISIONAI_ANTHROPIC_API_KEY` -- never the `anthropic`
  SDK's own implicit `ANTHROPIC_API_KEY` environment auto-detection, so configuration
  stays explicit and auditable through `Settings`, matching every other configuration
  value in this project. The master prompt's "environment variables, and OS keychain
  for secrets" names two acceptable sources; a grep across this entire repository
  turned up **no** existing `keyring` dependency or OS Credential Manager integration
  anywhere -- env-var-only is the current reality for every secret-shaped value in this
  codebase today, not a regression introduced by this slice. Adding real OS keychain
  storage is a genuine, separable piece of work (a new dependency, a new storage
  boundary, platform-specific code) and is recorded here as an accepted, explicit gap
  to revisit, not silently deferred.
- **No `UserSettingsStore` entry for the API key.** That store is a plaintext JSON file
  on disk (`.visionai/settings.json`), explicitly documented for values "safe to change
  at runtime" -- putting a secret there would be a real regression from the `Settings`
  (env-var) path. A desktop Settings-dialog toggle for `llm_provider` is left for a
  later slice, the same way microphone/wake-word desktop editing arrived several slices
  after the underlying voice pipeline existed.
- **Synchronous provider boundary, no orchestrator wiring yet.** `LLMProvider.respond()`
  is a plain blocking call, matching `LandmarkAdapter.read_candidate()` and
  `MicrophoneCapture.start()/stop()`'s adapter-boundary shape. The only entry point is
  `visionai --ask "<question>"`, which runs before `build_runtime()` is even called
  (mirroring `--list-microphones`) and never touches `runtime.orchestrator`,
  `runtime.dispatcher`, or the event buses. An LLM reply is only ever printed, never
  parsed as a command -- there is no path from this slice's code to any capability
  execution. Section 12's higher-risk "structured planner" (an LLM proposing an
  `ActionPlan` that still passes through policy) is explicitly deferred to a clearly
  labeled future slice, the same way gesture-to-capability mapping was deferred until
  the temporal-voting boundary existed and was tested standalone first.
- **No conversation memory.** Each `--ask` call is a stateless, one-shot request with
  nothing persisted -- Section 12's "retention limits and deletion" requirement is
  satisfied trivially by having nothing to retain yet, rather than building a retention
  policy for data that doesn't exist.
  - **Done, for the desktop window.** `visionai.intelligence.memory.ConversationMemory`
    adds a bounded (a fixed maximum turn count, oldest evicted first, plus a character
    budget so a long conversation can never grow an outgoing query past `LLMQuery`'s own
    validated length limit), explicitly clearable (`clear()`) question/answer history.
    It lives entirely on the caller's side of the unmodified `LLMProvider.respond(query)
    -> reply` boundary -- providers still only ever see one `LLMQuery` per call.
    `MainWindow`'s Ask AI button owns one `ConversationMemory` per window session (a new
    "Clear Conversation" button deletes it on demand); nothing is ever written to disk.
    The CLI's `--ask` deliberately keeps the original stateless reasoning above and does
    not use it -- a fresh process per invocation has no natural place to keep history
    without adding new persistence, which is a separate decision this slice does not make.

## Consequences

- Adding a second cloud provider or a local/offline provider means writing a new class
  behind `LLMProvider`, plus a `Settings.llm_provider` literal value and a branch in
  `app._build_llm_provider()` -- no changes to `LLMQuery`/`LLMReply`, `--ask`, or any
  test that exercises the `LLMProvider` Protocol itself.
- Before an LLM's output is ever allowed to influence a capability dispatch (the
  structured-planner slice), that slice must add: strict schema validation of any
  proposed plan, prompt/indirect-injection tests (Section 17), and an explicit
  confirmation surface -- none of which this slice needs, since it has no dispatch path
  to defend.
  - **Done, same session.** `visionai.intelligence.planner.suggest_command()` is the
    schema-validated layer (its output is always re-checked against
    `orchestration.text_planner.reviewed_phrases()`, never trusted from the LLM's raw
    reply -- covered in `tests/unit/test_command_suggestion.py`, including a
    hallucinated-phrase-outside-the-menu case standing in for a prompt-injection
    attempt), and `--suggest` gained the confirmation surface: a genuine
    `input("Execute this command? [y/N]: ")` question, never anything derived from the
    LLM's own output, gates the exact same unmodified `runtime.dispatcher.dispatch()`
    call `--text` already uses -- covered by
    `test_app_suggest_requires_confirmation_before_dispatch` (approve) and
    `test_app_suggest_cancel_does_not_dispatch` (decline). A capability still needing
    its own permission grant or fresh confirmation is denied by that unmodified policy
    check regardless of this new human question, exactly as `--text` already behaves.
- If OS keychain storage is added later, `Settings.anthropic_api_key` is the field to
  migrate off env-only reading; revisit this decision at that point rather than treating
  env-var-only as permanent.
  - **Done.** See `docs/DECISIONS/0005-os-keychain-secret-storage.md`: env-var reading
    is unchanged (still wins if set), and `visionai.config.secrets.
    resolve_anthropic_api_key()` adds a Windows Credential Manager fallback via the
    `keyring` package.
