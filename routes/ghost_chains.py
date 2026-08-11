from flask import Blueprint, request, jsonify
from dateutil.parser import isoparse
import threading
import time

ghost_chains_bp = Blueprint('ghost_chains', __name__, url_prefix='/ghost-chains')

state_lock = threading.Lock()

# Tunable identity-signal weights. Values are a design choice -- the spec
# and examples establish the *shape* of the behaviour, not exact numbers.
DIVERGENCE_SIGNAL = 0.35        # identity changes within an otherwise-connected flow
CROSS_COMPONENT_SIGNAL = 0.35   # same identity value reused across disconnected components


class GraphState:
    def __init__(self):
        self.processed_txs = {}
        self.graph = {}
        self.reverse_graph = {}
        self.time_window = []  # (timestamp_float, tx_id, u, v, ip, device)

        # identity_value -> set of (node_id, tx_id), for cross-component lookups
        self.ip_index = {}
        self.device_index = {}

        # tx_id -> (ip, device), for active (non-pruned) transactions only.
        # Lets us recover identity fields while walking the graph by node.
        self.tx_identity = {}

    def clear(self):
        self.processed_txs.clear()
        self.graph.clear()
        self.reverse_graph.clear()
        self.time_window.clear()
        self.ip_index.clear()
        self.device_index.clear()
        self.tx_identity.clear()

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

    def add_identity(self, index, value, node_id, tx_id):
        if value is None:
            return
        if value not in index:
            index[value] = set()
        index[value].add((node_id, tx_id))

    def remove_identity(self, index, value, tx_id):
        if value is None or value not in index:
            return
        index[value] = {(n, t) for (n, t) in index[value] if t != tx_id}
        if not index[value]:
            del index[value]


state = GraphState()


def get_undirected_neighbors(node):
    out = {n for n, _ in state.graph.get(node, set())}
    inn = {n for n, _ in state.reverse_graph.get(node, set())}
    return out | inn


def bfs_component(start):
    """Full weakly-connected component reachable from start, using only
    edges currently in the (post-pruning) graph."""
    visited = {start}
    stack = [start]
    while stack:
        curr = stack.pop()
        for nb in get_undirected_neighbors(curr):
            if nb not in visited:
                visited.add(nb)
                stack.append(nb)
    return visited


def local_component_nodes(u, v):
    """Union of u's and v's pre-insertion components. If this edge is about
    to bridge two previously-disjoint components, both sides count as
    'local' for divergence purposes -- the new edge is the transition point
    Examples 2/3 describe."""
    comp_u = bfs_component(u) if (u in state.graph or u in state.reverse_graph) else {u}
    comp_v = bfs_component(v) if (v in state.graph or v in state.reverse_graph) else {v}
    return comp_u | comp_v


def established_values(local_nodes, dim_index):
    """Identity values already seen on edges strictly within local_nodes,
    for one dimension (0=ip, 1=device)."""
    values = set()
    for node in local_nodes:
        for (nbr, tx_id) in state.graph.get(node, set()):
            ident = state.tx_identity.get(tx_id)
            if ident is None:
                continue
            val = ident[dim_index]
            if val is not None:
                values.add(val)
    return values


def dimension_signal(index, value, dim_index, local_nodes):
    """One identity dimension's contribution: divergence within the local
    component, OR the value recurring in some other, disconnected component."""
    if value is None:
        return 0.0

    signal = 0.0

    prior_local_values = established_values(local_nodes, dim_index)
    if prior_local_values and value not in prior_local_values:
        # A previously-connected flow is now showing a different identity --
        # weakens confidence that one actor explains the whole path.
        signal = max(signal, DIVERGENCE_SIGNAL)

    other_component_hits = {
        n for (n, _tx) in index.get(value, set()) if n not in local_nodes
    }
    if other_component_hits:
        # Same identity value reused where there's no structural link at all.
        signal = max(signal, CROSS_COMPONENT_SIGNAL)

    return signal


def compute_identity_signal(u, v, ip_address, device_id):
    local_nodes = local_component_nodes(u, v)
    ip_signal = dimension_signal(state.ip_index, ip_address, 0, local_nodes)
    device_signal = dimension_signal(state.device_index, device_id, 1, local_nodes)
    # independent dimensions -> probabilistic OR
    return 1.0 - (1.0 - ip_signal) * (1.0 - device_signal)


def compute_risk_score(u, v):
    is_u_known = u in state.graph or u in state.reverse_graph
    is_v_known = v in state.graph or v in state.reverse_graph

    cycles_found = count_independent_paths(v, u, max_depth=5)
    if cycles_found > 0:
        return 0.95 if cycles_found > 1 else 0.85

    if is_u_known and is_v_known:
        incoming_edges = state.reverse_graph.get(v, set())
        unique_sources = {src for src, _ in incoming_edges if src != u}
        if len(unique_sources) > 0:
            return 0.60  # Convergence

    if is_u_known or is_v_known:
        return 0.30  # Extension

    return 0.0  # Isolated


def compute_combined_risk_score(u, v, ip_address, device_id):
    structural_score = compute_risk_score(u, v)
    identity_signal = compute_identity_signal(u, v, ip_address, device_id)
    if identity_signal <= 0.0:
        return structural_score
    # Identity modifies structural suspicion; it never stands alone.
    return 1.0 - (1.0 - structural_score) * (1.0 - identity_signal)


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
    cutoff_time = current_time_ts - 86400.0
    while state.time_window and state.time_window[0][0] < cutoff_time:
        ts, tx_id, u, v, ip, device = state.time_window.pop(0)
        state.remove_edge(u, v, tx_id)
        state.remove_identity(state.ip_index, ip, tx_id)
        state.remove_identity(state.device_index, device, tx_id)
        state.tx_identity.pop(tx_id, None)


@ghost_chains_bp.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


@ghost_chains_bp.route('/reset', methods=['POST'])
def reset():
    req = request.get_json(force=True, silent=True) or {}
    if req.get("clearTransactions"):
        with state_lock:
            state.clear()
        return jsonify({"clearTransactions": True})
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
            ip_address = tx.get("ipAddress")
            device_id = tx.get("deviceId")

            try:
                dt = isoparse(tx.get("createdAt"))
                tx_time_ts = dt.timestamp()
            except Exception:
                tx_time_ts = time.time()

            prune_old_transactions(tx_time_ts)

            risk_score = compute_combined_risk_score(u, v, ip_address, device_id)

            state.add_edge(u, v, tx_id)
            state.tx_identity[tx_id] = (ip_address, device_id)
            state.add_identity(state.ip_index, ip_address, u, tx_id)
            state.add_identity(state.ip_index, ip_address, v, tx_id)
            state.add_identity(state.device_index, device_id, u, tx_id)
            state.add_identity(state.device_index, device_id, v, tx_id)
            state.time_window.append((tx_time_ts, tx_id, u, v, ip_address, device_id))

            final_score = round(float(risk_score), 4)
            state.processed_txs[tx_id] = final_score
            results.append({"txId": tx_id, "riskScore": final_score})

    return jsonify({"transactions": results})