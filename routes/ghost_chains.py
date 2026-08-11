from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from dateutil import parser
import threading

# Create the Blueprint with the required base path
ghost_chains_bp = Blueprint('ghost_chains', __name__, url_prefix='/ghost-chains')

# --- State Management ---
state_lock = threading.Lock()


class GraphState:
    def __init__(self):
        # Maps txId -> riskScore for idempotency
        self.processed_txs = {}

        # Adjacency list: node -> set of (target_node, txId)
        self.graph = {}

        # Reverse adjacency for convergence detection: node -> set of (source_node, txId)
        self.reverse_graph = {}

        # Queue of transactions to maintain the 24h rolling window
        # Stores: (timestamp, txId, u, v)
        self.time_window = []

    def clear(self):
        self.processed_txs.clear()
        self.graph.clear()
        self.reverse_graph.clear()
        self.time_window.clear()

    def add_edge(self, u, v, tx_id):
        if u not in self.graph:
            self.graph[u] = set()
        if v not in self.reverse_graph:
            self.reverse_graph[v] = set()

        self.graph[u].add((v, tx_id))
        self.reverse_graph[v].add((u, tx_id))

    def remove_edge(self, u, v, tx_id):
        if u in self.graph:
            self.graph[u].discard((v, tx_id))
            if not self.graph[u]:
                del self.graph[u]
        if v in self.reverse_graph:
            self.reverse_graph[v].discard((u, tx_id))
            if not self.reverse_graph[v]:
                del self.reverse_graph[v]


state = GraphState()


# --- Graph Analysis & Scoring ---
def compute_risk_score(u, v):
    """
    Evaluates the structural signal added by the edge u -> v.
    """
    is_u_known = u in state.graph or u in state.reverse_graph
    is_v_known = v in state.graph or v in state.reverse_graph

    # 1. Check for Loops (Return / Multi-Loop)
    cycles_found = count_independent_paths(v, u, max_depth=5)
    if cycles_found > 0:
        if cycles_found > 1:
            return 0.95  # Multi-Loop
        return 0.85  # Single Return/Loop

    # 2. Check for Convergence
    if is_u_known and is_v_known:
        existing_incoming = len(state.reverse_graph.get(v, set()))
        if existing_incoming > 0:
            return 0.60  # Convergence

    # 3. Check for Extension
    if is_u_known or is_v_known:
        return 0.30  # Extension

    # 4. Isolated
    return 0.10  # Isolated


def count_independent_paths(start, target, max_depth=5):
    """
    A simple BFS to find paths from start to target.
    Returns the number of unique immediate neighbors of 'start' that can reach 'target'.
    """
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


def prune_old_transactions(current_time):
    """
    Removes transactions older than 24 hours relative to the current transaction.
    """
    cutoff_time = current_time - timedelta(hours=24)

    while state.time_window and state.time_window[0][0] < cutoff_time:
        ts, tx_id, u, v = state.time_window.pop(0)
        state.remove_edge(u, v, tx_id)


# --- API Endpoints ---

@ghost_chains_bp.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


@ghost_chains_bp.route('/reset', methods=['POST'])
def reset():
    req = request.get_json() or {}
    if req.get("clearTransactions"):
        with state_lock:
            state.clear()
        return jsonify({"clearTransactions": True})
    return jsonify({"error": "Invalid request"}), 400


@ghost_chains_bp.route('/transactions', methods=['POST'])
def process_transactions():
    data = request.get_json() or {}
    transactions = data.get("transactions", [])

    results = []

    with state_lock:
        for tx in transactions:
            tx_id = tx.get("txId")

            # Idempotency check
            if tx_id in state.processed_txs:
                results.append({"txId": tx_id, "riskScore": state.processed_txs[tx_id]})
                continue

            u = tx.get("fromUserId")
            v = tx.get("toUserId")

            try:
                tx_time = parser.parse(tx.get("createdAt"))
            except (ValueError, TypeError):
                tx_time = datetime.utcnow()

            # Prune graph before scoring to respect 24h window
            prune_old_transactions(tx_time)

            # Score
            risk_score = compute_risk_score(u, v)

            # Update state
            state.add_edge(u, v, tx_id)
            state.time_window.append((tx_time, tx_id, u, v))

            final_score = round(risk_score, 4)
            state.processed_txs[tx_id] = final_score

            results.append({
                "txId": tx_id,
                "riskScore": final_score
            })

    return jsonify({"transactions": results})