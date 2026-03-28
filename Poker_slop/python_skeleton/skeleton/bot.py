'''
This file contains the base class that you should implement for your pokerbot.
'''
import pkrbot
from .actions import FoldAction, CheckAction

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
        
        deck = new_deck()

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