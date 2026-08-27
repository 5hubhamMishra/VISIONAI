import pytest

from visionai.orchestration.wake_word import WakeWordGate


def test_wake_word_gate_strips_default_wake_word() -> None:
    gate = WakeWordGate()

    assert gate.match("visionai open notepad") == "open notepad"


def test_wake_word_gate_is_case_insensitive() -> None:
    gate = WakeWordGate()

    assert gate.match("VisionAI Open Notepad") == "Open Notepad"


def test_wake_word_gate_rejects_missing_wake_word() -> None:
    gate = WakeWordGate()

    assert gate.match("open notepad") is None


def test_wake_word_gate_rejects_wake_word_alone() -> None:
    gate = WakeWordGate()

    assert gate.match("visionai") is None
    assert gate.match("  visionai  ") is None


def test_wake_word_gate_supports_a_custom_multi_word_phrase() -> None:
    gate = WakeWordGate(wake_word="hey visionai")

    assert gate.match("hey visionai open notepad") == "open notepad"
    assert gate.match("visionai open notepad") is None


def test_wake_word_gate_collapses_internal_whitespace_in_the_remainder() -> None:
    gate = WakeWordGate()

    assert gate.match("visionai   open    notepad") == "open notepad"


def test_wake_word_gate_normalizes_a_custom_wake_word_on_construction() -> None:
    gate = WakeWordGate(wake_word="  Hey   VisionAI  ")

    assert gate.wake_word == "hey visionai"
    assert gate.match("hey visionai open notepad") == "open notepad"


def test_wake_word_gate_rejects_empty_wake_word() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        WakeWordGate(wake_word="   ")


def test_wake_word_gate_rejects_control_characters_in_wake_word() -> None:
    with pytest.raises(ValueError, match="control characters"):
        WakeWordGate(wake_word="visionai\x00")


def test_wake_word_gate_does_not_match_a_word_that_only_starts_with_the_wake_word() -> None:
    gate = WakeWordGate()

    assert gate.match("visionaiable open notepad") is None
