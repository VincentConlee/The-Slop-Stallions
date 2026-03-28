"""
Human-readable validation script for the Bot implementation.

Run from Poker_slop root:
    python -m python_skeleton.skeleton.test_bot_validation

Optional env vars:
    BOT_VALIDATION_LOOKUPS=200000
    BOT_VALIDATION_BETSIZE_ITERS=200000
"""

from __future__ import annotations

import os
import sys
import time
import traceback
import types
from dataclasses import dataclass
from typing import Callable, List, Tuple

# bot.py imports pkrbot; stub if missing so tests can still run.
try:
    import pkrbot  # noqa: F401
except ImportError:
    sys.modules["pkrbot"] = types.ModuleType("pkrbot")

from .actions import FoldAction, CheckAction, CallAction, RaiseAction
from .bot import BIG_BLIND, Bot


@dataclass
class TestResult:
    name: str
    status: str
    elapsed_ms: float
    details: str = ""


class MockRoundState:
    def __init__(self, actions, hands=None, board=None, pips=None, stacks=None):
        self._actions = set(actions)
        self.hands = hands if hands is not None else [["Ah", "Ad"], []]
        self.board = board if board is not None else []
        self.pips = pips if pips is not None else [0, 0]
        self.stacks = stacks if stacks is not None else [250, 250]

    def legal_actions(self):
        return set(self._actions)


class MockTerminalState:
    # Intentional minimal shape to mimic skeleton TerminalState usage.
    def __init__(self, deltas, previous_state=None):
        self.deltas = list(deltas)
        self.previous_state = previous_state


def assert_close(actual: float, expected: float, tol: float = 1e-9):
    if abs(actual - expected) > tol:
        raise AssertionError(f"expected {expected}, got {actual}")


def run_test(name: str, fn: Callable[[], str]) -> TestResult:
    start = time.perf_counter()
    try:
        details = fn() or ""
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return TestResult(name=name, status="PASS", elapsed_ms=elapsed_ms, details=details)
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        tb = traceback.format_exc(limit=1).strip()
        details = f"{exc.__class__.__name__}: {exc} | {tb}"
        return TestResult(name=name, status="FAIL", elapsed_ms=elapsed_ms, details=details)


def test_lookup_known_values(bot: Bot) -> str:
    assert_close(bot.get_preflop_percent(["Ah", "Ad"]), 84.55)
    assert_close(bot.get_preflop_percent(["Ah", "Kh"]), 66.05)
    assert_close(bot.get_preflop_percent(["Ah", "Kd"]), 64.65)
    assert_close(bot.get_preflop_percent(["3h", "2h"]), 37.55)
    return "AA/AKs/AKo/32s match HANDS table"


def test_lookup_symmetry(bot: Bot) -> str:
    assert_close(bot.get_preflop_percent(["Ah", "Kd"]), bot.get_preflop_percent(["Kd", "Ah"]))
    assert_close(bot.get_preflop_percent(["Kh", "Ah"]), bot.get_preflop_percent(["Ah", "Kh"]))
    return "Card order invariance confirmed"


def test_lookup_default(bot: Bot) -> str:
    assert_close(bot.get_preflop_percent([]), 50.0)
    assert_close(bot.get_preflop_percent(["Ah"]), 50.0)
    return "Invalid/incomplete input returns 50.0"


def test_legal_action_filter(bot: Bot) -> str:
    actions = bot._get_legal_actions(MockRoundState({FoldAction, CheckAction, RaiseAction}))
    if FoldAction in actions:
        raise AssertionError("FoldAction should be removed when CheckAction is legal")

    actions = bot._get_legal_actions(MockRoundState({FoldAction, CallAction, RaiseAction}))
    if FoldAction not in actions:
        raise AssertionError("FoldAction should remain legal when CheckAction is unavailable")
    return "Check/fold rule behaves as requested"


def test_bet_size_bounds(bot: Bot) -> str:
    bot.opponent_behavior["aggression"] = 0.5
    v = bot._select_bet_size(equity=0.7, pot=80, stack=40, street=3)
    if not isinstance(v, int):
        raise AssertionError(f"bet size should be int, got {type(v)}")
    if v < BIG_BLIND:
        raise AssertionError(f"bet size should be >= BIG_BLIND ({BIG_BLIND}), got {v}")
    if v > 40:
        raise AssertionError(f"bet size should be stack-capped to 40, got {v}")
    return f"Output {v} is int, >= BB, <= stack"


def test_bet_size_aggression_response(bot: Bot) -> str:
    eq, pot, stack, street = 0.8, 100, 250, 4
    bot.opponent_behavior["aggression"] = 0.0
    passive_size = bot._select_bet_size(eq, pot, stack, street)
    bot.opponent_behavior["aggression"] = 1.0
    aggro_size = bot._select_bet_size(eq, pot, stack, street)

    if passive_size <= aggro_size:
        raise AssertionError(
            f"expected passive size > aggressive size, got {passive_size} <= {aggro_size}"
        )
    return f"Passive={passive_size}, Aggressive={aggro_size}"


def test_bet_size_equity_response(bot: Bot) -> str:
    bot.opponent_behavior["aggression"] = 0.5
    low = bot._select_bet_size(equity=0.35, pot=120, stack=250, street=3)
    high = bot._select_bet_size(equity=0.85, pot=120, stack=250, street=3)
    if high <= low:
        raise AssertionError(f"expected high-equity size > low-equity size, got {high} <= {low}")
    return f"LowEq={low}, HighEq={high}"


def test_bet_size_street_scaling(bot: Bot) -> str:
    bot.opponent_behavior["aggression"] = 0.5
    flop = bot._select_bet_size(equity=0.7, pot=100, stack=250, street=3)
    river = bot._select_bet_size(equity=0.7, pot=100, stack=250, street=5)
    if river <= flop:
        raise AssertionError(f"expected river size > flop size, got river={river}, flop={flop}")
    return f"Flop={flop}, River={river}"


def test_get_action_contract(bot: Bot) -> str:
    # Strong hand path where RaiseAction is likely selected.
    rs = MockRoundState(
        actions={RaiseAction, CheckAction, CallAction, FoldAction},
        hands=[["Ah", "Ad"], []],
        board=[],
        pips=[0, 0],
        stacks=[250, 250],
    )
    action = bot.get_action(game_state=types.SimpleNamespace(bankroll=0), round_state=rs, active=0)

    if isinstance(action, RaiseAction) and not isinstance(action.amount, int):
        raise AssertionError(
            f"RaiseAction amount should be int, got {type(action.amount)}; value={action.amount}"
        )
    return f"Returned action type: {type(action).__name__}"


def test_handle_round_over_contract(bot: Bot) -> str:
    # This mimics skeleton TerminalState shape: no stacks attribute.
    ts = MockTerminalState(deltas=[1, -1], previous_state=None)
    bot.handle_round_over(game_state=types.SimpleNamespace(), terminal_state=ts, active=0)
    return "handle_round_over accepted TerminalState-like input"


def benchmark_lookup(bot: Bot) -> Tuple[int, float, float]:
    n = int(os.environ.get("BOT_VALIDATION_LOOKUPS", "300000"))
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
    return n, elapsed, rate


def benchmark_bet_sizing(bot: Bot) -> Tuple[int, float, float]:
    n = int(os.environ.get("BOT_VALIDATION_BETSIZE_ITERS", "300000"))
    start = time.perf_counter()
    for i in range(n):
        bot.opponent_behavior["aggression"] = (i % 101) / 100.0
        _ = bot._select_bet_size(
            equity=((i % 100) / 100.0),
            pot=(20 + (i % 400)),
            stack=(50 + (i % 250)),
            street=(0 if i % 4 == 0 else 3 if i % 4 == 1 else 4 if i % 4 == 2 else 5),
        )
    elapsed = time.perf_counter() - start
    rate = n / elapsed if elapsed > 0 else float("inf")
    return n, elapsed, rate


def print_results(results: List[TestResult]):
    print("=" * 88)
    print("BOT VALIDATION REPORT")
    print("=" * 88)
    print(f"{'Status':<8} {'Test':<34} {'Time(ms)':>10}  Details")
    print("-" * 88)
    for r in results:
        print(f"{r.status:<8} {r.name:<34} {r.elapsed_ms:>10.2f}  {r.details}")

    total = len(results)
    passed = sum(1 for r in results if r.status == "PASS")
    failed = total - passed
    print("-" * 88)
    print(f"TOTAL: {total}  PASS: {passed}  FAIL: {failed}")
    print("=" * 88)


def main() -> int:
    bot = Bot()

    tests = [
        ("lookup known values", lambda: test_lookup_known_values(bot)),
        ("lookup symmetry", lambda: test_lookup_symmetry(bot)),
        ("lookup default fallback", lambda: test_lookup_default(bot)),
        ("legal action filtering", lambda: test_legal_action_filter(bot)),
        ("bet size bounds", lambda: test_bet_size_bounds(bot)),
        ("bet size aggression response", lambda: test_bet_size_aggression_response(bot)),
        ("bet size equity response", lambda: test_bet_size_equity_response(bot)),
        ("bet size street scaling", lambda: test_bet_size_street_scaling(bot)),
        ("get_action contract", lambda: test_get_action_contract(bot)),
        ("handle_round_over contract", lambda: test_handle_round_over_contract(bot)),
    ]

    results = [run_test(name, fn) for name, fn in tests]

    n_lookup, t_lookup, r_lookup = benchmark_lookup(bot)
    n_bet, t_bet, r_bet = benchmark_bet_sizing(bot)

    print_results(results)

    print("BENCHMARKS")
    print("-" * 88)
    print(
        "lookup table: "
        f"iterations={n_lookup:,} elapsed_s={t_lookup:.4f} lookups_per_sec={r_lookup:,.0f}"
    )
    print(
        "bet sizing:   "
        f"iterations={n_bet:,} elapsed_s={t_bet:.4f} evals_per_sec={r_bet:,.0f}"
    )
    print("=" * 88)

    failed = sum(1 for r in results if r.status == "FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
