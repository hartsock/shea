//! newtui reached from Python.
//!
//! Today this is one smoke: newtui's exhaustive `Explorer` walks a component
//! and reports, in-process, called from Python — the proof that newtui links
//! and runs in this configuration. The bridge that lets a *Python-defined*
//! component be explored is the next issue, not this file.

use newtui::{properties, Component, Explorer, Fingerprint, Flow, Key, Row, View};
use pyo3::prelude::*;

/// newtui's own first-acceptance idiom (its README doctest), verbatim.
struct Volume {
    level: u8,
}

impl Component for Volume {
    fn handle(&mut self, key: Key) -> Flow {
        match key {
            Key::Left => {
                self.level = self.level.saturating_sub(10);
                Flow::Stay
            }
            Key::Right => {
                self.level = (self.level + 10).min(100);
                Flow::Stay
            }
            Key::Enter => Flow::Close(true),
            Key::Esc => Flow::Close(false),
            _ => Flow::Stay,
        }
    }

    fn view(&self) -> View {
        View::titled("volume").row(
            Row::new("level", self.level.to_string())
                .adjustable()
                .selected(),
        )
    }

    fn fingerprint(&self) -> Fingerprint {
        Fingerprint::of_view(&self.view())
    }
}

/// Explore the `Volume` component under newtui's navigation alphabet.
/// Returns `(is_clean, report_text)`.
#[pyfunction]
fn smoke() -> (bool, String) {
    let report = Explorer::new(Key::navigation()).explore(
        || Volume { level: 50 },
        &[
            &properties::selection_is_always_in_range(),
            &properties::escape_always_closes_without_applying(),
            &properties::only_adjustable_rows_move(),
        ],
    );
    (report.is_clean(), report.to_string())
}

pub(crate) fn register(py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new(py, "ui")?;
    m.add_function(wrap_pyfunction!(smoke, &m)?)?;
    parent.add_submodule(&m)
}
