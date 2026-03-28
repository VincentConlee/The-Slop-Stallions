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

REDRAW_HOLE_MARGIN = 0.08
REDRAW_BOARD_MARGIN = 0.04


def analyze_board(board_cards):
    if not board_cards:
        return None
    
    ranks = [rank_of(c) for c in board_cards]
    suits = [suit_of(c) for c in board_cards]

    suit_coutns = {}
    for s in suits:
        suit_counts[s] = suit_counts.get(s, 0) + 1

    rank_counts = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1
    
    unique_ranks = sorted(set(ranks))

class Bot():
    '''
    The base class for a pokerbot.
    '''
    def __init__(self):
        self._ranks = "23456789TJQKA"
        self._rank_to_idx = {rank: idx for idx, rank in enumerate(self._ranks)}
        # Fast fixed-size table: key = ((hi_rank * 13 + lo_rank) * 2 + suited_bit)
        self._preflop_pct = [None] * (13 * 13 * 2)
        self._default_preflop_pct = 50.0
        self._load_preflop_lookup()

        self.opponent_behavior = {
            'aggression': 0.5,  # 0 (passive) to 1 (aggressive)
            'personality': 0,   # 0 Scared, 1 Cautious, 2 Balanced, 3 Aggressive
            'hand_strength': 0.5,  # 0 (weak) to 1 (strong)
            'redraw_tendency': 0.5,  # 0 (never redraw) to 1 (always redraw)
        } 

    def handle_new_round(self, game_state, round_state, active):
        '''
        Called when a new round starts. Called NUM_ROUNDS times.

        Arguments:
        game_state: the GameState object.
        round_state: the RoundState object.
        active: your player's index.

        Returns:
        Nothing.
        '''
        RANKS = "23456789TJQKA"
        SUITS = "cdhs"  

        def new_deck():
            return [r + s for r in RANKS for s in SUITS]
        
        self.deck = new_deck()

        if(game_state.bankroll >= 250001):
            self.always_fold = True
        
        self.hole_cards = round_state.hands[active]
        self.used_redraw = 0
        

        

    def handle_round_over(self, game_state, terminal_state, active):
        '''
        Called when a round ends. Called NUM_ROUNDS times.

        Arguments:
        game_state: the GameState object.
        terminal_state: the TerminalState object.
        active: your player's index.

        Returns:
        Nothing.
        '''
        # Update agression based on bet amount
        from skeleton.states import STARTING_STACK
        total_bet = STARTING_STACK - terminal_state.stacks[1-active]
        self.opponent_behavior['aggression'] = ((total_bet / STARTING_STACK) + self.opponent_behavior['aggression']) / 2

        # Update redraw tendency
        self.opponent_behavior['redraw_tendency'] = (self.used_redraw + self.opponent_behavior['redraw_tendency']) / 2



    def get_action(self, game_state, round_state, active):
        '''
        Where the magic happens - your code should implement this function.
        Called any time the engine needs an action from your bot.

        Arguments:
        game_state: the GameState object.
        round_state: the RoundState object.
        active: your player's index.

        Returns:    
        Your action (FoldAction, CallAction, CheckAction, RaiseAction, or RedrawAction).
        '''
        #TODO: make the base rate have some randomness to it so we don't always do the same thing with the same hand strength
        BASERAISE = 50
        AGGRESSIONMULTIPLIER = 0.5 #how aggressive the opponent is, can be used to adjust bet sizing to maximize value against passive opponents and minimize losses against aggressive opponents
        #what are my available actions?
        legal_actions = self._get_legal_actions(round_state)
        

        #what is my current hand stregth?
        hand_strength = self._evaluate_hand(round_state.hands[active], round_state.board)

        
        #add a randomness factor to my decision making so I don't always do the same thing with the same hand strength sometimes will bluff with weak hands or slow play with strong hands
        if hand_strength > 0.8: #strong hand, bet/raise
            #add randomness to raise etc... so most the time we raise with strong hands but sometimes we check or call to mix it up
            if RaiseAction in legal_actions:
                return RaiseAction(self._select_bet_size)  # example bet size
            elif CheckAction in legal_actions:
                return CheckAction()
            else:
                return FoldAction()  # fold if we can't bet or check
        elif hand_strength > 0.5: #decent hand, call/check
            if CheckAction in legal_actions:
                return CheckAction()
            elif CallAction in legal_actions:
                return CallAction()
            else:
                return FoldAction()  # fold if we can't check or call
        else: #weak hand, check/fold
            if CheckAction in legal_actions:
                return CheckAction()
            else:
                return FoldAction()  # fold if we can't check

            
        
        # raise NotImplementedError('get_action')

    def _get_legal_actions(self, round_state):
        '''
        Returns legal action classes for the current state with custom fold/check rule:
        - If check is legal, fold is removed.
        - If check is not legal, fold is included.
        '''
        actions = set(round_state.legal_actions())

        if CheckAction in actions:
            actions.discard(FoldAction)

        return actions

    def _preflop_key_from_parts(self, rank_a, rank_b, suited):
        idx_a = self._rank_to_idx[rank_a]
        idx_b = self._rank_to_idx[rank_b]
        hi = idx_a if idx_a >= idx_b else idx_b
        lo = idx_b if idx_a >= idx_b else idx_a

        suited_bit = 0 if hi == lo else (1 if suited else 0)
        return ((hi * 13 + lo) * 2) + suited_bit

    def _preflop_key_from_cards(self, card_a, card_b):
        rank_a = card_a[0].upper()
        rank_b = card_b[0].upper()
        suited = card_a[1].lower() == card_b[1].lower()
        return self._preflop_key_from_parts(rank_a, rank_b, suited)

    def _load_preflop_lookup(self, table_path=None):
        if table_path is None:
            table_path = os.path.join(os.path.dirname(__file__), 'HANDS.json')

        with open(table_path, 'r', encoding='utf-8') as table_file:
            for raw_line in table_file:
                line = raw_line.strip()
                if not line:
                    continue

                tokens = line.split()
                if len(tokens) < 3:
                    continue

                combo = tokens[1].upper()
                pct = float(tokens[2].rstrip('%'))

                if len(combo) == 2:
                    # Pair, e.g. AA
                    key_off = self._preflop_key_from_parts(combo[0], combo[1], False)
                    key_suited = self._preflop_key_from_parts(combo[0], combo[1], True)
                    self._preflop_pct[key_off] = pct
                    self._preflop_pct[key_suited] = pct
                elif len(combo) == 3:
                    # Non-pair, e.g. AKs / AKo
                    suited = combo[2] == 'S'
                    key = self._preflop_key_from_parts(combo[0], combo[1], suited)
                    self._preflop_pct[key] = pct

    def get_preflop_percent(self, hole_cards):
        '''
        Returns preflop equity percent for two hole cards, e.g. 64.65 for AKo.
        '''
        if not hole_cards or len(hole_cards) < 2:
            return self._default_preflop_pct

        key = self._preflop_key_from_cards(hole_cards[0], hole_cards[1])
        value = self._preflop_pct[key]
        return self._default_preflop_pct if value is None else value

    def _evaluate_hand(self, hole_cards, board_cards):
        _ = board_cards
        # Normalized 0..1 strength for fast preflop decisions.
        return self.get_preflop_percent(hole_cards) / 100.0
    def _estimate_equity(self, hole_cards, board_cards, num_simulations):
        """
        Monte Carlo equity estimate against a uniform random opponent.
 
        Deals random opponent hole cards and remaining board cards,
        evaluates both hands, and counts win/tie/loss.
 
         Args:
            hero_cards:      list of int, hero's hole cards
            board_cards:     list of int, current board cards (0-5)
            num_simulations: number of MC rollouts
 
        Returns:
            float, equity in [0.0, 1.0]
        """
        stub= get_stub(hero_cards, board_cards)
        board_to_deal = 5 - len(board_cards)
        wins = 0.0

        for _ in range(num_simulations):
            drawn = np.random.choice(stub, size=2 + board_to_deal, replace=False)
        villain_cards = drawn[:2]
        future_board  = drawn[2:]
 
        full_board = list(board_cards) + list(future_board)
        hero_rank    = best_hand_rank(list(hero_cards) + full_board)
        villain_rank = best_hand_rank(list(villain_cards) + full_board)
 
        if hero_rank > villain_rank:
            wins += 1.0
        elif hero_rank == villain_rank:
            wins += 0.5
 
        return wins / num_simulations
    def _evaluate_redraw_options(self, hole_cards, board_cards, stub):
        """
    Evaluate all legal redraw targets and return the best option.
 
    For HOLE card redraws: iterate over stub cards, compute average equity
    after replacing each hole card. This is a full MC computation.
 
    For BOARD card redraws: use a lighter heuristic — estimate how much
    the board helps a typical opponent range vs. us, and whether swapping
    a specific board card improves our texture.
 
    Args:
        hero_cards:     list of 2 ints
        board_cards:    list of 3-4 ints (flop or turn)
        current_equity: float, our equity if we keep everything
        num_sims:       MC rollouts per stub card for hole redraws
 
    Returns:
        best_option: dict with keys:
            'type':            'hole' or 'board' or None
            'index':           int index of card to swap
            'expected_equity': float, estimated equity after swap
            'gain':            float, equity improvement over keeping
        or None if no redraw is profitable
    """
        stub = get_stub(hero_cards, board_cards)
        best = None
        best_gain = 0.0

        for hole_idx in range(2):
            equity_sum = 0.0
            other_hole = hero_cards[1-hole_idx]

            for swap_card in stub:
                new_hero = [other_hole, swap_card]
                eq = estimate_equity(new_hero, board_Cards, num_simulations = num_sims)
                equity_sum += eq
            avg_equity = equity_sum / len(stub)
            gain = avg_equity - current_equity

            if gain > REDRAW_HOLE_MARGIN and gain > best_gain:
                best_gain = gain
                best = {
                    'type': 'hole',
                    'index': hole_idx,
                    'expected_equity': avg_equity,
                    'gain': gain,
                }
        board_texture = analyze_board(board_cards)
        if board_texture:
            hero_ranks = [rank_of(c) for c in hero_cards]
            hero_high = max(hero_ranks)

            for board_idx in range(len(board_cards)):
                board_rank = rank_of(board_cards[board_idx])
                swap_value = 0.0

                if board_rank >= 8 and abs(board_rank - hero_high) > 2:
                    swap_value +=0.04 * (board_rank - 7)
                
                hero_suits = [suit_of(c) for c in hero_cards]
                board_suit = suit_of(board_cards[board_idx])
                if board_suit in hero_suits and board_texture['is_monotone']:
                    swap_value -=0.15 # dont destroy flush/draw

                #if board paired, swapping one of the pair cards disrupts sets/trips
                if board_texture['is_paired'] and \
                sum(1 for c in board_cards if rank_of(c) == board_rank) >=2:
                    swap_value += 0.05

                if current_equity < EQUITY_BLUFF_BOARD:
                    swap_value += 0.03
                
                if swap_value > REDRAW_BOARD_MARGIN and swap_values > best_gain:
                    best_gain = swap_value
                    best = {
                        'type': 'board',
                        'index': board_idx,
                        'expected_equity': current_equity + swap_value,
                        'gain': swap_value,
                    }
        return best
    def _board_texture(self, board_cards):
        pass
    def _opponent_range_estimate(self, street, action_history):
        pass
    def _pot_odds_and_commitment(self, roundstate, active):
        pass
    def _select_bet_size(self, equity, pot, stack, street):
        '''
        Returns a chip amount sized from:
        - equity (0..1)
        - pot size
        - remaining stack
        - street (0, 3, 4, 5)
        - opponent aggression in self.opponent_behavior['aggression'] (0..1)

        The model sizes up for value against passive opponents and sizes down
        against aggressive opponents to control downside variance.
        '''
        if stack <= 0:
            return 0

        # Clamp inputs into safe ranges.
        equity = max(0.0, min(1.0, float(equity)))
        pot = max(0.0, float(pot))
        stack = max(0.0, float(stack))
        aggression = float(self.opponent_behavior.get('aggression', 0.5))
        aggression = max(0.0, min(1.0, aggression))

        # Later streets allow larger sizing because ranges are more defined.
        street_factor = {
            0: 0.85,  # preflop
            3: 1.00,  # flop
            4: 1.15,  # turn
            5: 1.30,  # river
        }.get(street, 1.00)

        # Value signal is stronger as equity moves above 0.5.
        value_signal = max(0.0, (equity - 0.5) / 0.5)

        # Base pot fraction from equity.
        pot_fraction = 0.25 + (0.65 * value_signal)

        # Versus passive players, size up for value.
        passive_bonus = (1.0 - aggression) * (0.20 + 0.25 * value_signal)

        # Versus aggressive players, reduce size to control losses.
        aggressive_discount = aggression * (0.15 + 0.25 * (1.0 - value_signal))

        pot_fraction += passive_bonus
        pot_fraction -= aggressive_discount

        # Controlled semi-bluff region.
        if 0.38 <= equity <= 0.55:
            pot_fraction += (1.0 - aggression) * 0.12
            pot_fraction -= aggression * 0.08

        # Weak hands should mostly keep pot smaller.
        if equity < 0.40:
            pot_fraction = min(pot_fraction, 0.15 + (0.35 * (1.0 - aggression)))

        # Keep practical bounds before street scaling.
        pot_fraction = max(0.10, min(1.25, pot_fraction))
        pot_fraction *= street_factor

        # If pot is tiny (or unknown), anchor to blind-based sizing.
        if pot <= 0:
            desired = BIG_BLIND * (2 if equity > 0.70 else 1)
        else:
            desired = int(round(pot * pot_fraction))

        # Strong value spot against passive opponents: allow larger sizing.
        if equity >= 0.82 and aggression <= 0.40 and pot > 0:
            desired = max(desired, int(round(pot * 1.10)))

        # Final stack and floor constraints.
        desired = max(BIG_BLIND, desired)
        desired = min(desired, int(stack))

        return int(desired)