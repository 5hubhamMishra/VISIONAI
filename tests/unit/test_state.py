import threading

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


def test_state_machine_notifies_registered_listeners() -> None:
    machine = StateMachine()
    transitions = []
    machine.on_transition(transitions.append)

    transition = machine.transition(AppState.LISTENING, reason="voice")

    assert transitions == [transition]


def test_state_machine_cancel_is_a_noop_when_idle_or_stopped() -> None:
    machine = StateMachine()

    assert machine.cancel() is None
    machine.transition(AppState.STOPPED)
    assert machine.cancel() is None


def test_state_machine_serializes_concurrent_transitions() -> None:
    """Regression: only one of many racing transitions may succeed.

    Voice and gesture recognition run on separate threads and both drive
    this state machine, so it must not reintroduce the uncontrolled shared
    state the old prototype used instead of a real state machine. Without
    a lock, multiple threads can all observe the same starting state and
    all successfully transition, corrupting history (multiple entries
    claiming the same from_state, one of which is stale).
    """
    machine = StateMachine()
    machine.transition(AppState.LISTENING)
    machine.transition(AppState.TRANSCRIBING)
    machine.transition(AppState.INTERPRETING)

    thread_count = 50
    barrier = threading.Barrier(thread_count)
    successes: list[bool] = []
    successes_lock = threading.Lock()

    def worker() -> None:
        barrier.wait()
        try:
            machine.transition(AppState.RESPONDING)
        except StateTransitionError:
            return
        with successes_lock:
            successes.append(True)

    threads = [threading.Thread(target=worker) for _ in range(thread_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(successes) == 1
    assert machine.state == AppState.RESPONDING
    for earlier, later in zip(machine.history, machine.history[1:], strict=False):
        assert later.from_state == earlier.to_state
