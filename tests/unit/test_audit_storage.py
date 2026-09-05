from pathlib import Path

import pytest

from visionai.core.errors import StorageError
from visionai.core.events import AuditEvent, RiskLevel
from visionai.observability import JsonlAuditSink


def test_jsonl_audit_sink_persists_events(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    sink = JsonlAuditSink(path)

    sink.record(
        AuditEvent(
            category="policy",
            actor="system",
            summary="permission denied",
            risk_level=RiskLevel.SENSITIVE,
        )
    )

    events = JsonlAuditSink(path).list()

    assert len(events) == 1
    assert events[0].summary == "permission denied"


def test_jsonl_audit_sink_rejects_malformed_lines(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("{not-json}\n", encoding="utf-8")

    with pytest.raises(StorageError):
        JsonlAuditSink(path).list()


def test_jsonl_audit_sink_clear_removes_existing_events(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    sink = JsonlAuditSink(path)
    sink.record(AuditEvent(category="policy", actor="system", summary="entry"))

    sink.clear()

    assert sink.list() == ()
    assert path.exists() is False


def test_jsonl_audit_sink_clear_is_a_noop_when_no_file_exists(tmp_path) -> None:
    sink = JsonlAuditSink(tmp_path / "audit.jsonl")

    sink.clear()

    assert sink.list() == ()


def test_jsonl_audit_sink_record_raises_storage_error_on_write_failure(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "audit.jsonl"
    sink = JsonlAuditSink(path)
    original_open = Path.open

    def _raise_for_target(self: Path, *args: object, **kwargs: object) -> object:
        if self == path:
            raise OSError("disk full")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _raise_for_target)

    with pytest.raises(StorageError, match="could not be written"):
        sink.record(AuditEvent(category="policy", actor="system", summary="entry"))


def test_jsonl_audit_sink_clear_raises_storage_error_on_unlink_failure(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    sink = JsonlAuditSink(path)
    original_unlink = Path.unlink

    def _raise_for_target(self: Path, *args: object, **kwargs: object) -> object:
        if self == path:
            raise OSError("permission denied")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _raise_for_target)

    with pytest.raises(StorageError, match="could not be cleared"):
        sink.clear()
