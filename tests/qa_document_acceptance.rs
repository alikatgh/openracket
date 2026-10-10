//! Independent model-level acceptance tests; not OS keyboard or dialog tests.
use iced::widget::text_editor::{Action, Cursor, Edit, Motion, Position};
use openracket::{
    document::{Document, decode_file},
    files,
};
use std::{fs, sync::Arc};

fn move_to(d: &mut Document, cursor: Cursor) {
    d.edit(Action::Move(Motion::Right));
    d.content.move_to(cursor);
}

#[test]
fn qa_unicode_selection_edit_undo_redo_property() {
    let mut d = Document::new(
        1,
        "#lang racket\r\n(define λ \"你好 🌱 e\u{301}\")\r\n;; end",
        None,
    );
    let mut seed = 0x1234_5678u64;
    let mut next = || {
        seed ^= seed << 13;
        seed ^= seed >> 7;
        seed ^= seed << 17;
        seed
    };
    for step in 0..800 {
        let line = next() as usize % d.content.line_count();
        let text = d.content.line(line).unwrap().text.to_string();
        let boundaries: Vec<usize> = text
            .char_indices()
            .map(|(i, _)| i)
            .chain(std::iter::once(text.len()))
            .collect();
        let column = boundaries[next() as usize % boundaries.len()];
        let position = Position { line, column };
        let selection = if next() % 4 == 0 {
            let other_line = next() as usize % d.content.line_count();
            Some(Position {
                line: other_line,
                column: 0,
            })
        } else {
            None
        };
        move_to(
            &mut d,
            Cursor {
                position,
                selection,
            },
        );
        let before = d.text();
        let before_cursor = d.content.cursor();
        let revision = d.revision;
        let edit = match next() % 9 {
            0 => Edit::Backspace,
            1 => Edit::Delete,
            2 => Edit::Enter,
            3 => Edit::Paste(Arc::new("λ\n你好🌱\n".into())),
            4 => Edit::Insert('\u{301}'),
            5 => Edit::Insert('🌱'),
            6 => Edit::Indent,
            7 => Edit::Unindent,
            _ => Edit::Insert('x'),
        };
        let edit_description = format!("{edit:?}");
        let edit_result =
            std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| d.edit(Action::Edit(edit))));
        assert!(
            edit_result.is_ok(),
            "edit panic at step {step}; edit={edit_description}; cursor={before_cursor:?}; buffer={before:?}"
        );
        let after = d.text();
        let after_cursor = d.content.cursor();
        if after != before {
            d.undo();
            assert_eq!(d.text(), before, "undo bytes at step {step}");
            assert_eq!(d.revision, revision, "undo revision at step {step}");
            assert_eq!(
                d.content.cursor(),
                before_cursor,
                "undo cursor at step {step}"
            );
            d.redo();
            assert_eq!(d.text(), after, "redo bytes at step {step}");
            assert_eq!(
                d.content.cursor(),
                after_cursor,
                "redo cursor at step {step}"
            );
        }
    }
}

#[test]
fn qa_async_save_snapshot_cannot_clear_newer_dirty_edits() {
    let mut d = Document::new(1, "old", None);
    d.edit(Action::Move(Motion::DocumentEnd));
    d.edit(Action::Edit(Edit::Insert('1')));
    let saved_revision = d.revision;
    let saved_text = Arc::new(d.text());
    d.edit(Action::Move(Motion::DocumentEnd));
    d.edit(Action::Edit(Edit::Insert('2')));
    d.mark_saved(saved_revision, saved_text, "test.rkt".into());
    assert!(d.dirty());
    assert_eq!(d.text(), "old12");
    d.undo();
    assert_eq!(d.text(), "old1");
    assert!(!d.dirty());
}

#[test]
fn qa_undo_is_independent_between_documents() {
    let mut a = Document::new(1, "A", None);
    let mut b = Document::new(2, "B", None);
    a.edit(Action::Edit(Edit::Insert('λ')));
    b.edit(Action::Edit(Edit::Insert('🌱')));
    let b_before = b.text();
    a.undo();
    assert_eq!(a.text(), "A");
    assert_eq!(b.text(), b_before);
    b.undo();
    assert_eq!(b.text(), "B");
}

#[test]
fn qa_character_error_column_selects_unicode_scalar() {
    let mut d = Document::new(1, "(λ 你好 🌱 e\u{301})", None);
    d.goto(0, 6, 1);
    assert_eq!(d.content.selection().as_deref(), Some("🌱"));
    d.goto(0, 0, usize::MAX);
    assert_eq!(
        d.content.selection().as_deref(),
        Some("(λ 你好 🌱 e\u{301})")
    );
}

#[test]
fn qa_racket_position_handles_tabs_crlf_unicode_and_multiline_span() {
    // Verified with Racket 9.3 port-next-location: CRLF advances source position
    // by one, tabs by one (although display columns expand), Unicode by scalar.
    let mut d = Document::new(1, "a\r\n\tλ你好🌱 x\r\nnext", None);
    d.goto_offset(9, 1);
    assert_eq!(d.content.selection().as_deref(), Some("x"));
    d.goto_offset(7, 8);
    // Iced intentionally normalizes selected clipboard text to LF; the backing
    // document must still keep original CRLF bytes.
    assert_eq!(d.content.selection().as_deref(), Some("🌱 x\nnext"));
    assert_eq!(d.text(), "a\r\n\tλ你好🌱 x\r\nnext");
}

#[test]
fn qa_text_mentioning_wxme_is_still_plain_text() {
    let text = "#lang racket\n(displayln \"WXME is a format\")\n";
    assert_eq!(decode_file(text.as_bytes().to_vec()).unwrap(), text);
}

#[test]
fn qa_file_round_trip_and_failed_save_preserve_bytes() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("λ space.rkt");
    let original = Arc::new("#lang racket\r\n\"你好🌱\"\r\n".to_owned());
    files::save(path.clone(), original.clone(), None, false).unwrap();
    assert_eq!(
        files::load(path.clone()).unwrap().text.as_str(),
        original.as_str()
    );
    let updated = Arc::new("unsaved change".to_owned());
    assert!(
        files::save(
            dir.path().join("missing/sub.rkt"),
            updated.clone(),
            None,
            false
        )
        .is_err()
    );
    assert_eq!(updated.as_str(), "unsaved change");
    assert_eq!(fs::read(&path).unwrap(), original.as_bytes());
    fs::write(&path, "changed elsewhere").unwrap();
    assert!(files::save(path.clone(), updated, Some(original), false).is_err());
    assert_eq!(fs::read_to_string(&path).unwrap(), "changed elsewhere");
    assert_eq!(
        fs::read_dir(dir.path()).unwrap().count(),
        1,
        "no failed-save temp files remain"
    );
}

#[cfg(unix)]
#[test]
fn qa_symlink_open_uses_canonical_identity() {
    let dir = tempfile::tempdir().unwrap();
    let file = dir.path().join("original.rkt");
    let alias = dir.path().join("alias.rkt");
    fs::write(&file, "#lang racket\n42\n").unwrap();
    std::os::unix::fs::symlink(&file, &alias).unwrap();
    assert_eq!(
        files::load(file).unwrap().path,
        files::load(alias).unwrap().path
    );
}
