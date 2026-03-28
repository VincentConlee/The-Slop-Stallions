"""
Smoke tests for Bot preflop lookup and legal-action filtering.

Run from Poker_slop directory:
    python -m python_skeleton.skeleton.test_bot_smoke
"""

import os
import sys
import time
import types

# bot.py imports pkrbot even though these tests do not need it.
# Stub it if unavailable so tests can still run.
try:
    import pkrbot  # noqa: F401
except ImportError:
    sys.modules["pkrbot"] = types.ModuleType("pkrbot")

from .actions import FoldAction, CheckAction, CallAction, RaiseAction
from .bot import Bot


class _MockRoundState:
    def __init__(self, actions):
        self._actions = set(actions)

    def legal_actions(self):
        return set(self._actions)


def _assert_close(actual, expected, tol=1e-9):
    if abs(actual - expected) > tol:
        raise AssertionError(f"expected {expected}, got {actual}")


def test_preflop_lookup_values(bot):
    # Exact values from HANDS.json
    _assert_close(bot.get_preflop_percent(["Ah", "Ad"]), 84.55)  # AA
    _assert_close(bot.get_preflop_percent(["Ah", "Kh"]), 66.05)  # AKs
    _assert_close(bot.get_preflop_percent(["Ah", "Kd"]), 64.65)  # AKo
    _assert_close(bot.get_preflop_percent(["3h", "2h"]), 37.55)  # 32s


def test_preflop_lookup_symmetry(bot):
    # Order of hole cards should not matter.
    _assert_close(
        bot.get_preflop_percent(["Ah", "Kd"]),
        bot.get_preflop_percent(["Kd", "Ah"]),
    )
    _assert_close(
        bot.get_preflop_percent(["Kh", "Ah"]),
        bot.get_preflop_percent(["Ah", "Kh"]),
    )


def test_preflop_lookup_default(bot):
    # Fallback behavior for invalid/incomplete card lists.
    _assert_close(bot.get_preflop_percent([]), 50.0)
    _assert_close(bot.get_preflop_percent(["Ah"]), 50.0)


def test_legal_action_filtering(bot):
    # If check exists, fold should be removed.
    actions = bot._get_legal_actions(_MockRoundState({FoldAction, CheckAction, RaiseAction}))
    if FoldAction in actions:
        raise AssertionError("FoldAction should be removed when CheckAction is legal")
    if CheckAction not in actions:
        raise AssertionError("CheckAction should remain legal")

    # If check does not exist, fold should remain if present from engine set.
    actions = bot._get_legal_actions(_MockRoundState({FoldAction, CallAction, RaiseAction}))
    if FoldAction not in actions:
        raise AssertionError("FoldAction should remain legal when CheckAction is not legal")


def benchmark_lookup(bot, n=1_000_000):
    deck = [r + s for r in "23456789TJQKA" for s in "cdhs"]
    deck_len = len(deck)

    start = time.perf_counter()
    idx = 0
    for _ in range(n):
        c1 = deck[idx % deck_len]
        c2 = deck[(idx + 17) % deck_len]
        idx += 1
        if c1 == c2:
            continue
        bot.get_preflop_percent([c1, c2])

    elapsed = time.perf_counter() - start
    rate = n / elapsed if elapsed > 0 else float("inf")
    return elapsed, rate


def run_all_tests():
    bot = Bot()

    test_preflop_lookup_values(bot)
    test_preflop_lookup_symmetry(bot)
    test_preflop_lookup_default(bot)
    test_legal_action_filtering(bot)

    elapsed, rate = benchmark_lookup(bot)

    print("PASS: all smoke tests")
    print(f"lookup_benchmark: elapsed_s={elapsed:.4f}, lookups_per_sec={rate:,.0f}")

    # Optional strict perf gate (disabled by default).
    # Set BOT_LOOKUP_MIN_RATE to enforce a minimum lookups/sec threshold.
    min_rate_env = os.environ.get("BOT_LOOKUP_MIN_RATE", "").strip()
    if min_rate_env:
        min_rate = float(min_rate_env)
        if rate < min_rate:
            raise AssertionError(
                f"lookup speed too low: {rate:,.0f} < required {min_rate:,.0f} lookups/sec"
            )
        print(f"PASS: perf threshold met ({rate:,.0f} >= {min_rate:,.0f})")


if __name__ == "__main__":
    run_all_tests()
