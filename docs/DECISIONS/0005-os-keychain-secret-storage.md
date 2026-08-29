# Decision 0005: OS Keychain Secret Storage for the Anthropic API Key

## Status

Accepted.

## Context

`docs/DECISIONS/0004-llm-provider-choice.md` recorded env-var-only secret storage as
an explicit, accepted gap: "Adding real OS keychain storage is a genuine, separable
piece of work... revisit this decision at that point rather than treating env-var-only
as permanent." The master prompt (Section 15) names "environment variables, and OS
keychain" as the two acceptable secret sources. With Phase 6's provider boundary and
command-suggestion slices done on both the CLI and the desktop window, and asked which
direction to take next (this, a local/offline provider, or conversation memory), the
user chose this.

## Decision

- **Backend: `keyring` (pinned `keyring==25.7.0`, MIT-licensed), Windows Credential
  Manager.** The standard Python library for OS credential-store access; on Windows it
  uses `WinVaultKeyring` automatically. Folded into the existing `intelligence` extra
  (`requirements/intelligence.txt`, `pyproject.toml`) rather than a new extras category,
  since its only current consumer is the Anthropic API key -- matching
  `docs/DECISIONS/0002`'s "don't create a category ahead of the code that justifies
  it." A fixed service name, `"visionai"`, namespaces every secret this app ever stores
  in the OS credential store; the secret's logical name (`"anthropic_api_key"`) is the
  keyring "username" field.
- **`src/visionai/config/secrets.py`** mirrors `visionai.platform.lock_state`'s
  Protocol/in-memory-double/real-implementation shape: a `SecretStore` Protocol
  (`get`/`set`/`delete`), `InMemorySecretStore` (a real dict-backed round-trip, the test
  double), and `KeyringSecretStore` (the real implementation; `keyring` is imported
  lazily inside each method, never at module level, so `visionai.config` stays
  importable without the `intelligence` extra installed, mirroring
  `intelligence/anthropic_provider.py`'s lazy `anthropic` import).
- **Precedence: explicit env var wins, keychain is the fallback.**
  `resolve_anthropic_api_key(settings, store=None)` checks
  `settings.anthropic_api_key` (still read from `VISIONAI_ANTHROPIC_API_KEY`, unchanged
  behavior for existing users) first; only if that's unset does it fall back to
  `(store or default_secret_store()).get("anthropic_api_key")`. This is backward
  compatible (nothing that worked before changes) and matches the common convention
  that an explicit, per-process override takes priority over a persistent stored
  default.
- **`get()` fails soft; `set()`/`delete()` fail loud.** A keychain read failure (locked
  store, backend unavailable) is indistinguishable from "no key configured" and returns
  `None`, matching `WindowsLockStateAdapter`'s "any check failure -> safe default"
  precedent -- there is nothing more informative to do with a failed read than treat it
  as absent. A failed *write* is different: silently swallowing it would let a user
  believe a key was saved when it wasn't, so `set()`/`delete()` raise
  `core.errors.StorageError` (already used by `JsonlAuditSink`/`JsonPermissionStore`/
  `UserSettingsStore` for exactly this "local persistence operation failed" case) on a
  genuine backend failure. `delete()` specifically catches `keyring.errors.
  PasswordDeleteError` and treats it as a silent no-op -- confirmed against the real
  Windows backend source (not assumed) that this exception specifically means "wasn't
  there," making repeated deletes safely idempotent.
- **New CLI flags only, no desktop UI control yet:** `visionai --set-api-key` prompts
  via `getpass.getpass()` (hidden input, avoids shell-history/process-list exposure)
  and stores the value; `visionai --delete-api-key` removes it. Both run before
  `build_runtime()` (like `--ask`/`--list-microphones` -- neither needs the capability
  registry). A `MainWindow` control for this is deliberately deferred, matching this
  project's established CLI-first-then-UI pattern (`--gesture-listen` before the
  Gesture Control button, `--ask`/`--suggest` before their UI buttons).

## Consequences

- `_build_llm_provider()` in both `app.py` and `main_window.py` now calls
  `resolve_anthropic_api_key(settings)` instead of reading
  `settings.anthropic_api_key` directly -- any future secret source (e.g. a different
  OS on a future platform target) is a change to this one function, not every call
  site.
- A user who has never run `--set-api-key` and has no `VISIONAI_ANTHROPIC_API_KEY` set
  sees the exact same `ValueError` message as before, now naming both ways to fix it.
- If a desktop Settings control for this is added later, it should call the same
  `default_secret_store()`/`resolve_anthropic_api_key()` functions this decision
  introduces, not a separate keychain integration.
