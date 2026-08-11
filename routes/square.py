import json
import logging

from flask import request, Blueprint

from routes import app

logger = logging.getLogger(__name__)
square_bp = Blueprint('square_bp', __name__)

@square_bp.route('/square', methods=['POST'])
def evaluate():
    data = request.get_json()
    logging.info("data sent for evaluation {}".format(data))
    input_value = data.get("input")
    result = input_value * input_value
    logging.info("My result :{}".format(result))
    return json.dumps(result)
