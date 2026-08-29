"""Secret storage boundary: OS keychain, with an env-var fallback caller.

Mirrors `visionai.platform.lock_state`'s Protocol/in-memory-double/real-
implementation shape. `keyring` (the optional `intelligence` extra) is only
imported inside the methods that touch it, so `visionai.config` stays
importable without it, matching `visionai.intelligence.anthropic_provider`'s
lazy-import pattern for `anthropic`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from visionai.config.settings import Settings
from visionai.core.errors import StorageError

_SERVICE_NAME = "visionai"


class SecretStore(Protocol):
    """Get, set, and delete one named secret."""

    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str) -> None: ...

    def delete(self, key: str) -> None: ...


@dataclass
class InMemorySecretStore:
    """Test double: a real get/set/delete round-trip, no OS keychain touched."""

    _values: dict[str, str] = field(default_factory=dict)

    def get(self, key: str) -> str | None:
        return self._values.get(key)

    def set(self, key: str, value: str) -> None:
        self._values[key] = value

    def delete(self, key: str) -> None:
        self._values.pop(key, None)


class KeyringSecretStore:
    """Real OS keychain-backed store (Windows Credential Manager via `keyring`)."""

    def get(self, key: str) -> str | None:
        # Import stays unguarded: a missing `intelligence` extra must raise
        # ImportError (already handled by callers), not look identical to
        # "no key configured."
        import keyring

        try:
            return keyring.get_password(_SERVICE_NAME, key)
        except Exception:  # true external OS boundary, mirrors WindowsLockStateAdapter
            return None

    def set(self, key: str, value: str) -> None:
        import keyring

        try:
            keyring.set_password(_SERVICE_NAME, key, value)
        except Exception as exc:
            raise StorageError(f"could not save secret {key!r}") from exc

    def delete(self, key: str) -> None:
        import keyring
        import keyring.errors

        try:
            keyring.delete_password(_SERVICE_NAME, key)
        except keyring.errors.PasswordDeleteError:
            pass  # idempotent: the Windows backend raises this to mean "wasn't there"
        except Exception as exc:
            raise StorageError(f"could not delete secret {key!r}") from exc


def default_secret_store() -> SecretStore:
    return KeyringSecretStore()


def resolve_anthropic_api_key(settings: Settings, store: SecretStore | None = None) -> str | None:
    """Explicit env var wins; the OS keychain is the fallback, never silently merged."""

    if settings.anthropic_api_key is not None:
        return settings.anthropic_api_key.get_secret_value()
    return (store or default_secret_store()).get("anthropic_api_key")
