from visionai.platform import StaticLockStateAdapter, WindowsLockStateAdapter
from visionai.policy import JsonPermissionStore, PolicyContext


def test_static_lock_state_defaults_to_conservative_locked() -> None:
    assert StaticLockStateAdapter().is_locked() is True


def test_policy_context_can_be_built_from_permission_and_lock_adapters(tmp_path) -> None:
    permissions = JsonPermissionStore(tmp_path / "permissions.json")
    permissions.grant("clipboard.read")

    context = PolicyContext.from_sources(
        permission_store=permissions,
        lock_state=StaticLockStateAdapter(locked=False),
    )

    assert context.granted_capabilities == frozenset({"clipboard.read"})
    assert context.locked_screen is False


def test_windows_lock_state_adapter_is_conservative_on_failure() -> None:
    adapter = WindowsLockStateAdapter(
        process_id_provider=lambda: 10,
        session_id_provider=lambda process_id: None,
    )

    assert adapter.is_locked() is True
    assert adapter.last_error is not None


def test_windows_lock_state_adapter_reports_unlocked_when_session_is_available() -> None:
    adapter = WindowsLockStateAdapter(
        process_id_provider=lambda: 10,
        session_id_provider=lambda process_id: 1,
    )

    assert adapter.is_locked() is False
    assert adapter.last_error is None
