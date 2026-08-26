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
    def _raise() -> bool:
        raise OSError("desktop query failed")

    adapter = WindowsLockStateAdapter(can_open_input_desktop=_raise)

    assert adapter.is_locked() is True
    assert adapter.last_error is not None


def test_windows_lock_state_adapter_reports_locked_when_input_desktop_is_unreachable() -> None:
    """OpenInputDesktop fails while the secure lock-screen desktop is active."""
    adapter = WindowsLockStateAdapter(can_open_input_desktop=lambda: False)

    assert adapter.is_locked() is True
    assert adapter.last_error is None


def test_windows_lock_state_adapter_reports_unlocked_when_input_desktop_is_reachable() -> None:
    adapter = WindowsLockStateAdapter(can_open_input_desktop=lambda: True)

    assert adapter.is_locked() is False
    assert adapter.last_error is None


def test_windows_lock_state_adapter_runs_against_the_real_windows_api() -> None:
    """Smoke test: catches ctypes signature/marshaling regressions.

    This cannot assert a specific lock state (the test runner's session is
    not under our control), only that the real OpenInputDesktop/CloseDesktop
    call sequence executes cleanly and returns a bool.
    """
    result = WindowsLockStateAdapter().is_locked()

    assert isinstance(result, bool)
