'''
This file contains the base class that you should implement for your pokerbot.
'''
import pkrbot

class Bot():
    '''
    The base class for a pokerbot.
    '''
    def __init__(self):
        RANKS = "23456789TJQKA"
        SUITS = "cdhs"  

        def new_deck():
            return [r + s for r in RANKS for s in SUITS]
        
        deck = new_deck()

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
        raise NotImplementedError('handle_new_round')

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
        raise NotImplementedError('get_action')

    def _evaluate_hand(self, hole_cards, board_cards):
        pass
    def _estimate_equity(self, hole_cards, board_cards, num_simulations):
        pass
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