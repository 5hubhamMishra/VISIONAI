# Decision 0006: Local/Offline LLM Provider

## Status

Accepted.

## Context

`docs/DECISIONS/0004-llm-provider-choice.md` named a local/offline provider as
an explicit, accepted gap: Section 12 requires supporting "cloud, optional
local, and deterministic fallback providers," and only the cloud
(`AnthropicProvider`) and fallback (`DeterministicFallbackProvider`) sides
existed. This closes that gap behind the same unmodified `LLMProvider`
Protocol (`respond(query: LLMQuery) -> LLMReply`) `0004` already established,
exactly as `0004`'s own "Consequences" section anticipated: "a new class
behind `LLMProvider`, plus a `Settings.llm_provider` literal value and a
branch in `app._build_llm_provider()` -- no changes to `LLMQuery`/`LLMReply`,
`--ask`, or any test that exercises the `LLMProvider` Protocol itself."

## Decision

- **Library: `gpt4all`** (`requirements/local_llm.txt`, pinned `gpt4all==2.8.2`;
  MIT-licensed). Checked against the real PyPI release metadata before
  choosing it, the same way `0003` checked mediapipe's actual Windows wheel
  support before pinning it: `gpt4all` publishes prebuilt `py3-none` wheels
  for `win_amd64`, `manylinux1_x86_64`, and macOS, so a Windows end user
  installs a binary wheel with no local compiler. The obvious alternative,
  `llama-cpp-python`, was checked and rejected for this project: as of the
  version checked (0.3.35), PyPI carries only an sdist for it -- installing
  it would require a working C++ build toolchain (cmake, a C++ compiler) on
  every user's machine, which is a real, avoidable installation burden this
  project does not need to accept.
- **New optional dependency group: `local_llm`** (`pyproject.toml`'s
  `[project.optional-dependencies]`, `requirements/local_llm.txt`),
  deliberately **not** added to `requirements/dev.txt`, mirroring how
  `vision`/`mediapipe` is kept out of the standard dev/CI install per
  `docs/DECISIONS/0003-accepted-protobuf-cve.md`. This keeps the standard
  verification suite's dependency surface unchanged, and means the real
  `gpt4all` import path (`LocalLlamaProvider.__init__`'s `client is None`
  branch) is not installed or exercised by the automated suite in this
  session -- the same accepted, pre-existing shape `AnthropicProvider`'s own
  real-import branch had before this session incidentally closed it (see
  "Consequences" below).
- **No model download, ever.** The real client is always constructed with
  `allow_download=False`. `Settings.local_model_path` (`VISIONAI_LOCAL_MODEL_PATH`)
  must point at a GGUF model file the user has already placed on disk;
  `app._build_llm_provider()`/`main_window._build_llm_provider()` raise a
  clear `ValueError` if it is unset or the file does not exist, rather than
  silently falling through to a network fetch. This is the one property that
  actually makes this provider "local/offline" rather than merely "a
  different vendor's cloud API" -- a local provider that could reach out to
  the network to fetch a model on first use would not meet that bar.
- **Same authority boundary as every other provider.** `LocalLlamaProvider`
  is a plain `LLMProvider`: `respond()` returns free text that only `--ask`/
  Ask AI ever print, never parsed as a command, never reaching policy or the
  dispatcher. Its system prompt is the exact same fixed, code-owned string
  `AnthropicProvider` uses, folded into the one prompt string sent to
  `generate()` (gpt4all's `generate()` takes one prompt, not a separate
  system-role message the way the Anthropic Messages API does). Client
  failures and `LLMReply`'s own `SafeText` validation failures are both
  caught broadly and re-raised as `core.errors.ProviderError`, matching
  `AnthropicProvider.respond()`'s exact precedent (including the bug that
  precedent exists to prevent -- see `docs/SECURITY.md`'s 2026-09-05
  text-safety hardening entry).
- **`gpt4all` is imported via `importlib.import_module()`, not a static
  `from gpt4all import ...`**, mirroring `visionai.platform.webcam`'s pattern
  for `cv2`/`mediapipe` rather than `anthropic_provider.py`'s static import --
  because, unlike `anthropic`/`keyring` (both part of `requirements/dev.txt`
  via `intelligence.txt`), `gpt4all` is not installed in the standard
  dev/CI environment, so a static import would fail mypy's strict
  module-resolution check the same way a static `import cv2` would.

## Consequences

- Not live-verified in this session: no real GGUF model file exists in this
  Linux sandbox (no display, GPU, or downloaded model, matching this
  project's standing hardware constraint for Windows-only adapters), and
  `gpt4all` itself was never installed here (deliberately, per the
  "Decision" section above). `LocalLlamaProvider` is verified the same way
  `AnthropicProvider` is: fully unit-tested against an injected fake client
  (`tests/unit/test_local_provider.py`, mirroring
  `tests/unit/test_anthropic_provider.py` exactly, including the
  unsafe-reply-becomes-`ProviderError` regression case) and through
  `_build_llm_provider()`'s own branch logic in both `app.py` and
  `main_window.py` (missing path, missing file, and a happy path that
  substitutes a fake `LocalLlamaProvider` class for the real one so the
  `gpt4all` import itself is never required to run the test). The real
  `import_module("gpt4all")` branch inside `LocalLlamaProvider.__init__`
  remains genuinely untested in this sandbox, an explicit, accepted gap for
  a later session with the extra installed (or real Windows hardware) to
  close, the same shape `WebcamLandmarkAdapter`'s real mediapipe path was in
  before it was live-verified.
- While adding this, found and closed an unrelated, pre-existing coverage
  gap in the same two functions this decision touches: neither
  `app._build_llm_provider()` nor `main_window._build_llm_provider()` had
  ever been tested for its own real branch logic before this session --
  every existing test replaced the whole function with a fake provider
  instead. `app.py`'s anthropic branch (missing-key rejection and real
  `AnthropicProvider` construction) is now covered too, incidentally
  bringing `anthropic_provider.py` itself to 100% coverage (previously 89%,
  missing exactly its own real-`anthropic`-import branch) since the new
  `app.py`-level test is the first one anywhere in this suite to reach it
  with `anthropic` actually installed. `main_window.py`'s equivalent
  function had zero coverage at all before this session; it now has the
  same branch coverage `app.py`'s does.
- A future desktop Settings control for choosing `local_model_path` (the
  same way the Anthropic API key got a masked Settings field in
  `docs/DECISIONS/0005-os-keychain-secret-storage.md`) is left for a later
  slice; today this is environment-variable-only, matching where the
  Anthropic provider's model/provider selection already stood before `0005`.
