from flask import Flask, request, jsonify, Blueprint

# 1. Define the blueprint
showdown_bp = Blueprint('showdown', __name__)


# 2. Attach routes to the blueprint
@showdown_bp.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200


@showdown_bp.route('/move', methods=['POST'])
def move():
    # Force=True parses the JSON safely even if the game server headers are missing
    state = request.get_json(force=True, silent=True) or {}

    legal_actions = state.get('legal_actions', [])
    round_name = state.get('round')

    # Default to 0 instead of None to prevent Math errors
    my_card = state.get('your_number', 0)
    comm_card = state.get('community_number')
    to_call = state.get('to_call', 0)
    min_raise = state.get('min_raise_to')
    max_raise = state.get('max_raise_to')
    rule = state.get('table_rule', 'standard')

    # --- BULLETPROOF HELPER FUNCTIONS ---
    def do_raise(amount):
        if min_raise is not None and max_raise is not None:
            valid_amount = max(min_raise, min(amount, max_raise))
            if "raise" in legal_actions:
                return jsonify({"action": "raise", "amount": valid_amount})
            if "bet" in legal_actions:
                return jsonify({"action": "bet", "amount": valid_amount})
        return do_call()

    def do_call():
        if "call" in legal_actions:
            return jsonify({"action": "call"})
        return do_check()

    def do_check():
        if "check" in legal_actions:
            return jsonify({"action": "check"})
        return jsonify({"action": "fold"})

    def do_fold():
        if "fold" in legal_actions:
            return jsonify({"action": "fold"})
        return do_check()

    # --- THE BRAIN ---
    def decide_action():
        # Identify who we are playing against from the players array
        opponent = "unknown"
        for p in state.get('players', []):
            name = p.get('name', '')
            if name != 'you' and name != '':
                opponent = name

        # ==========================================
        # RULE 1: LOW BALL (Inverted) - vs Nadia
        # ==========================================
        if rule == 'low_ball':
            if opponent == "Nadia":
                if round_name == "pre_reveal":
                    if to_call <= 2:  # No major raise yet, steal the pot
                        if my_card <= 9: return do_raise(min_raise if min_raise else 5)
                        return do_call()
                    else:  # She raised!
                        # Adjusted: We now call small bets with 4 and 5
                        if my_card <= 3: return do_call()
                        if my_card <= 5 and to_call <= 5: return do_call()
                        return do_fold()

                elif round_name == "post_reveal":
                    if my_card == comm_card: return do_fold()  # Pairs are trash in low ball
                    if to_call == 0:  # She checked, try to steal
                        if my_card <= 8: return do_raise(min_raise if min_raise else 10)
                        return do_check()
                    else:  # She bet
                        if my_card <= 3: return do_call()
                        if my_card <= 5 and to_call <= 15: return do_call()
                        return do_fold()
            else:
                # Generic low ball logic (Fallback)
                if round_name == "pre_reveal":
                    if my_card <= 4: return do_raise(min_raise + 3 if min_raise else 10)
                    if my_card <= 6 and to_call <= 5: return do_call()
                    return do_fold()
                elif round_name == "post_reveal":
                    if my_card == comm_card: return do_fold()
                    if my_card <= 2: return do_raise(max_raise)
                    if my_card <= 4 and to_call <= 20: return do_call()
                    return do_fold()

        # ==========================================
        # RULE 2: WILD SEVEN (7 is a pair) - vs Remy
        # ==========================================
        elif rule == 'wild_seven':
            if round_name == "pre_reveal":
                if my_card >= 11 or my_card == 7:
                    if to_call <= 15: return do_raise(min_raise + 5 if min_raise else 10)
                    return do_call()
                if my_card >= 8 and to_call <= 5: return do_call()
                return do_fold()

            elif round_name == "post_reveal":
                if my_card == comm_card or my_card == 7: return do_raise(max_raise)
                if my_card >= 11:
                    if to_call <= 20: return do_call()
                    if to_call == 0: return do_raise(min_raise if min_raise else 10)
                if to_call == 0: return do_check()
                return do_fold()

        # ==========================================
        # RULE 3 & 4: STANDARD & PAIR BOUNTY
        # ==========================================
        else:
            if opponent == "Nadia":
                # Nadia plays Standard. Steal her blinds!
                if round_name == "pre_reveal":
                    if to_call <= 2:
                        if my_card >= 6: return do_raise(min_raise if min_raise else 5)
                        return do_call()
                    else:
                        if my_card >= 11: return do_call()
                        return do_fold()

                elif round_name == "post_reveal":
                    if my_card == comm_card: return do_raise(max_raise)
                    if to_call == 0:
                        if my_card >= 7: return do_raise(min_raise if min_raise else 10)  # Bluff
                        return do_check()
                    else:
                        if my_card >= 12: return do_call()
                        return do_fold()

            else:
                # Remy plays Pair Bounty. He's aggressive. Trap him.
                if round_name == "pre_reveal":
                    if my_card >= 11:
                        if to_call <= 10: return do_raise(min_raise + 5 if min_raise else 15)
                        return do_call()
                    if my_card >= 9 and to_call <= 5: return do_call()
                    return do_fold()

                elif round_name == "post_reveal":
                    if my_card == comm_card: return do_raise(max_raise)
                    if my_card >= 11:
                        # Call his bluffs! Don't raise and scare him off.
                        if to_call <= 40: return do_call()
                        if my_card == 13: return do_call()
                        return do_fold()
                    if to_call == 0: return do_check()
                    return do_fold()

        return do_fold()

    # Get the decision
    final_action = decide_action()

    return final_action


# Allow running this file directly for local testing
if __name__ == '__main__':
    app = Flask(__name__)
    app.register_blueprint(showdown_bp)
    app.run(port=5000)