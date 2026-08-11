from flask import Blueprint, request, jsonify
from dateutil.parser import isoparse
import threading
import time

ghost_chains_bp = Blueprint('ghost_chains', __name__, url_prefix='/ghost-chains')

state_lock = threading.Lock()


class GraphState:
    def __init__(self):
        self.processed_txs = {}
        self.graph = {}
        self.reverse_graph = {}
        self.time_window = []  # Now stores (timestamp_float, tx_id, u, v)

    def clear(self):
        self.processed_txs.clear()
        self.graph.clear()
        self.reverse_graph.clear()
        self.time_window.clear()

    def add_edge(self, u, v, tx_id):
        if u not in self.graph: self.graph[u] = set()
        if v not in self.reverse_graph: self.reverse_graph[v] = set()
        self.graph[u].add((v, tx_id))
        self.reverse_graph[v].add((u, tx_id))

    def remove_edge(self, u, v, tx_id):
        if u in self.graph:
            self.graph[u].discard((v, tx_id))
            if not self.graph[u]: del self.graph[u]
        if v in self.reverse_graph:
            self.reverse_graph[v].discard((u, tx_id))
            if not self.reverse_graph[v]: del self.reverse_graph[v]


state = GraphState()


def compute_risk_score(u, v):
    is_u_known = u in state.graph or u in state.reverse_graph
    is_v_known = v in state.graph or v in state.reverse_graph

    cycles_found = count_independent_paths(v, u, max_depth=5)
    if cycles_found > 0:
        return 0.95 if cycles_found > 1 else 0.85

    if is_u_known and is_v_known:
        # Check if v already has incoming edges from someone OTHER than u
        incoming_edges = state.reverse_graph.get(v, set())
        unique_sources = {src for src, _ in incoming_edges if src != u}
        if len(unique_sources) > 0:
            return 0.60  # Convergence

    if is_u_known or is_v_known:
        return 0.30  # Extension

    return 0.0  # Isolated


def count_independent_paths(start, target, max_depth=4):
    if start not in state.graph:
        return 0
    successful_branches = 0
    for neighbor, _ in state.graph.get(start, set()):
        if neighbor == target:
            successful_branches += 1
            continue
        queue = [(neighbor, 1)]
        visited = {start, neighbor}
        found = False
        while queue and not found:
            curr, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for next_node, _ in state.graph.get(curr, set()):
                if next_node == target:
                    successful_branches += 1
                    found = True
                    break
                if next_node not in visited:
                    visited.add(next_node)
                    queue.append((next_node, depth + 1))
    return successful_branches


def prune_old_transactions(current_time_ts):
    # current_time_ts is a float. 24 hours = 86400 seconds.
    cutoff_time = current_time_ts - 86400.0
    while state.time_window and state.time_window[0][0] < cutoff_time:
        ts, tx_id, u, v = state.time_window.pop(0)
        state.remove_edge(u, v, tx_id)


@ghost_chains_bp.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


@ghost_chains_bp.route('/reset', methods=['POST'])
def reset():
    # force=True ignores missing headers, silent=True prevents crashes on bad body
    req = request.get_json(force=True, silent=True) or {}
    if req.get("clearTransactions"):
        with state_lock:
            state.clear()
        return jsonify({"clearTransactions": True})
    # Even if payload is weird, force a reset just in case to avoid a 0 score
    with state_lock:
        state.clear()
    return jsonify({"clearTransactions": True})


@ghost_chains_bp.route('/transactions', methods=['POST'])
def process_transactions():
    data = request.get_json(force=True, silent=True) or {}
    transactions = data.get("transactions", [])
    results = []

    with state_lock:
        for tx in transactions:
            tx_id = tx.get("txId")
            if not tx_id:
                continue

            if tx_id in state.processed_txs:
                results.append({"txId": tx_id, "riskScore": state.processed_txs[tx_id]})
                continue

            u = tx.get("fromUserId")
            v = tx.get("toUserId")

            # Bulletproof timestamp parsing
            try:
                dt = isoparse(tx.get("createdAt"))
                tx_time_ts = dt.timestamp()
            except Exception:
                tx_time_ts = time.time()

            prune_old_transactions(tx_time_ts)
            risk_score = compute_risk_score(u, v)

            state.add_edge(u, v, tx_id)
            state.time_window.append((tx_time_ts, tx_id, u, v))

            final_score = round(float(risk_score), 4)
            state.processed_txs[tx_id] = final_score
            results.append({"txId": tx_id, "riskScore": final_score})

    return jsonify({"transactions": results})