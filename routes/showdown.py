from flask import Flask, request, jsonify, Blueprint

app = Flask(__name__)
showdown_bp = Blueprint('showdown', __name__)

# Warm-up endpoint required by the coordinator
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/move', methods=['POST'])
def move():
    # 1. Use 'or {}' to prevent crashes if the server sends empty data
    state = request.json or {}

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

    # ==========================================
    # RULE 1: LOW BALL (Everything is inverted)
    # ==========================================
    if rule == 'low_ball':
        if round_name == "pre_reveal":
            if my_card <= 3:
                if to_call <= 10: return do_raise(min_raise + 3 if min_raise else 10)
                return do_call()
            elif my_card <= 6:
                if to_call <= 5: return do_call()
                return do_fold()
            else:
                if to_call == 0: return do_check()
                return do_fold()

        elif round_name == "post_reveal":
            has_pair = (my_card == comm_card)
            if has_pair:
                if to_call == 0: return do_check()
                return do_fold()

            if my_card <= 3:
                if my_card == 1:
                    if to_call == 0: return do_raise(min_raise)
                    return do_raise(max_raise)
                if to_call <= 20: return do_call()
                return do_fold()
            else:
                if to_call == 0: return do_check()
                return do_fold()

    # ==========================================
    # RULE 2: WILD SEVEN (7 is always a pair)
    # ==========================================
    elif rule == 'wild_seven':
        if round_name == "pre_reveal":
            if my_card >= 11 or my_card == 7:
                if to_call <= 10: return do_raise(min_raise + 3 if min_raise else 10)
                return do_call()
            elif my_card >= 8:
                if to_call <= 5: return do_call()
                return do_fold()
            else:
                if to_call == 0: return do_check()
                return do_fold()

        elif round_name == "post_reveal":
            has_pair = (my_card == comm_card) or (my_card == 7)
            if has_pair:
                return do_raise(max_raise)
            elif my_card >= 11:
                if my_card == 13:
                    if to_call == 0: return do_raise(min_raise)
                    return do_call()
                else:
                    if to_call <= 20: return do_call()
                    return do_fold()
            else:
                if to_call == 0: return do_check()
                return do_fold()

    # ==========================================
    # RULE 3 & 4: STANDARD & PAIR BOUNTY
    # ==========================================
    else:
        if round_name == "pre_reveal":
            if my_card >= 11:
                if to_call <= 10: return do_raise(min_raise + 3 if min_raise else 10)
                return do_call()
            elif my_card >= 8:
                if to_call <= 5: return do_call()
                return do_fold()
            else:
                if to_call == 0: return do_check()
                return do_fold()

        elif round_name == "post_reveal":
            has_pair = (my_card == comm_card)
            if has_pair:
                return do_raise(max_raise)
            elif my_card >= 11:
                if my_card == 13:
                    if to_call == 0: return do_raise(min_raise)
                    return do_call()
                else:
                    if to_call <= 20: return do_call()
                    return do_fold()
            else:
                if to_call == 0: return do_check()
                return do_fold()

    return do_fold()


if __name__ == '__main__':
    # Run the server on port 5000
    app.run(port=5000)