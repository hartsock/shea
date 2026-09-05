"""The log is a chain of crate-minted nodes: links are real, ids are proofs,
and a Python-side value hashes to the same id Rust gives the same node."""

from __future__ import annotations

import pytest
import content_addressable as ca

from shea._native import cas
from shea.merkle_log import MerkleLog


def test_rust_genesis_node_equals_python_minted_value():
    # Same node, two languages: Rust MerkleNode vs a Python dict of the same
    # shape (no links needed for genesis). Equal ids mean no bespoke encoding.
    rust_id, _ = cas.merkle_node(ca.to_canonical_dagcbor("hello"), [])
    assert ca.ContentId.parse(rust_id) == ca.content_id(
        {"payload": "hello", "parents": []}
    )


def test_append_links_to_previous_head_and_replays_from_disk(tmp_path):
    log = MerkleLog(tmp_path)
    first = log.append({"round": 1})
    second = log.append({"round": 2})
    assert log.head == second
    assert log.node(second)["parents"] == [first]
    assert [p for _, p in MerkleLog(tmp_path)] == [{"round": 2}, {"round": 1}]


def test_tampered_bytes_fail_verification(tmp_path):
    log = MerkleLog(tmp_path)
    cid = log.append({"round": 1})
    log.append({"round": 2})
    blob = tmp_path / str(cid)
    blob.write_bytes(blob.read_bytes()[:-1] + b"\x00")
    with pytest.raises(ValueError, match="does not match"):
        log.verify()
