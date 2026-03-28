'''
This file contains the base class that you should implement for your pokerbot.
'''
import os
import pkrbot
from .actions import FoldAction, CheckAction, CallAction, RaiseAction

STARTING_STACK = 400
BIG_BLIND = 5
SMALL_BLIND = 2
EFFECTIVE_BB = STARTING_STACK / BIG_BLIND

NUM_ROUNDS = 1000
TOTAL_TIME_BUDGET = 180.0
TIME_SAFETY_MARGIN = 5.0
FAST_MODE_THRESHOLD = 0.70

REDRAW_HOLE_MARGIN = 0.08
REDRAW_BOARD_MARGIN = 0.04

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
        raise NotImplementedError('handle_round_over')

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
        BASERAISE = 2
        AGGRESSIONMULTIPLIER = 1.5
        #what are my available actions?
        legal_actions = self._get_legal_actions(round_state)
        

        #what is my current hand stregth?
        hand_strength = self._evaluate_hand(round_state.hands[active], round_state.board)

        
        #add a randomness factor to my decision making so I don't always do the same thing with the same hand strength sometimes will bluff with weak hands or slow play with strong hands
        if hand_strength > 0.8: #strong hand, bet/raise
            #add randomness to raise etc... so most the time we raise with strong hands but sometimes we check or call to mix it up
            if RaiseAction in legal_actions:
                return RaiseAction(BASERAISE * AGGRESSIONMULTIPLIER)  # example bet size
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
        if (board_cards.length() == 0)
    def _evaluate_redraw_options(self, hole_cards, board_cards, stub):
        pass  
    def _board_texture(self, board_cards):
        pass
    def _opponent_range_estimate(self, street, action_history):
        pass
    def _pot_odds_and_commitment(self, roundstate, active):
        pass
    def _select_bet_size(self, equity, pot, stack, street):
        pass