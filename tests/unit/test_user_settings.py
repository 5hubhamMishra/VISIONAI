import json

import pytest

from visionai.config.user_settings import (
    DEFAULT_WAKE_WORD,
    UserSettingsStore,
    effective_log_level,
    effective_wake_word,
)
from visionai.core.errors import StorageError


def test_user_settings_store_persists_log_level_and_onboarding_flag(tmp_path) -> None:
    path = tmp_path / "settings.json"
    store = UserSettingsStore(path)

    assert store.get_log_level() is None
    assert store.has_seen_onboarding() is False

    store.set_log_level("DEBUG")
    store.mark_onboarding_seen()

    loaded = UserSettingsStore(path)
    assert loaded.get_log_level() == "DEBUG"
    assert loaded.has_seen_onboarding() is True


def test_user_settings_store_persists_microphone_device_index(tmp_path) -> None:
    store = UserSettingsStore(tmp_path / "settings.json")

    assert store.get_microphone_device_index() is None
    store.set_microphone_device_index(3)

    assert UserSettingsStore(tmp_path / "settings.json").get_microphone_device_index() == 3


def test_user_settings_store_ignores_invalid_microphone_device_index(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"microphone_device_index": -1}), encoding="utf-8")

    assert UserSettingsStore(path).get_microphone_device_index() is None


def test_user_settings_store_ignores_invalid_log_level(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"log_level": "TRACE"}), encoding="utf-8")

    assert UserSettingsStore(path).get_log_level() is None


def test_user_settings_store_rejects_malformed_json(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(StorageError):
        UserSettingsStore(path).get_log_level()


def test_effective_log_level_falls_back_to_environment_default(tmp_path) -> None:
    assert effective_log_level(UserSettingsStore(tmp_path / "settings.json")) == "INFO"


def test_user_settings_store_persists_a_normalized_wake_word(tmp_path) -> None:
    store = UserSettingsStore(tmp_path / "settings.json")

    assert store.get_wake_word() is None
    store.set_wake_word("  Hey  VisionAI  ")

    assert UserSettingsStore(tmp_path / "settings.json").get_wake_word() == "hey visionai"


def test_user_settings_store_rejects_an_empty_wake_word(tmp_path) -> None:
    store = UserSettingsStore(tmp_path / "settings.json")

    with pytest.raises(ValueError, match="non-empty"):
        store.set_wake_word("   ")


def test_user_settings_store_rejects_a_wake_word_with_control_characters(tmp_path) -> None:
    store = UserSettingsStore(tmp_path / "settings.json")

    with pytest.raises(ValueError, match="control characters"):
        store.set_wake_word("visionai\x00")


def test_user_settings_store_ignores_a_non_string_wake_word(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"wake_word": 42}), encoding="utf-8")

    assert UserSettingsStore(path).get_wake_word() is None


def test_effective_wake_word_falls_back_to_the_built_in_default(tmp_path) -> None:
    store = UserSettingsStore(tmp_path / "settings.json")

    assert effective_wake_word(store) == DEFAULT_WAKE_WORD

    store.set_wake_word("friday")
    assert effective_wake_word(store) == "friday"
