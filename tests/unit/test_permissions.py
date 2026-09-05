import pytest

from visionai.core.errors import StorageError
from visionai.policy import JsonPermissionStore
from visionai.policy import permissions as permissions_module


def test_permission_store_persists_grants_and_revocations(tmp_path) -> None:
    path = tmp_path / "permissions.json"
    store = JsonPermissionStore(path)

    store.grant("clipboard.read")
    assert JsonPermissionStore(path).is_granted("clipboard.read") is True

    store.revoke("clipboard.read")
    assert JsonPermissionStore(path).is_granted("clipboard.read") is False


def test_permission_store_lists_only_granted_capabilities(tmp_path) -> None:
    store = JsonPermissionStore(tmp_path / "permissions.json")

    store.grant("clipboard.read")
    store.revoke("browser.open_site")

    assert store.granted_capabilities() == frozenset({"clipboard.read"})


def test_permission_store_rejects_malformed_json(tmp_path) -> None:
    path = tmp_path / "permissions.json"
    path.write_text("[not valid json", encoding="utf-8")

    with pytest.raises(StorageError):
        JsonPermissionStore(path).granted_capabilities()


def test_permission_store_rejects_invalid_entries(tmp_path) -> None:
    path = tmp_path / "permissions.json"
    path.write_text('{"clipboard.read": "yes"}', encoding="utf-8")

    with pytest.raises(StorageError):
        JsonPermissionStore(path).granted_capabilities()


def test_permission_store_rejects_non_object_json_root(tmp_path) -> None:
    path = tmp_path / "permissions.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(StorageError, match="root must be an object"):
        JsonPermissionStore(path).granted_capabilities()


def test_permission_store_raises_storage_error_on_write_failure(tmp_path, monkeypatch) -> None:
    path = tmp_path / "permissions.json"

    def _raise_os_error(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(permissions_module, "NamedTemporaryFile", _raise_os_error)

    with pytest.raises(StorageError, match="could not be written"):
        JsonPermissionStore(path).grant("clipboard.read")
