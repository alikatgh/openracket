//! File model and bounded, changed-line undo history. No full-buffer snapshots on typing.
use iced::widget::text_editor::{self, Action, Cursor, Edit, Position};
use std::{
    collections::VecDeque,
    path::{Path, PathBuf},
    sync::Arc,
    time::{Duration, Instant},
};

const HISTORY_BYTES: usize = 8 * 1024 * 1024;
const HISTORY_STEPS: usize = 1000;

#[derive(Debug, Clone)]
struct Change {
    start: usize,
    before: String,
    after: String,
    before_lines: usize,
    after_lines: usize,
    before_cursor: Cursor,
    after_cursor: Cursor,
    before_revision: u64,
    after_revision: u64,
    typed: bool,
    at: Instant,
}

pub struct Document {
    pub id: u64,
    pub path: Option<PathBuf>,
    pub content: text_editor::Content,
    pub revision: u64,
    saved_revision: u64,
    next_revision: u64,
    undo: VecDeque<Change>,
    redo: Vec<Change>,
    history_bytes: usize,
    pub disk_text: Option<Arc<String>>,
}

impl Document {
    pub fn new(id: u64, text: &str, path: Option<PathBuf>) -> Self {
        Self {
            id,
            path,
            content: text_editor::Content::with_text(text),
            revision: 0,
            saved_revision: 0,
            next_revision: 1,
            undo: VecDeque::new(),
            redo: Vec::new(),
            history_bytes: 0,
            disk_text: Some(Arc::new(text.to_owned())),
        }
    }
    pub fn title(&self) -> String {
        self.path
            .as_deref()
            .and_then(Path::file_name)
            .map(|s| s.to_string_lossy().into_owned())
            .unwrap_or_else(|| format!("untitled-{}.rkt", self.id))
    }
    pub fn dirty(&self) -> bool {
        self.revision != self.saved_revision
    }
    pub fn mark_saved(&mut self, revision: u64, text: Arc<String>, path: PathBuf) {
        self.saved_revision = revision;
        self.disk_text = Some(text);
        self.path = Some(path);
        // A saved boundary must never be merged into later typing.
        if let Some(change) = self.undo.back_mut() {
            change.typed = false;
        }
    }
    pub fn text(&self) -> String {
        self.content.text()
    }
    pub fn break_undo_group(&mut self) {
        if let Some(change) = self.undo.back_mut() {
            change.typed = false;
        }
    }
    pub fn edit(&mut self, action: Action) {
        if !action.is_edit() {
            if !matches!(action, Action::Scroll { .. })
                && let Some(change) = self.undo.back_mut()
            {
                change.typed = false;
            }
            self.content.perform(action);
            return;
        }
        let before_cursor = self.content.cursor();
        let other = before_cursor.selection.unwrap_or(before_cursor.position);
        let start = before_cursor
            .position
            .line
            .min(other.line)
            .saturating_sub(1);
        let old_count = self.content.line_count();
        let end = (before_cursor.position.line.max(other.line) + 2).min(old_count);
        let before = line_region(&self.content, start, end);
        let typed = matches!(action, Action::Edit(Edit::Insert(c)) if c != '\n');
        if matches!(action, Action::Edit(Edit::Unindent)) {
            safe_unindent(&mut self.content);
        } else {
            self.content.perform(action);
        }
        let new_count = self.content.line_count();
        let new_end =
            (end as isize + new_count as isize - old_count as isize).max(start as isize) as usize;
        let after = line_region(&self.content, start, new_end);
        if before == after {
            return;
        }
        let change = Change {
            start,
            before,
            after,
            before_lines: end - start,
            after_lines: new_end - start,
            before_cursor,
            after_cursor: self.content.cursor(),
            before_revision: self.revision,
            after_revision: self.next_revision,
            typed,
            at: Instant::now(),
        };
        self.next_revision += 1;
        self.revision = change.after_revision;
        self.redo.clear();
        let merge = self.undo.back().is_some_and(|last| {
            typed
                && last.typed
                && last.start == start
                && last.after == change.before
                && last.after_cursor == before_cursor
                && change.at.duration_since(last.at) < Duration::from_millis(650)
        });
        if merge {
            let last = self.undo.back_mut().unwrap();
            self.history_bytes -= last.after.len();
            last.after = change.after;
            last.after_lines = change.after_lines;
            last.after_cursor = change.after_cursor;
            last.after_revision = change.after_revision;
            last.at = change.at;
            self.history_bytes += last.after.len();
        } else {
            self.history_bytes += change.before.len() + change.after.len();
            self.undo.push_back(change);
        }
        while self.undo.len() > HISTORY_STEPS
            || (self.history_bytes > HISTORY_BYTES && self.undo.len() > 1)
        {
            if let Some(old) = self.undo.pop_front() {
                self.history_bytes -= old.before.len() + old.after.len();
            }
        }
    }
    pub fn undo(&mut self) {
        if let Some(change) = self.undo.pop_back() {
            replace_region(
                &mut self.content,
                change.start,
                change.after_lines,
                &change.before,
            );
            clear_selection_and_move(&mut self.content, change.before_cursor);
            self.revision = change.before_revision;
            self.history_bytes -= change.before.len() + change.after.len();
            self.redo.push(change);
        }
    }
    pub fn redo(&mut self) {
        if let Some(mut change) = self.redo.pop() {
            replace_region(
                &mut self.content,
                change.start,
                change.before_lines,
                &change.after,
            );
            clear_selection_and_move(&mut self.content, change.after_cursor);
            self.revision = change.after_revision;
            change.typed = false;
            self.history_bytes += change.before.len() + change.after.len();
            self.undo.push_back(change);
        }
    }
    pub fn replace_all(&mut self, text: String) {
        self.content.perform(Action::SelectAll);
        self.edit(Action::Edit(Edit::Paste(Arc::new(text))));
    }
    pub fn add_racket_language(&mut self) {
        clear_selection_and_move(
            &mut self.content,
            Cursor {
                position: Position { line: 0, column: 0 },
                selection: None,
            },
        );
        self.edit(Action::Edit(Edit::Paste(Arc::new(
            "#lang racket\n".to_owned(),
        ))));
    }
    pub fn goto(&mut self, line: usize, character_column: usize, span: usize) {
        let line = line.min(self.content.line_count().saturating_sub(1));
        let value = self
            .content
            .line(line)
            .map(|l| l.text.into_owned())
            .unwrap_or_default();
        let column = char_to_byte(&value, character_column);
        let end = char_to_byte(&value, character_column.saturating_add(span));
        clear_selection_and_move(
            &mut self.content,
            Cursor {
                position: Position { line, column: end },
                selection: Some(Position { line, column }),
            },
        );
    }
    /// Select a 1-based Racket character offset and span, including multi-line spans.
    /// Iced positions use UTF-8 byte columns; Racket positions count Unicode characters.
    pub fn goto_offset(&mut self, position: usize, span: usize) {
        let locate = |mut chars: usize| {
            for index in 0..self.content.line_count() {
                if let Some(line) = self.content.line(index) {
                    let count = line.text.chars().count();
                    if chars <= count {
                        return Position {
                            line: index,
                            column: char_to_byte(&line.text, chars),
                        };
                    }
                    chars = chars.saturating_sub(
                        count
                            + if line.ending == text_editor::LineEnding::CrLf {
                                1
                            } else {
                                line.ending.as_str().chars().count()
                            },
                    );
                }
            }
            let line = self.content.line_count().saturating_sub(1);
            Position {
                line,
                column: self.content.line(line).map(|l| l.text.len()).unwrap_or(0),
            }
        };
        let start = locate(position.saturating_sub(1));
        let end = locate(position.saturating_sub(1).saturating_add(span));
        clear_selection_and_move(
            &mut self.content,
            Cursor {
                position: end,
                selection: Some(start),
            },
        );
    }
    /// Case-sensitive literal search with wrap-around. The view uses native editor selection.
    pub fn find(&mut self, needle: &str, backwards: bool) -> Option<(usize, usize)> {
        if needle.is_empty() {
            return None;
        }
        let value = self.content.text();
        let cursor = self.content.cursor();
        let mut offset = 0;
        for i in 0..cursor.position.line {
            if let Some(line) = self.content.line(i) {
                offset += line.text.len() + line.ending.as_str().len();
            }
        }
        offset = (offset + cursor.position.column).min(value.len());
        while !value.is_char_boundary(offset) {
            offset -= 1;
        }
        let found = if backwards {
            let start = cursor
                .selection
                .map(|p| {
                    let mut off = 0;
                    for i in 0..p.line {
                        if let Some(l) = self.content.line(i) {
                            off += l.text.len() + l.ending.as_str().len();
                        }
                    }
                    off + p.column
                })
                .unwrap_or(offset)
                .min(value.len());
            value[..start].rfind(needle).or_else(|| value.rfind(needle))
        } else {
            value[offset..]
                .find(needle)
                .map(|n| n + offset)
                .or_else(|| value.find(needle))
        }?;
        let start = byte_position(&value, found);
        let end = byte_position(&value, found + needle.len());
        clear_selection_and_move(
            &mut self.content,
            Cursor {
                position: end,
                selection: Some(start),
            },
        );
        Some((start.line + 1, value[..found].matches(needle).count() + 1))
    }
    pub fn history_bytes(&self) -> usize {
        self.history_bytes
    }
}

/// Avoid cosmic-text 0.15's unsigned cursor underflow when Shift+Tab is used
/// inside leading whitespace. Match its default 8-column indentation blocks,
/// while clamping both cursor endpoints to valid UTF-8 boundaries.
fn safe_unindent(content: &mut text_editor::Content) {
    let mut cursor = content.cursor();
    let other = cursor.selection.unwrap_or(cursor.position);
    for line in cursor.position.line.min(other.line)..=cursor.position.line.max(other.line) {
        let value = content
            .line(line)
            .map(|l| l.text.into_owned())
            .unwrap_or_default();
        let mut start = 0;
        let mut end = value.len();
        for (count, (index, ch)) in value.char_indices().enumerate() {
            if !ch.is_whitespace() {
                end = index;
                break;
            }
            if count % 8 == 0 {
                start = index;
            }
        }
        if start == end {
            continue;
        }
        clear_selection_and_move(
            content,
            Cursor {
                position: Position { line, column: end },
                selection: Some(Position {
                    line,
                    column: start,
                }),
            },
        );
        content.perform(Action::Edit(Edit::Paste(Arc::new(String::new()))));
        let adjust = |p: &mut Position| {
            if p.line == line && p.column > start {
                p.column = if p.column >= end {
                    p.column - (end - start)
                } else {
                    start
                };
            }
        };
        adjust(&mut cursor.position);
        if let Some(selection) = &mut cursor.selection {
            adjust(selection);
        }
    }
    clear_selection_and_move(content, cursor);
}

fn clear_selection_and_move(content: &mut text_editor::Content, cursor: Cursor) {
    // Iced 0.14 move_to(None) leaves a prior selection behind; a Move clears it first.
    content.perform(Action::Move(text_editor::Motion::Right));
    content.move_to(cursor);
}
fn char_to_byte(value: &str, n: usize) -> usize {
    value
        .char_indices()
        .nth(n)
        .map(|(i, _)| i)
        .unwrap_or(value.len())
}
fn byte_position(value: &str, offset: usize) -> Position {
    let prefix = &value[..offset];
    let line = prefix.bytes().filter(|&c| c == b'\n').count();
    let column = prefix
        .rsplit_once('\n')
        .map(|(_, s)| s.len())
        .unwrap_or(prefix.len());
    Position { line, column }
}
fn line_region(content: &text_editor::Content, start: usize, end: usize) -> String {
    let mut result = String::new();
    for index in start..end {
        if let Some(line) = content.line(index) {
            result.push_str(&line.text);
            if index + 1 < content.line_count() {
                result.push_str(if line.ending.as_str().is_empty() {
                    "\n"
                } else {
                    line.ending.as_str()
                });
            }
        }
    }
    result
}
fn replace_region(content: &mut text_editor::Content, start: usize, count: usize, text: &str) {
    let end_line = start + count;
    let end = if end_line < content.line_count() {
        Position {
            line: end_line,
            column: 0,
        }
    } else {
        let line = content.line_count().saturating_sub(1);
        Position {
            line,
            column: content.line(line).map(|l| l.text.len()).unwrap_or(0),
        }
    };
    clear_selection_and_move(
        content,
        Cursor {
            position: end,
            selection: Some(Position {
                line: start,
                column: 0,
            }),
        },
    );
    content.perform(Action::Edit(Edit::Paste(Arc::new(text.to_owned()))));
}

/// UTF-8 plain-text only: never silently flatten a rich WXME document.
pub fn decode_file(bytes: Vec<u8>) -> Result<String, String> {
    if bytes.starts_with(b"WXME")
        || (bytes.starts_with(b"#reader") && bytes.windows(4).take(200).any(|s| s == b"WXME"))
    {
        return Err("This is a rich WXME document. Open it in DrRacket and save a plain-text copy first; embedded objects are not supported yet.".into());
    }
    if bytes.contains(&0) {
        return Err(
            "This file contains binary data; only UTF-8 plain-text Racket files are supported."
                .into(),
        );
    }
    String::from_utf8(bytes)
        .map_err(|_| "This file is not UTF-8. Convert a copy to UTF-8 before opening it.".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn unicode_undo_redo_restores_exact_buffer() {
        let mut d = Document::new(1, "#lang racket\n(define λ \"你好 🌱\")\n", None);
        d.content
            .perform(Action::Move(text_editor::Motion::DocumentEnd));
        let original = d.text();
        d.edit(Action::Edit(Edit::Paste(Arc::new(
            "(displayln λ)\n".into(),
        ))));
        let changed = d.text();
        assert_ne!(changed, original);
        d.undo();
        assert_eq!(d.text(), original);
        d.redo();
        assert_eq!(d.text(), changed);
    }
    #[test]
    fn selection_replace_and_multiline_undo() {
        let mut d = Document::new(1, "a\nb\nc\nd\n", None);
        let orig = d.text();
        d.content.move_to(Cursor {
            position: Position { line: 3, column: 1 },
            selection: Some(Position { line: 1, column: 0 }),
        });
        d.edit(Action::Edit(Edit::Paste(Arc::new("你好\nX".into()))));
        assert_eq!(d.text(), "a\n你好\nX\n");
        d.undo();
        assert_eq!(d.text(), orig);
        d.redo();
        assert_eq!(d.text(), "a\n你好\nX\n");
    }
    #[test]
    fn saved_revision_and_typing_boundary() {
        let mut d = Document::new(1, "", None);
        d.edit(Action::Edit(Edit::Insert('a')));
        d.mark_saved(d.revision, Arc::new(d.text()), "test.rkt".into());
        assert!(!d.dirty());
        d.edit(Action::Edit(Edit::Insert('b')));
        assert!(d.dirty());
        d.undo();
        assert_eq!(d.text(), "a");
        assert!(!d.dirty());
    }
    #[test]
    fn typing_deltas_do_not_copy_large_buffer() {
        let mut d = Document::new(1, &"(define x 1)\n".repeat(80000), None);
        for c in "hello".chars() {
            d.edit(Action::Edit(Edit::Insert(c)));
        }
        assert!(d.history_bytes() < 1024);
        d.undo();
        assert!(d.text().starts_with("(define"));
    }
    #[test]
    fn crlf_is_preserved() {
        let mut d = Document::new(1, "a\r\nb\r\n", None);
        d.edit(Action::Edit(Edit::Insert('λ')));
        d.undo();
        assert_eq!(d.text(), "a\r\nb\r\n");
    }
    #[test]
    fn missing_language_is_only_changed_explicitly() {
        let mut d = Document::new(1, "1/2", None);
        assert_eq!(d.text(), "1/2");
        d.add_racket_language();
        assert_eq!(d.text(), "#lang racket\n1/2");
        d.undo();
        assert_eq!(d.text(), "1/2");
    }
    #[test]
    fn unicode_search_selects_literal() {
        let mut d = Document::new(1, "λx 你好 λx", None);
        assert!(d.find("你好", false).is_some());
        assert_eq!(d.content.selection().as_deref(), Some("你好"));
    }
    #[test]
    fn rejects_rich_and_invalid_input() {
        assert!(decode_file(b"#reader(lib\"read.ss\"\"wxme\")WXME0108".to_vec()).is_err());
        assert!(decode_file(vec![255]).is_err());
    }
}
