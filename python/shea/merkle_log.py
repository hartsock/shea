"""An append-only Merkle log on disk: every entry is a content-addressed node.

Each node is the crate's ``MerkleNode`` — a payload plus the id of the entry
before it — minted in Rust (``shea._native.cas.merkle_node``) and stored as its
canonical dag-cbor under its own id. ``HEAD`` names the newest node. Reading
walks parents from ``HEAD``; ``verify`` re-derives every id from its bytes.

Where this is used, "which harness version produced this row" is a proof over
bytes, not a lookup: change any earlier node and every later id changes.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import content_addressable as ca

from shea._native import cas


class MerkleLog:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def head(self) -> ca.ContentId | None:
        p = self.root / "HEAD"
        return ca.ContentId.parse(p.read_text().strip()) if p.exists() else None

    def append(self, payload: Any) -> ca.ContentId:
        """Mint a node over ``payload`` (any dag-cbor-representable value) whose
        single parent is the current head; store it; advance HEAD."""
        parents = [str(self.head)] if self.head else []
        cid_s, node_bytes = cas.merkle_node(ca.to_canonical_dagcbor(payload), parents)
        (self.root / cid_s).write_bytes(node_bytes)
        (self.root / "HEAD").write_text(cid_s)
        return ca.ContentId.parse(cid_s)

    def node(self, cid: ca.ContentId) -> dict:
        """Load and decode one node, verifying its bytes match its id."""
        raw = (self.root / str(cid)).read_bytes()
        if ca.ContentId.from_canonical_bytes(raw) != cid:
            raise ValueError(f"node {cid} does not match its bytes")
        return ca.from_canonical_dagcbor_checked(raw)

    def __iter__(self) -> Iterator[tuple[ca.ContentId, Any]]:
        """Yield ``(id, payload)`` newest first, walking parent links."""
        cid = self.head
        while cid is not None:
            n = self.node(cid)
            yield cid, n["payload"]
            parents = n["parents"]
            cid = parents[0] if parents else None

    def verify(self) -> None:
        """Walk the whole chain; raise on the first node whose bytes lie."""
        for _ in self:
            pass
