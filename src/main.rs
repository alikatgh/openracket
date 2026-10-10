mod app;
mod theme;
use openracket::{document, files, preferences, runtime};
fn main() -> iced::Result {
    app::run()
}
