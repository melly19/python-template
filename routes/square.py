import logging

from flask import request, Blueprint, jsonify

logger = logging.getLogger(__name__)
square_bp = Blueprint('square_bp', __name__)

@square_bp.route('/square', methods=['POST'])
def evaluate():
    data = request.get_json(force=True, silent=True) or {}
    logging.info("data sent for evaluation %s", data)

    number = data.get("number")
    if number is None or not isinstance(number, (int, float)):
        return jsonify({"error": "Invalid input; expected a numeric 'number' field."}), 400

    answer = number * number
    logging.info("answer: %s", answer)
    return jsonify({"answer": answer})
