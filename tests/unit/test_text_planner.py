from visionai.core.events import RiskLevel
from visionai.policy import PolicyContext
from visionai.runtime import build_runtime


def _planned_step(text: str):
    runtime = build_runtime()
    _intent, plan = runtime.planner.plan(text)
    assert len(plan.steps) == 1
    return plan.steps[0]


def test_planner_maps_direct_system_commands() -> None:
    assert _planned_step("what time is it").capability_id == "system.time"
    assert _planned_step("date").capability_id == "system.date"
    assert _planned_step("battery status").capability_id == "system.battery"
    assert _planned_step("system health").capability_id == "system.health"
    assert _planned_step("help").capability_id == "system.help"
    assert _planned_step("list capabilities").capability_id == "system.capabilities"
    assert _planned_step("clear history").capability_id == "system.clear_history"
    assert _planned_step("stop").capability_id == "system.stop"


def test_planner_maps_allowlisted_app_open() -> None:
    step = _planned_step("launch calculator")

    assert step.capability_id == "app.open"
    assert step.arguments["app"] == "calculator"
    assert step.risk_level == RiskLevel.REVERSIBLE


def test_planner_maps_allowlisted_site_open() -> None:
    step = _planned_step("go to github")

    assert step.capability_id == "browser.open"
    assert step.arguments["site"] == "github"


def test_planner_maps_search_query_as_data() -> None:
    step = _planned_step("search for VisionAI local assistant")

    assert step.capability_id == "browser.search"
    assert step.arguments["query"] == "visionai local assistant"


def test_planner_maps_media_phrases() -> None:
    step = _planned_step("volume up")

    assert step.capability_id == "media.control"
    assert step.arguments["action"] == "volume_up"


def test_planner_does_not_emit_action_for_unknown_text() -> None:
    runtime = build_runtime()

    intent, plan = runtime.planner.plan("make me coffee")

    assert intent.name == "conversation.reply"
    assert plan.steps == ()
    assert plan.summary == "No executable action selected."


def test_planner_does_not_emit_action_for_injection_shaped_app_text() -> None:
    runtime = build_runtime()

    intent, plan = runtime.planner.plan("open calc & powershell")

    assert intent.name == "conversation.reply"
    assert plan.steps == ()


def test_runtime_dispatches_planned_text_command() -> None:
    opened: list[str] = []
    runtime = build_runtime(browser_opener=lambda url: not opened.append(url))
    _intent, plan = runtime.planner.plan("open youtube")

    result = runtime.dispatcher.dispatch(plan.steps[0], PolicyContext())

    assert result.success is True
    assert opened == ["https://youtube.com/"]


def test_text_command_with_control_character_search_stays_non_executable() -> None:
    runtime = build_runtime()

    intent, plan = runtime.planner.plan("search hello\x00world")

    assert plan.steps == ()
    assert "\x00" not in intent.source_text


def test_text_command_with_control_character_app_name_stays_non_executable() -> None:
    """Regression: a rejected slot's control character must not crash the
    fallback plan -- Intent's SafeText fields reject them, but _empty_plan
    used to pass the raw, unsanitized text straight through."""
    runtime = build_runtime()

    intent, plan = runtime.planner.plan("open notepad\x00")

    assert plan.steps == ()
    assert intent.name == "conversation.reply"
    assert "\x00" not in intent.source_text
