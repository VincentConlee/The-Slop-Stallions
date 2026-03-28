'''
This file contains the base class that you should implement for your pokerbot.
'''
import pkrbot
from .actions import FoldAction, CheckAction
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

    def _evaluate_hand(self, hole_cards, board_cards):
        pass
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
        pass