from flask import Flask, request, jsonify, Blueprint

# 1. Define the blueprint
showdown_bp = Blueprint('showdown', __name__)


# 2. Attach routes to the blueprint, not the app!
@showdown_bp.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200


@showdown_bp.route('/move', methods=['POST'])
def move():
    # 3. force=True guarantees we parse the payload even if headers are weird
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

            # Explicitly check for both "raise" and "bet"
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
        # ==========================================
        # RULE 1: LOW BALL (Everything is inverted)
        # ==========================================
        if rule == 'low_ball':
            if round_name == "pre_reveal":
                if my_card <= 4:
                    if to_call <= 15: return do_raise(min_raise + 3 if min_raise else 10)
                    return do_call()
                elif my_card <= 7:
                    if to_call <= 10: return do_call()
                    return do_fold()
                else:
                    if to_call == 0: return do_check()
                    return do_fold()

            elif round_name == "post_reveal":
                has_pair = (my_card == comm_card)
                if has_pair:  # Pairs are terrible in low ball
                    if to_call == 0: return do_check()
                    return do_fold()

                if my_card <= 4:
                    if my_card == 1:
                        if to_call == 0: return do_raise(min_raise)
                        return do_raise(max_raise)
                    if to_call <= 25: return do_call()
                    return do_fold()
                else:
                    if to_call == 0: return do_check()
                    return do_fold()

        # ==========================================
        # RULE 2: WILD SEVEN (7 is always a pair)
        # ==========================================
        elif rule == 'wild_seven':
            if round_name == "pre_reveal":
                if my_card >= 10 or my_card == 7:
                    if to_call <= 15: return do_raise(min_raise + 3 if min_raise else 10)
                    return do_call()
                elif my_card >= 7:
                    if to_call <= 10: return do_call()
                    return do_fold()
                else:
                    if to_call == 0: return do_check()
                    return do_fold()

            elif round_name == "post_reveal":
                has_pair = (my_card == comm_card) or (my_card == 7)
                if has_pair:
                    return do_raise(max_raise)
                elif my_card >= 10:
                    if my_card >= 12:
                        if to_call == 0: return do_raise(min_raise)
                        return do_call()
                    else:
                        if to_call <= 25: return do_call()
                        return do_fold()
                else:
                    if to_call == 0: return do_check()
                    return do_fold()

        # ==========================================
        # RULE 3 & 4: STANDARD & PAIR BOUNTY
        # ==========================================
        else:
            if round_name == "pre_reveal":
                if my_card >= 10:
                    if to_call <= 15: return do_raise(min_raise + 5 if min_raise else 15)
                    return do_call()
                elif my_card >= 7:
                    if to_call <= 10: return do_call()
                    return do_fold()
                else:
                    if to_call == 0: return do_check()
                    return do_fold()

            elif round_name == "post_reveal":
                has_pair = (my_card == comm_card)
                if has_pair:
                    return do_raise(max_raise)
                elif my_card >= 10:
                    if my_card >= 12:
                        if to_call <= 10: return do_raise(min_raise)
                        return do_call()
                    else:
                        if to_call <= 25: return do_call()
                        return do_fold()
                else:
                    if to_call == 0: return do_check()
                    return do_fold()

        return do_fold()

    # Get the decision
    final_action = decide_action()

    # Print a log so you can watch what it does in your terminal/Render logs
    print(f"Rule: {rule} | Card: {my_card} | ToCall: {to_call} -> Output: {final_action.get_json()}")

    return final_action


# Allow running this file directly for testing
if __name__ == '__main__':
    app = Flask(__name__)

    # We must register the blueprint if running this file directly
    app.register_blueprint(showdown_bp)

    # Run the server on port 5000
    app.run(port=5000)