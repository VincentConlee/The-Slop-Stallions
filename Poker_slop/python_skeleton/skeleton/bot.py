'''
This file contains the base class that you should implement for your pokerbot.
'''
import os
import pkrbot
from .actions import FoldAction, CheckAction, CallAction, RaiseAction
import numpy as np
STARTING_STACK = 250
BIG_BLIND = 5
SMALL_BLIND = 2
EFFECTIVE_BB = STARTING_STACK / BIG_BLIND

NUM_ROUNDS = 1000
TOTAL_TIME_BUDGET = 180.0
TIME_SAFETY_MARGIN = 5.0
FAST_MODE_THRESHOLD = 0.70

RANKS = '23456789TJQKA'
SUITS = 'shdc'

# Postflop equity thresholds (50BB heads-up context)
EQUITY_VALUE_BET   = 0.62
EQUITY_CHECK_CALL  = 0.42
EQUITY_BLUFF_BOARD = 0.30
EQUITY_FOLD        = 0.25

# Redraw thresholds — hole redraws reveal a card so the bar is higher
REDRAW_HOLE_MARGIN  = 0.08
REDRAW_BOARD_MARGIN = 0.04

COMMITMENT_FRACTION = 0.40

# Preflop equity tiers aligned to HANDS.json percentages
PREFLOP_PREMIUM  = 0.72   # JJ+, AKs
PREFLOP_STRONG   = 0.62   # TT, AKo, AQs, AJs
PREFLOP_GOOD     = 0.54   # 88-99, AQo, broadway suited
PREFLOP_PLAYABLE = 0.48   # small pairs, suited connectors
PREFLOP_MARGINAL = 0.44   # weak suited, low connectors


# =============================================================================
# CARD UTILITIES
# =============================================================================

_RANK_IDX = {c: i for i, c in enumerate(RANKS)}
_SUIT_IDX = {c: i for i, c in enumerate(SUITS)}


def card_to_int(card_str):
    """Convert engine card string (e.g. 'Ah', 'Td') to integer 0-51."""
    return _SUIT_IDX[card_str[1]] * 13 + _RANK_IDX[card_str[0]]


def int_to_card(card_int):
    """Convert integer 0-51 back to engine card string."""
    return RANKS[card_int % 13] + SUITS[card_int // 13]


def rank_of(card_int):
    return card_int % 13


def suit_of(card_int):
    return card_int // 13


def get_stub(hole_cards, board_cards):
    """Return cards not in hero's hand or on the board."""
    used = set(hole_cards) | set(board_cards)
    return [c for c in range(52) if c not in used]


# =============================================================================
# HAND EVALUATION (optimized — no dicts/sets in hot path)
# =============================================================================

def hand_rank_5(c0, c1, c2, c3, c4):
    """
    Evaluate exactly 5 cards and return a comparable integer rank.
    Higher = better. Category gaps ensure no overlap:
      8M = straight flush, 7M = quads, 6M = full house, 5M = flush,
      4M = straight, 3M = trips, 2M = two pair, 1M = pair, 0 = high card
    """
    ranks = sorted((c0 % 13, c1 % 13, c2 % 13, c3 % 13, c4 % 13), reverse=True)
    r0, r1, r2, r3, r4 = ranks

    is_flush = (c0 // 13 == c1 // 13 == c2 // 13 == c3 // 13 == c4 // 13)

    all_diff = r0 != r1 and r1 != r2 and r2 != r3 and r3 != r4
    is_straight = False
    straight_high = 0
    if all_diff:
        if r0 - r4 == 4:
            is_straight = True
            straight_high = r0
        elif (r0, r1, r2, r3, r4) == (12, 3, 2, 1, 0):
            is_straight = True
            straight_high = 3  # wheel

    if is_straight and is_flush:
        return 8_000_000 + straight_high

    if r0 == r1 == r2 == r3:
        return 7_000_000 + r0 * 13 + r4
    if r1 == r2 == r3 == r4:
        return 7_000_000 + r1 * 13 + r0

    if r0 == r1 == r2 and r3 == r4:
        return 6_000_000 + r0 * 13 + r3
    if r0 == r1 and r2 == r3 == r4:
        return 6_000_000 + r2 * 13 + r0

    if is_flush:
        return 5_000_000 + r0 * 28561 + r1 * 2197 + r2 * 169 + r3 * 13 + r4

    if is_straight:
        return 4_000_000 + straight_high

    if r0 == r1 == r2:
        return 3_000_000 + r0 * 169 + r3 * 13 + r4
    if r1 == r2 == r3:
        return 3_000_000 + r1 * 169 + r0 * 13 + r4
    if r2 == r3 == r4:
        return 3_000_000 + r2 * 169 + r0 * 13 + r1

    if r0 == r1 and r2 == r3:
        return 2_000_000 + r0 * 169 + r2 * 13 + r4
    if r0 == r1 and r3 == r4:
        return 2_000_000 + r0 * 169 + r3 * 13 + r2
    if r1 == r2 and r3 == r4:
        return 2_000_000 + r1 * 169 + r3 * 13 + r0

    if r0 == r1:
        return 1_000_000 + r0 * 2197 + r2 * 169 + r3 * 13 + r4
    if r1 == r2:
        return 1_000_000 + r1 * 2197 + r0 * 169 + r3 * 13 + r4
    if r2 == r3:
        return 1_000_000 + r2 * 2197 + r0 * 169 + r1 * 13 + r4
    if r3 == r4:
        return 1_000_000 + r3 * 2197 + r0 * 169 + r1 * 13 + r2

    return r0 * 28561 + r1 * 2197 + r2 * 169 + r3 * 13 + r4


def best_hand_rank(cards):
    """From 5-7 cards, find the best 5-card hand rank (C(7,5) = 21 combos max)."""
    if len(cards) == 5:
        return hand_rank_5(cards[0], cards[1], cards[2], cards[3], cards[4])
    return max(hand_rank_5(a, b, c, d, e) for a, b, c, d, e in combinations(cards, 5))


# =============================================================================
# PREFLOP LOOKUP (HANDS.json — loaded once at module import)
# =============================================================================

_PREFLOP_TABLE = [50.0] * (13 * 13 * 2)


def _load_preflop_table():
    """Parse HANDS.json into a flat lookup array keyed by (hi*13+lo)*2+suited."""
    path = os.path.join(os.path.dirname(__file__), 'HANDS.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                tokens = line.split()
                if len(tokens) < 3:
                    continue
                combo = tokens[1].upper()
                pct = float(tokens[2].rstrip('%'))
                if len(combo) == 2:
                    ri = _RANK_IDX.get(combo[0])
                    if ri is not None:
                        k = (ri * 13 + ri) * 2
                        _PREFLOP_TABLE[k] = pct
                        _PREFLOP_TABLE[k + 1] = pct
                elif len(combo) == 3:
                    a, b = _RANK_IDX.get(combo[0]), _RANK_IDX.get(combo[1])
                    if a is not None and b is not None:
                        hi, lo = (a, b) if a >= b else (b, a)
                        s = 1 if combo[2] == 'S' else 0
                        _PREFLOP_TABLE[(hi * 13 + lo) * 2 + s] = pct
    except FileNotFoundError:
        pass


_load_preflop_table()


def get_preflop_equity(card_a, card_b):
    """O(1) preflop equity from HANDS.json. Returns 0.0-1.0."""
    r1, r2 = card_a % 13, card_b % 13
    hi, lo = (r1, r2) if r1 >= r2 else (r2, r1)
    suited = 1 if (hi != lo and card_a // 13 == card_b // 13) else 0
    return _PREFLOP_TABLE[(hi * 13 + lo) * 2 + suited] / 100.0


# =============================================================================
# EQUITY ESTIMATION (Monte Carlo)
# =============================================================================

def estimate_equity(hero_cards, board_cards, num_simulations=300):
    """
    MC equity vs uniform random opponent.
    Uses random.sample (faster than np.random.choice for small draws).
    """
    stub = get_stub(hero_cards, board_cards)
    to_deal = 5 - len(board_cards)
    draw_n = 2 + to_deal
    wins = 0.0
    h = list(hero_cards)
    b = list(board_cards)

    for _ in range(num_simulations):
        drawn = random.sample(stub, draw_n)
        full_board = b + drawn[2:]
        hr = best_hand_rank(h + full_board)
        vr = best_hand_rank([drawn[0], drawn[1]] + full_board)
        if hr > vr:
            wins += 1.0
        elif hr == vr:
            wins += 0.5

    return wins / num_simulations


# =============================================================================
# BOARD TEXTURE ANALYSIS
# =============================================================================

def analyze_board(board_cards):
    """Classify board texture for redraw and strategy heuristics."""
    if not board_cards:
        return None

    ranks = [c % 13 for c in board_cards]
    suits = [c // 13 for c in board_cards]

    suit_counts = {}
    for s in suits:
        suit_counts[s] = suit_counts.get(s, 0) + 1
    rank_counts = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1

    unique_ranks = sorted(set(ranks))
    is_connected = False
    if len(unique_ranks) >= 3:
        for i in range(len(unique_ranks) - 2):
            if unique_ranks[i + 2] - unique_ranks[i] <= 4:
                is_connected = True
                break

    return {
        'high_card_count': sum(1 for r in ranks if r >= 8),
        'is_monotone': len(suit_counts) == 1,
        'is_two_tone': len(suit_counts) == 2,
        'is_paired': any(c >= 2 for c in rank_counts.values()),
        'is_connected': is_connected,
        'max_rank': max(ranks),
        'suit_counts': suit_counts,
    }


# =============================================================================
# POT CONTEXT
# =============================================================================

def compute_pot_context(round_state, active):
    """Extract pot geometry and commitment from round state."""
    my_pip = round_state.pips[active]
    opp_pip = round_state.pips[1 - active]
    my_stack = round_state.stacks[active]
    pot = 2 * STARTING_STACK - round_state.stacks[0] - round_state.stacks[1]
    to_call = max(opp_pip - my_pip, 0)
    pot_after_call = pot + to_call
    pot_odds = to_call / pot_after_call if pot_after_call > 0 else 0.0
    committed_frac = (STARTING_STACK - my_stack) / STARTING_STACK

    return {
        'pot': pot,
        'my_pip': my_pip,
        'opp_pip': opp_pip,
        'to_call': to_call,
        'pot_after_call': pot_after_call,
        'pot_odds': pot_odds,
        'my_stack': my_stack,
        'committed_frac': committed_frac,
        'am_committed': committed_frac >= COMMITMENT_FRACTION,
    }


# =============================================================================
# BET SIZING
# =============================================================================

def select_raise_amount(equity, pot_ctx, round_state):
    """
    Pot-relative raise sizing. Returns raise-to total (matching raise_bounds API).
    Three tiers: 1/3 pot (probe), 2/3 pot (value), full pot (polar).
    Auto-shoves when the raise commits >70% of remaining stack.
    """
    min_raise, max_raise = round_state.raise_bounds()
    if max_raise <= min_raise:
        return min_raise

    if equity >= 0.75 or equity < 0.30:
        frac = 1.0
    elif equity >= EQUITY_VALUE_BET:
        frac = 0.67
    else:
        frac = 0.33

    additional = int(pot_ctx['pot_after_call'] * frac)
    raise_to = pot_ctx['my_pip'] + pot_ctx['to_call'] + additional
    amount = max(min_raise, min(raise_to, max_raise))

    cost = amount - pot_ctx['my_pip']
    if cost > pot_ctx['my_stack'] * 0.70:
        amount = max_raise

    return amount


# =============================================================================
# REDRAW EVALUATION (heuristic — full MC per stub card is too expensive)
# =============================================================================

def evaluate_redraw_options(hero_cards, board_cards, current_equity):
    """
    Lightweight redraw evaluation using board texture and hand fit.
    Returns the best option dict or None if no redraw clears the margin.
    """
    board_texture = analyze_board(board_cards)
    if board_texture is None:
        return None

    best = None
    best_gain = 0.0
    hero_ranks = [c % 13 for c in hero_cards]
    hero_suits = [c // 13 for c in hero_cards]
    hero_high = max(hero_ranks)
    board_ranks = [c % 13 for c in board_cards]
    dom_suit = max(board_texture['suit_counts'], key=board_texture['suit_counts'].get)

    # --- Hole card redraws ---
    for idx in range(2):
        r = hero_ranks[idx]
        other_r = hero_ranks[1 - idx]
        s = hero_suits[idx]
        gain = 0.0

        # Low kicker with strong anchor — replace the weak card
        if other_r >= 10 and r <= 5:
            gain += 0.06 + 0.01 * (10 - r)

        # Card doesn't connect to board at all
        connects = r in board_ranks or any(abs(r - br) <= 1 for br in board_ranks)
        if not connects and r < 8:
            gain += 0.04

        # Potential to draw into a flush
        if board_texture['suit_counts'][dom_suit] >= 3 and s != dom_suit:
            gain += 0.03

        # Revealing a high card leaks valuable info to opponent
        if r >= 10:
            gain -= 0.03

        # Don't redraw when we already have strong equity
        if current_equity >= EQUITY_VALUE_BET:
            gain -= 0.05

        if gain > REDRAW_HOLE_MARGIN and gain > best_gain:
            best_gain = gain
            best = {'type': 'hole', 'index': idx,
                    'expected_equity': current_equity + gain, 'gain': gain}

    # --- Board card redraws ---
    for bi in range(len(board_cards)):
        br = board_ranks[bi]
        bs = board_cards[bi] // 13
        sv = 0.0

        # High board card not connecting to us likely helps opponent
        if br >= 8 and abs(br - hero_high) > 2:
            sv += 0.04 * (br - 7)

        # Don't destroy our flush
        if bs in hero_suits and board_texture['is_monotone']:
            sv -= 0.15

        # Paired board: disrupting opponent's trips/sets
        if board_texture['is_paired'] and \
           sum(1 for c in board_cards if c % 13 == br) >= 2:
            sv += 0.05

        # Low equity makes board disruption more valuable
        if current_equity < EQUITY_BLUFF_BOARD:
            sv += 0.03

        if sv > REDRAW_BOARD_MARGIN and sv > best_gain:
            best_gain = sv
            best = {'type': 'board', 'index': bi,
                    'expected_equity': current_equity + sv, 'gain': sv}

    return best


# =============================================================================
# OPPONENT MODEL
# =============================================================================

class OpponentModel:
    """Tracks opponent tendencies across the match for future exploitation."""

    def __init__(self):
        self.hands_seen = 0
        self.vpip_count = 0
        self.total_invested = 0.0
        self.redraw_count = 0

    @property
    def vpip(self):
        return self.vpip_count / max(self.hands_seen, 1)

    @property
    def avg_investment(self):
        return self.total_invested / max(self.hands_seen, 1)

    @property
    def aggression_ratio(self):
        """Fraction of stack committed on average — higher = more aggressive."""
        return self.avg_investment / STARTING_STACK

    def update(self, terminal_state, active):
        self.hands_seen += 1
        prev = terminal_state.previous_state
        if prev is not None and hasattr(prev, 'stacks'):
            opp = 1 - active
            invested = STARTING_STACK - prev.stacks[opp]
            self.total_invested += invested
            if invested > BIG_BLIND:
                self.vpip_count += 1
            if hasattr(prev, 'redraws_used') and prev.redraws_used[opp]:
                self.redraw_count += 1

    def is_passive(self):
        return self.aggression_ratio < 0.15 and self.hands_seen > 30

    def is_aggressive(self):
        return self.aggression_ratio > 0.35 and self.hands_seen > 30


# =============================================================================
# BOT CLASS
# =============================================================================

class Bot():
    """Poker bot for Hold'em + Redraw at 50BB / 2-5 blinds / 1000 hands."""

    def __init__(self):
        self.match_start_time = time.time()
        self.time_used = 0.0
        self.opponent = OpponentModel()

        self.hero_cards = []
        self.is_button = False
        self.has_redrawn = False
        self.hand_number = 0
        self._lock_in_win = False

    # -----------------------------------------------------------------
    # REQUIRED INTERFACE METHODS
    # -----------------------------------------------------------------

    def handle_new_round(self, game_state, round_state, active):
        """Called at the start of each hand."""
        self.hand_number = game_state.round_num
        self.hero_cards = [card_to_int(c) for c in round_state.hands[active]
                          if c and c != '??']
        self.is_button = (active == 0)
        self.has_redrawn = False

        remaining = NUM_ROUNDS - self.hand_number + 1
        self._lock_in_win = game_state.bankroll > remaining * BIG_BLIND

    def handle_round_over(self, game_state, terminal_state, active):
        """Called when a hand ends."""
        self.time_used = time.time() - self.match_start_time
        self.opponent.update(terminal_state, active)

    def get_action(self, game_state, round_state, active):
        """Main decision dispatcher."""
        legal = round_state.legal_actions()

        if self._lock_in_win:
            return CheckAction() if CheckAction in legal else FoldAction()

        street = round_state.street
        self.hero_cards = [card_to_int(c) for c in round_state.hands[active]
                          if c and c != '??']
        board_cards = [card_to_int(c) for c in round_state.board
                      if c and c != '??']

        if len(self.hero_cards) < 2:
            return CheckAction() if CheckAction in legal else FoldAction()

        fast_mode = (self.time_used / TOTAL_TIME_BUDGET) > FAST_MODE_THRESHOLD

        if street == 0:
            action = self._preflop_action(round_state, active, legal)
        elif street == 5:
            action = self._river_action(round_state, active, legal, board_cards, fast_mode)
        else:
            action = self._postflop_action(round_state, active, legal, board_cards, fast_mode)

        if isinstance(action, FoldAction) and CheckAction in legal:
            return CheckAction()
        return action

    # -----------------------------------------------------------------
    # STREET-SPECIFIC STRATEGIES
    # -----------------------------------------------------------------

    def _preflop_action(self, round_state, active, legal):
        """Preflop strategy driven by HANDS.json equity lookup — zero MC cost."""
        equity = get_preflop_equity(self.hero_cards[0], self.hero_cards[1])
        ctx = compute_pot_context(round_state, active)

        if ctx['to_call'] > 0:
            if equity >= PREFLOP_PREMIUM:
                if RaiseAction in legal:
                    return RaiseAction(select_raise_amount(0.80, ctx, round_state))
                return CallAction()

            if equity >= PREFLOP_STRONG:
                if self.is_button and RaiseAction in legal:
                    return RaiseAction(select_raise_amount(0.70, ctx, round_state))
                return CallAction()

            if equity >= PREFLOP_GOOD:
                if self.is_button and RaiseAction in legal:
                    return RaiseAction(select_raise_amount(0.60, ctx, round_state))
                if ctx['to_call'] <= 3 * BIG_BLIND:
                    return CallAction()
                return FoldAction()

            if equity >= PREFLOP_PLAYABLE:
                if self.is_button and ctx['to_call'] <= 2.5 * BIG_BLIND:
                    return CallAction()
                if not self.is_button and ctx['to_call'] <= 1.5 * BIG_BLIND:
                    return CallAction()
                return FoldAction()

            if equity >= PREFLOP_MARGINAL:
                if not self.is_button and ctx['to_call'] <= BIG_BLIND:
                    return CallAction()
                return FoldAction()

            return FoldAction()

        # to_call == 0: BB checked to (SB limped)
        if equity >= PREFLOP_STRONG and RaiseAction in legal:
            return RaiseAction(select_raise_amount(0.70, ctx, round_state))
        return CheckAction()

    def _postflop_action(self, round_state, active, legal, board_cards, fast_mode):
        """Postflop (flop + turn) strategy with MC equity and optional redraw."""
        ctx = compute_pot_context(round_state, active)

        sims = 150 if fast_mode else 300
        equity = estimate_equity(self.hero_cards, board_cards, num_simulations=sims)

        redraw = None
        if not self.has_redrawn and RedrawAction in legal:
            redraw = evaluate_redraw_options(self.hero_cards, board_cards, equity)

        base = self._choose_betting_action(equity, ctx, legal, round_state, active)

        if redraw and redraw['gain'] > 0:
            self.has_redrawn = True
            if isinstance(base, FoldAction):
                base = CheckAction() if CheckAction in legal else CallAction()
            return RedrawAction(redraw['type'], redraw['index'], base)

        return base

    def _river_action(self, round_state, active, legal, board_cards, fast_mode):
        """River strategy — no redraw, pure equity-based play."""
        ctx = compute_pot_context(round_state, active)
        sims = 150 if fast_mode else 400
        equity = estimate_equity(self.hero_cards, board_cards, num_simulations=sims)
        return self._choose_betting_action(equity, ctx, legal, round_state, active)

    # -----------------------------------------------------------------
    # SHARED BETTING LOGIC
    # -----------------------------------------------------------------

    def _choose_betting_action(self, equity, ctx, legal, round_state, active):
        """Select bet/check/call/fold based on equity, pot odds, and commitment."""
        if ctx['to_call'] > 0:
            # Pot-committed: never fold
            if ctx['am_committed']:
                if RaiseAction in legal and equity >= EQUITY_VALUE_BET:
                    return RaiseAction(select_raise_amount(equity, ctx, round_state))
                return CallAction()

            required = ctx['pot_odds']

            if equity >= EQUITY_VALUE_BET and RaiseAction in legal:
                return RaiseAction(select_raise_amount(equity, ctx, round_state))
            if equity >= required and equity >= EQUITY_FOLD:
                return CallAction()
            return FoldAction()

        # No bet facing us — check or bet
        if equity >= EQUITY_VALUE_BET and RaiseAction in legal:
            return RaiseAction(select_raise_amount(equity, ctx, round_state))

        if equity < 0.20 and RaiseAction in legal and random.random() < 0.25:
            return RaiseAction(select_raise_amount(equity, ctx, round_state))

        return CheckAction()
