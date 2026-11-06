//! Reusable document, file, preferences, and Racket process APIs.
//!
//! The desktop UI and theme belong to the binary crate. `cargo test --lib`
//! covers the modules below; integration tests and binary UI tests are separate.
//! Tests requiring a real Racket installation are ignored by default.

pub mod document;
pub mod files;
pub mod preferences;
pub mod runtime;
