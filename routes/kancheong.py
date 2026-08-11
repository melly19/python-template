import json
import heapq
from datetime import datetime, timezone

from flask import Flask, request, jsonify, Blueprint

# 1. Define the blueprint
kancheong_bp = Blueprint('kancheong', __name__)

def _parse_time(s: str) -> float:
    """Parse an ISO-8601 timestamp into epoch seconds (UTC)."""
    s2 = s.replace('Z', '+00:00')
    dt = datetime.fromisoformat(s2)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _format_time(ts: float) -> str:
    """Format epoch seconds back into an ISO-8601 UTC timestamp (Z suffix)."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    iso = dt.isoformat()
    if iso.endswith('+00:00'):
        iso = iso[:-6] + 'Z'
    return iso


def _traverse(base_duration: float, obs_list, t0: float):
    """
    Simulate traversing an edge that requires `base_duration` seconds of
    "work" at normal speed, starting at time t0. `obs_list` is a list of
    (start_ts, end_ts, speed_factor) tuples describing time windows during
    which travel on this *directed* edge is slowed (or blocked, if
    speed_factor == 0).

    Returns the arrival time (epoch seconds), or None if the edge is
    permanently blocked before completion.
    """
    if base_duration <= 0:
        return t0

    remaining = base_duration
    cur = t0

    while remaining > 1e-9:
        # Effective speed factor right now: worst case among any
        # obstruction currently active (start inclusive, end exclusive).
        active = [f for (s, e, f) in obs_list if s <= cur < e]
        factor = min(active) if active else 1.0

        # Next moment in time at which the active-set could change.
        next_events = []
        for (s, e, f) in obs_list:
            if s > cur:
                next_events.append(s)
            if e > cur:
                next_events.append(e)
        next_time = min(next_events) if next_events else None

        if factor == 0:
            # Fully blocked right now; nothing to do but wait for the
            # next change of state (can't reverse mid-edge).
            if next_time is None:
                return None  # blocked forever
            cur = next_time
            continue

        if next_time is None:
            # No more obstruction changes; finish at this constant speed.
            cur += remaining / factor
            remaining = 0.0
            break

        interval = next_time - cur
        doable = interval * factor
        if doable >= remaining - 1e-9:
            cur += remaining / factor
            remaining = 0.0
            break
        else:
            remaining -= doable
            cur = next_time

    return cur

@kancheong_bp.route('/kan-cheong-delivery-driver', methods=['POST'])
def solve() -> str:
    obj = request.get_json(force=True, silent=True)
    if obj is None:
        return jsonify({
            "total_duration_sec": None,
            "arrival_time": None,
            "path": [],
            "error": "Invalid JSON payload",
        }), 400

    try:
        start_coord = tuple(obj['start_coordinate'])
        end_coord = tuple(obj['end_coordinate'])
        start_time = _parse_time(obj['start_time'])
    except (KeyError, TypeError, ValueError):
        return jsonify({
            "total_duration_sec": None,
            "arrival_time": None,
            "path": [],
            "error": "Malformed request payload",
        }), 400

    edges = obj.get('edges', [])
    obstructions = obj.get('obstructions', [])

    # Map (from_coord, to_coord, edge_id) -> list of obstruction windows.
    obs_map = {}
    for ob in obstructions:
        key = (
            tuple(ob['edge']['from']),
            tuple(ob['edge']['to']),
            ob['edge_id'],
        )
        obs_map.setdefault(key, []).append((
            _parse_time(ob['start_time']),
            _parse_time(ob['end_time']),
            ob['speed_factor'],
        ))

    # Build bidirectional adjacency list.
    adj = {}
    for e in edges:
        n1 = tuple(e['node1'])
        n2 = tuple(e['node2'])
        eid = e['edge_id']
        dur = e['base_duration_sec']
        for (a, b) in ((n1, n2), (n2, n1)):
            obs_list = obs_map.get((a, b, eid), [])
            adj.setdefault(a, []).append((eid, b, dur, obs_list))
            adj.setdefault(b, adj.get(b, []))  # ensure node exists

    def unreachable():
        return jsonify({
            "total_duration_sec": None,
            "arrival_time": None,
            "path": [],
        })

    if start_coord == end_coord:
        return jsonify({
            "total_duration_sec": 0,
            "arrival_time": _format_time(start_time),
            "path": [],
        })

    # Dijkstra over arrival times (edge cost depends on departure time,
    # but is monotonic/FIFO since speed factors never exceed 1.0).
    dist = {start_coord: start_time}
    prev_edge = {}  # coord -> (prev_coord, edge_id)
    visited = set()
    heap = [(start_time, start_coord)]

    while heap:
        t, u = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u)
        if u == end_coord:
            break
        for (eid, v, dur, obs_list) in adj.get(u, []):
            arr = _traverse(dur, obs_list, t)
            if arr is None:
                continue
            if arr < dist.get(v, float('inf')) - 1e-9:
                dist[v] = arr
                prev_edge[v] = (u, eid)
                heapq.heappush(heap, (arr, v))

    if end_coord not in dist:
        return unreachable()

    # Reconstruct path.
    path = []
    cur = end_coord
    while cur != start_coord:
        if cur not in prev_edge:
            return unreachable()
        u, eid = prev_edge[cur]
        path.append(eid)
        cur = u
    path.reverse()

    total = dist[end_coord] - start_time
    if abs(total - round(total)) < 1e-6:
        total = int(round(total))
    else:
        total = round(total, 6)

    return jsonify({
        "total_duration_sec": total,
        "arrival_time": _format_time(dist[end_coord]),
        "path": path,
    })


if __name__ == "__main__":
    app = Flask(__name__)
    app.register_blueprint(kancheong_bp)
    app.run(port=5000)