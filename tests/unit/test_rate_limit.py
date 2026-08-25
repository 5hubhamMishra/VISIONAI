from visionai.policy import FixedWindowRateLimiter


def test_rate_limiter_blocks_after_limit_inside_window() -> None:
    now = 100.0
    limiter = FixedWindowRateLimiter(clock=lambda: now)

    assert limiter.allow("system.time", 2) is True
    assert limiter.allow("system.time", 2) is True
    assert limiter.allow("system.time", 2) is False


def test_rate_limiter_resets_after_window() -> None:
    current = 100.0
    limiter = FixedWindowRateLimiter(clock=lambda: current)

    assert limiter.allow("system.time", 1) is True
    assert limiter.allow("system.time", 1) is False

    current = 161.0

    assert limiter.allow("system.time", 1) is True
