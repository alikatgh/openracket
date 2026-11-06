//! Desktop entry point: reuse the library's models and launch the Iced workbench.

mod app;
mod theme;
use openracket::{document, files, preferences, runtime};
fn main() -> iced::Result {
    app::run()
}
