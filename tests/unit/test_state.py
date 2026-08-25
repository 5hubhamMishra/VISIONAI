import pytest

from visionai.core.errors import StateTransitionError
from visionai.core.state import AppState, StateMachine


def test_state_machine_allows_normal_listening_path() -> None:
    machine = StateMachine()

    assert machine.transition(AppState.LISTENING).to_state == AppState.LISTENING
    assert machine.transition(AppState.TRANSCRIBING).to_state == AppState.TRANSCRIBING
    assert machine.transition(AppState.INTERPRETING).to_state == AppState.INTERPRETING
    assert machine.transition(AppState.RESPONDING).to_state == AppState.RESPONDING
    assert machine.transition(AppState.IDLE).to_state == AppState.IDLE


def test_state_machine_rejects_unapproved_jump() -> None:
    machine = StateMachine()

    with pytest.raises(StateTransitionError):
        machine.transition(AppState.EXECUTING)
