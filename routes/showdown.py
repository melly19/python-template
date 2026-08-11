from flask import Flask, request, jsonify, Blueprint

app = Flask(__name__)
showdown_bp = Blueprint('showdown', __name__)

# Warm-up endpoint required by the coordinator
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200


# The main game loop endpoint
@app.route('/move', methods=['POST'])
def move():
    state = request.json

    legal_actions = state.get('legal_actions', [])
    round_name = state.get('round')
    my_card = state.get('your_number')
    comm_card = state.get('community_number')
    to_call = state.get('to_call', 0)
    min_raise = state.get('min_raise_to')
    max_raise = state.get('max_raise_to')

    # --- HELPER FUNCTIONS ---
    # These ensure we NEVER make an illegal move and handle fallback logic safely.

    def do_raise(amount):
        if "raise" in legal_actions and min_raise is not None and max_raise is not None:
            # Clamp the bet so it never violates min_raise_to or max_raise_to
            valid_amount = max(min_raise, min(amount, max_raise))
            return {"action": "raise", "amount": valid_amount}
        return do_call()  # Fallback if raising isn't allowed

    def do_call():
        if "call" in legal_actions: return {"action": "call"}
        return do_check()

    def do_check():
        if "check" in legal_actions: return {"action": "check"}
        return {"action": "fold"}

    def do_fold():
        if "fold" in legal_actions: return {"action": "fold"}
        return do_check()

    # ==========================================
    # PHASE 1 STRATEGY: TIGHT-AGGRESSIVE (TAG)
    # ==========================================

    if round_name == "pre_reveal":
        # 1. Premium Cards (11, 12, 13): Build the pot
        if my_card >= 11:
            if to_call <= 10:
                # Value raise slightly above minimum to build the pot
                return do_raise(min_raise + 3 if min_raise else 10)
            return do_call()

        # 2. Medium Cards (8, 9, 10): See the reveal cheaply, but fold to heavy raises
        elif my_card >= 8:
            if to_call <= 5:
                return do_call()
            return do_fold()

        # 3. Weak Cards (1-7): Fold to any aggression (save your chips)
        else:
            if to_call == 0:
                return do_check()
            return do_fold()

    elif round_name == "post_reveal":
        has_pair = (my_card == comm_card)

        # 1. THE NUTS (Pair): Go All-In!
        # Any pair beats a non-pair, and no other pair can exist. Unbeatable.
        if has_pair:
            return do_raise(max_raise)

        # 2. High Cards (11, 12, 13)
        elif my_card >= 11:
            # 13 is only beaten if the opponent has a pair (1/13 chance)
            if my_card == 13:
                if to_call == 0:
                    return do_raise(min_raise)  # Value bet if they check to us
                return do_call()  # Never fold a 13; let them bluff
            else:
                # 11 or 12: Play slightly more cautiously against big bets
                if to_call <= 20:
                    return do_call()
                return do_fold()

        # 3. Medium/Weak Cards: Check if free, otherwise Fold.
        else:
            if to_call == 0:
                return do_check()
            return do_fold()

    # Failsafe
    return do_fold()


if __name__ == '__main__':
    # Run the server on port 5000
    app.run(port=5000)