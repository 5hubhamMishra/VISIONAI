import json

import pytest

from visionai.config.routines import RoutineStore, normalize_routine_name
from visionai.core.errors import StorageError


def test_routine_store_saves_and_lists_a_routine(tmp_path) -> None:
    store = RoutineStore(tmp_path / "routines.json")

    assert store.list_names() == ()
    store.save("Morning", ["what time is it", "open notepad"])

    loaded = RoutineStore(tmp_path / "routines.json")
    assert loaded.list_names() == ("morning",)
    assert loaded.get("Morning") == ("what time is it", "open notepad")


def test_routine_store_delete_is_idempotent(tmp_path) -> None:
    store = RoutineStore(tmp_path / "routines.json")
    store.save("morning", ["what time is it"])

    store.delete("morning")
    store.delete("morning")

    assert store.get("morning") is None
    assert store.list_names() == ()


def test_routine_store_rejects_an_empty_name(tmp_path) -> None:
    store = RoutineStore(tmp_path / "routines.json")

    with pytest.raises(ValueError, match="non-empty"):
        store.save("   ", ["what time is it"])


def test_routine_store_rejects_a_name_with_control_characters(tmp_path) -> None:
    store = RoutineStore(tmp_path / "routines.json")

    with pytest.raises(ValueError, match="control characters"):
        store.save("morning\x00", ["what time is it"])


def test_routine_store_rejects_an_empty_phrase_list(tmp_path) -> None:
    store = RoutineStore(tmp_path / "routines.json")

    with pytest.raises(ValueError, match="at least one phrase"):
        store.save("morning", [])


def test_routine_store_get_returns_none_for_an_unknown_name(tmp_path) -> None:
    store = RoutineStore(tmp_path / "routines.json")

    assert store.get("does not exist") is None


def test_routine_store_get_ignores_a_malformed_entry(tmp_path) -> None:
    path = tmp_path / "routines.json"
    path.write_text(json.dumps({"morning": "not a list"}), encoding="utf-8")

    assert RoutineStore(path).get("morning") is None


def test_routine_store_rejects_malformed_json(tmp_path) -> None:
    path = tmp_path / "routines.json"
    path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(StorageError):
        RoutineStore(path).list_names()


def test_normalize_routine_name_collapses_whitespace_and_case() -> None:
    assert normalize_routine_name("  Morning  Routine  ") == "morning routine"


def test_normalize_routine_name_rejects_empty_or_unsafe() -> None:
    assert normalize_routine_name("   ") is None
    assert normalize_routine_name("bad\x00name") is None
