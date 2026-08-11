from flask import Flask, request, jsonify, Blueprint
import base64
import json

from routes import app

api_gateway_bp = Blueprint('api_gateway', __name__)
@api_gateway_bp.route('/solve', methods=['POST'])
def solve():
    try:
        # 1. Parse JSON body
        data = request.get_json()
        if not data or 'payload' not in data:
            return jsonify({"error": "Missing payload field"}), 400

        # 2. Decode the base64 payload string
        b64_payload = data['payload']
        decoded_bytes = base64.b64decode(b64_payload)
        decoded_json = json.loads(decoded_bytes.decode('utf-8'))

        # 3. Extract the nested dictionaries safely
        adapt_input = decoded_json.get('adaptInput', {})
        user = adapt_input.get('user', {})
        metadata = adapt_input.get('metadata', {})

        # 4. Map priority to integers, defaulting to 2
        priority_map = {
            "LOW": 1,
            "MEDIUM": 2,
            "HIGH": 3
        }
        raw_priority = metadata.get('priority')
        priority = priority_map.get(raw_priority, 2)

        # 5. Build the output
        adapt_output = {
            "id": user.get('id', ''),
            "name": user.get('fullName', ''),
            "action": adapt_input.get('action', '').lower(),
            "priority": priority
        }

        # 6. Return transformed payload
        return jsonify({"adaptOutput": adapt_output}), 200

    except Exception as e:
        return jsonify({"error": "Invalid payload structure"}), 400