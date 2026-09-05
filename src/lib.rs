//! shea's native extension: newt-agent's PyO3 modules plus a newtui bridge,
//! assembled here instead of taken from the `newt-agent-py` umbrella wheel so
//! shea tracks newt and newtui `main` from source. Composition root only
//! (CRAFT-03): each member registers itself.

use pyo3::prelude::*;

mod ui;

#[pymodule]
fn _native(py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    newt_core::pyo3_module::register(py, m)?;
    newt_data::pyo3_module::register(py, m)?;
    newt_tools::pyo3_module::register(py, m)?;
    newt_inference::pyo3_module::register(py, m)?;
    newt_coder::pyo3_module::register(py, m)?;
    newt_eval::pyo3_module::register(py, m)?;
    newt_acp_worker::pyo3_module::register(py, m)?;
    newt_mcp_server::pyo3_module::register(py, m)?;
    ui::register(py, m)
}
