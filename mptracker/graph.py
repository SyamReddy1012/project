"""Graph-based last-seen network.

Nodes  = locations where a person may be sighted (cameras, landmarks).
Edges  = connections between locations. Two sources:
         * geographic adjacency (``connect_nearby`` / ``add_edge``)
         * observed movement (``record_movement``) which increments ``traversals``
Pure Python (no networkx) so it is easy to test and deploy.
"""
from __future__ import annotations

import heapq
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .models import Location, Person


@dataclass
class Edge:
    distance_km: float
    traversals: int = 0


class SightingGraph:
    def __init__(self) -> None:
        self._nodes: Dict[int, Location] = {}
        self._adj: Dict[int, Dict[int, Edge]] = defaultdict(dict)

    # ---- construction ---------------------------------------------------
    def add_location(self, loc: Location) -> None:
        self._nodes[loc.id] = loc
        self._adj.setdefault(loc.id, {})

    def location(self, loc_id: int) -> Location:
        return self._nodes[loc_id]

    @property
    def locations(self) -> List[Location]:
        return list(self._nodes.values())

    def __len__(self) -> int:
        return len(self._nodes)

    def add_edge(self, a: int, b: int, distance_km: Optional[float] = None) -> None:
        """Undirected geographic link. Keeps existing traversal counts."""
        if a == b:
            return
        d = distance_km if distance_km is not None else self._nodes[a].distance_km(self._nodes[b])
        for u, v in ((a, b), (b, a)):
            if v in self._adj[u]:
                self._adj[u][v].distance_km = d
            else:
                self._adj[u][v] = Edge(d)

    def connect_nearby(self, max_km: float) -> None:
        """Link every pair of locations closer than ``max_km``."""
        locs = self.locations
        for i, a in enumerate(locs):
            for b in locs[i + 1:]:
                d = a.distance_km(b)
                if d <= max_km:
                    self.add_edge(a.id, b.id, d)

    def record_movement(self, src: int, dst: int) -> None:
        """A person was seen at src, then later at dst (directed observation)."""
        if src == dst:
            return
        if dst not in self._adj[src]:
            self.add_edge(src, dst)
        self._adj[src][dst].traversals += 1

    def ingest_person(self, person: Person) -> None:
        """Turn a person's ordered sightings into movement edges."""
        for prev, cur in zip(person.sightings, person.sightings[1:]):
            self.record_movement(prev.location.id, cur.location.id)

    def neighbors(self, node: int) -> Dict[int, Edge]:
        return self._adj[node]

    # ---- algorithms -----------------------------------------------------
    def shortest_distances(self, source: int, max_km: float = math.inf) -> Dict[int, float]:
        """Dijkstra over the network, truncated at ``max_km``."""
        dist = {source: 0.0}
        heap = [(0.0, source)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist.get(u, math.inf):
                continue
            for v, edge in self._adj[u].items():
                nd = d + edge.distance_km
                if nd <= max_km and nd < dist.get(v, math.inf):
                    dist[v] = nd
                    heapq.heappush(heap, (nd, v))
        return dist

    def shortest_path(self, source: int, target: int) -> Tuple[List[int], float]:
        """Dijkstra shortest path and distance between source and target."""
        if source == target:
            return [source], 0.0
        dist = {source: 0.0}
        prev: Dict[int, int] = {}
        heap = [(0.0, source)]
        while heap:
            d, u = heapq.heappop(heap)
            if u == target:
                break
            if d > dist.get(u, math.inf):
                continue
            for v, edge in self._adj[u].items():
                nd = d + edge.distance_km
                if nd < dist.get(v, math.inf):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(heap, (nd, v))
        if target not in dist:
            return [], math.inf
        path = []
        curr = target
        while curr in prev:
            path.append(curr)
            curr = prev[curr]
        path.append(source)
        path.reverse()
        return path, dist[target]

    def transition_probs(self, node: int, allowed: Optional[Set[int]] = None) -> Dict[int, float]:
        """P(next location | current). Favours near nodes and frequently travelled edges."""
        weights = {}
        for v, e in self._adj[node].items():
            if allowed is not None and v not in allowed:
                continue
            weights[v] = (1.0 + e.traversals) / (0.5 + e.distance_km)
        total = sum(weights.values())
        return {v: w / total for v, w in weights.items()} if total else {}

    def spread(self, source: int, allowed: Set[int], steps: int = 4,
               stay: float = 0.25, decay: float = 0.8) -> Dict[int, float]:
        """Random-walk likelihood of the person being at each node (sums to 1)."""
        mass: Dict[int, float] = {source: 1.0}
        score: Dict[int, float] = defaultdict(float)
        for k in range(1, steps + 1):
            nxt: Dict[int, float] = defaultdict(float)
            for u, p in mass.items():
                probs = self.transition_probs(u, allowed)
                if not probs:
                    nxt[u] += p
                    continue
                nxt[u] += p * stay
                for v, t in probs.items():
                    nxt[v] += p * (1 - stay) * t
            mass = nxt
            for v, p in mass.items():
                score[v] += (decay ** k) * p
        total = sum(score.values())
        return {v: s / total for v, s in score.items()} if total else {source: 1.0}
