# Third-party notices

OpenRacket's original implementation is MIT licensed. No OpenCode or DrRacket source or artwork is copied into the application. A local Racket installation is required and is not redistributed in this source package.

Direct Rust dependencies are pinned/resolved by Cargo.lock. Principal libraries:

- Iced 0.14 and component crates: MIT, https://github.com/iced-rs/iced
- rfd 0.15.4: MIT, https://github.com/PolyMeilex/rfd
- serde and serde_json: MIT OR Apache-2.0, https://github.com/serde-rs
- tempfile: MIT OR Apache-2.0, https://github.com/Stebalien/tempfile
- libc: MIT OR Apache-2.0, https://github.com/rust-lang/libc
- tiny-skia (test captures and Iced software renderer): BSD-3-Clause, https://github.com/linebender/tiny-skia
- Noto Sans and Noto Sans Mono fonts: SIL Open Font License 1.1, see assets/FONTS-LICENSE.txt

Cargo fetches dependency sources and their license files from crates.io; use `cargo metadata --locked` to inspect the exact resolved packages. The resolved inventory is included as DEPENDENCY-LICENSES.md, with upstream texts under licenses/. Iced component crates share the MIT text included under licenses/iced-0.14.0/. Some target-only workspace crates do not bundle a separate license file; the inventory preserves their declared licensing.

Racket is a separate user-installed runtime. Its official distribution includes its own license terms: https://docs.racket-lang.org/license/index.html . OpenRacket's bridge is original MIT-licensed source.
