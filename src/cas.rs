//! Content addressing that Python cannot do alone.
//!
//! The `content-addressable` Python binding mints ids over plain values but
//! refuses a `ContentId` *inside* a value, so a Merkle node with real parent
//! links cannot be assembled in Python. This member mints nodes through the
//! crate's own `MerkleNode` — payload plus deduplicated, ordered parent links,
//! id over both — and hands Python the canonical bytes and the id. Python
//! stores, verifies (`ContentId.from_canonical_bytes`), and decodes
//! (`from_canonical_dagcbor_checked`, which turns links back into ids).

use content_addressable::canonical::from_canonical_dagcbor_checked;
use content_addressable::{ContentAddressable, ContentId, MerkleNode};
use ipld_core::ipld::Ipld;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

/// Mint a Merkle node: `payload_cbor` is the payload's canonical dag-cbor (from
/// the Python binding's `to_canonical_dagcbor`), `parents` are parent ids as
/// strings. Returns `(id, canonical_node_bytes)`.
#[pyfunction]
fn merkle_node(payload_cbor: &[u8], parents: Vec<String>) -> PyResult<(String, Vec<u8>)> {
    let payload: Ipld = from_canonical_dagcbor_checked(payload_cbor)
        .map_err(|e| PyValueError::new_err(format!("payload is not canonical dag-cbor: {e}")))?;
    let parents = parents
        .iter()
        .map(|s| {
            s.parse::<ContentId>()
                .map_err(|e| PyValueError::new_err(format!("bad parent id {s:?}: {e}")))
        })
        .collect::<PyResult<Vec<_>>>()?;
    let node = MerkleNode::new(payload, parents);
    let id = node
        .id()
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    let bytes = node
        .canonical_form()
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok((id.to_string(), bytes))
}

pub(crate) fn register(py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new(py, "cas")?;
    m.add_function(wrap_pyfunction!(merkle_node, &m)?)?;
    parent.add_submodule(&m)
}
