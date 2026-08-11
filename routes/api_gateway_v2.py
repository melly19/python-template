from flask import Flask, request, jsonify, Blueprint
import base64
import json
import math

api_gateway_bp_v2 = Blueprint('api_gateway_v2', __name__)

def percentile(sorted_values, pct):
    """Nearest-rank percentile. `sorted_values` must already be sorted ascending."""
    n = len(sorted_values)
    if n == 0:
        return None
    idx = math.ceil((pct / 100) * n) - 1
    idx = max(0, min(idx, n - 1))
    return sorted_values[idx]

@api_gateway_bp_v2.route('/solve', methods=['POST'])
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

        slo_query = decoded_json.get('sloQuery', {})
        heartbeats = decoded_json.get('heartbeats', {})

        service = slo_query.get("service")
        since = slo_query.get("since")

        # Keep only well-formed rows for requested service
        candidates = [
            hb
            for hb in heartbeats
            if isinstance(hb, dict)
            and hb.get("service") == service
            and isinstance(hb.get("timestamp"), (int, float))
            and (since is None or hb["timestamp"] >= since)
        ]
 
        # Handle out-of-order input by sorting chronologically
        candidates.sort(key=lambda hb: hb["timestamp"])

        # Ignore duplicate heartbeats
        seen = set()
        filtered = []
        for hb in candidates:
            key = (hb["service"], hb["timestamp"])
            if key in seen:
                continue
            seen.add(key)
            filtered.append(hb)
    
        if not filtered:
            return jsonify({"availability": 0.0, "p95LatencyMs": 0}), 200
    
        ok_count = sum(1 for hb in filtered if hb.get("status") == "OK")
        availability = ok_count / len(filtered)
    
        latencies = sorted(
            hb["latencyMs"] for hb in filtered if isinstance(hb.get("latencyMs"), (int, float))
        )
        p95_latency = percentile(latencies, 95) if latencies else 0

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

        slo_output = {
            "availability": availability,
            "p95LatencyMs": p95_latency
        }

        # 6. Return transformed payload
        return jsonify({
            "adaptOutput": adapt_output,
            "sloOutput": slo_output
        }), 200

    except Exception:
        return jsonify({"error": "Invalid payload structure"}), 400