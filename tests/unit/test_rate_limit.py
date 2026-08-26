import threading

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


def test_rate_limiter_enforces_limit_under_concurrent_access() -> None:
    """Regression: allow() must not let concurrent callers exceed the limit.

    A dispatcher only serializes handler execution, not policy evaluation,
    so this limiter can be hit from multiple recognition threads at once.
    """
    limiter = FixedWindowRateLimiter(clock=lambda: 100.0)
    limit = 20
    thread_count = 100
    barrier = threading.Barrier(thread_count)
    results: list[bool] = []
    results_lock = threading.Lock()

    def worker() -> None:
        barrier.wait()
        allowed = limiter.allow("system.time", limit)
        with results_lock:
            results.append(allowed)

    threads = [threading.Thread(target=worker) for _ in range(thread_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count(True) == limit
