//! Independent native-widget snapshot harness.
//!
//! This uses Iced's real tiny-skia renderer without creating a window, socket,
//! browser, or graphical session. It verifies widget rendering and layout; it
//! does not prove operating-system focus, clipboard, dialogs, or keyboard input.

use iced::advanced::renderer::Headless;
use iced::{Element, Font, Pixels, Size, Theme};
use iced_runtime::user_interface::{Cache, UserInterface};
use std::path::Path;

// Fixtures use stable UI defaults regardless of the tester's saved preferences.
// App::new only reads preferences; the returned async tasks are not executed.
fn app_fixture() -> super::App {
    let (mut app, _) = super::App::new();
    app.dark = true;
    app.sidebar = true;
    app.wrap = false;
    app.font_size = 15.0;
    app.notice = None;
    app
}

fn load_fonts() {
    use std::borrow::Cow;
    let mut fonts = iced::advanced::graphics::text::font_system()
        .write()
        .unwrap();
    fonts.load_font(Cow::Borrowed(include_bytes!(
        "../assets/NotoSans-Regular.ttf"
    )));
    fonts.load_font(Cow::Borrowed(include_bytes!(
        "../assets/NotoSansMono-Regular.ttf"
    )));
}

pub fn capture<Message>(
    view: Element<'_, Message>,
    theme: &Theme,
    width: u32,
    height: u32,
    output: &Path,
) where
    Message: 'static,
{
    load_fonts();
    let mut renderer = iced::Renderer::new(Font::with_name("Noto Sans"), Pixels(14.0));
    let mut ui = UserInterface::build(
        view,
        Size::new(width as f32, height as f32),
        Cache::new(),
        &mut renderer,
    );
    let mut messages = Vec::new();
    let _ = ui.update(
        &[iced::Event::Window(iced::window::Event::RedrawRequested(
            std::time::Instant::now(),
        ))],
        iced::mouse::Cursor::Unavailable,
        &mut renderer,
        &mut iced::advanced::clipboard::Null,
        &mut messages,
    );
    ui.draw(
        &mut renderer,
        theme,
        &iced::advanced::renderer::Style {
            text_color: theme.palette().text,
        },
        iced::mouse::Cursor::Unavailable,
    );
    let bytes = renderer.screenshot(Size::new(width, height), 1.0, theme.palette().background);
    assert_eq!(bytes.len(), width as usize * height as usize * 4);
    assert!(
        bytes.chunks_exact(4).any(|p| p[0] > 180),
        "no visible bright pixels"
    );
    if let Some(parent) = output.parent() {
        std::fs::create_dir_all(parent).expect("create QA screenshot directory");
    }
    // Every pixel is rendered over an opaque background, so the RGBA bytes are
    // valid tiny-skia premultiplied pixels as well as ordinary RGBA pixels.
    tiny_skia::Pixmap::from_vec(bytes, tiny_skia::IntSize::from_wh(width, height).unwrap())
        .expect("valid snapshot dimensions")
        .save_png(output)
        .expect("write native widget snapshot");
}

#[test]
fn capture_native_ui() {
    use std::borrow::Cow;
    {
        let mut fonts = iced::advanced::graphics::text::font_system()
            .write()
            .unwrap();
        fonts.load_font(Cow::Borrowed(include_bytes!(
            "../assets/NotoSans-Regular.ttf"
        )));
        fonts.load_font(Cow::Borrowed(include_bytes!(
            "../assets/NotoSansMono-Regular.ttf"
        )));
    }
    let mut app = app_fixture();
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("qa/screenshots");
    for dark in [true, false] {
        app.dark = dark;
        let label = if dark { "dark" } else { "light" };
        capture(
            app.view(),
            &app.theme(),
            1280,
            860,
            &root.join(format!("welcome-{label}.png")),
        );
    }
    app.new_document(Some(
        "#lang racket\n\n;; A small program with real interactions\n(define (square x)\n  (* x x))\n\n(define greeting \"Hello, Racket λ\")\n(displayln greeting)\n(square 12)\n".to_owned(),
    ));
    app.session_doc = Some(app.documents[0].id);
    app.session_name = app.documents[0].title();
    app.runtime_ready = true;
    app.racket_version = "9.3".into();
    app.status = "Ready".into();
    app.output =
        "Hello, Racket λ\n144\n> (square 7)\n49\n> (map square '(1 2 3 4))\n'(1 4 9 16)\n".into();
    app.refresh_output();
    for dark in [true, false] {
        app.dark = dark;
        let label = if dark { "dark" } else { "light" };
        capture(
            app.view(),
            &app.theme(),
            1280,
            860,
            &root.join(format!("editor-{label}.png")),
        );
        capture(
            app.view(),
            &app.theme(),
            900,
            650,
            &root.join(format!("editor-small-{label}.png")),
        );
    }
    app.active_id = Some(42);
    app.handle_protocol(serde_json::json!({"event":"error","id":42,"kind":"runtime",
        "message":"square: contract violation\n  expected: number?\n  given: \"hello\"",
        "locations":[{"source":"interactions","line":1,"column":0,"position":1,"span":16}]}));
    app.handle_protocol(serde_json::json!({"event":"done","id":42,"status":"error"}));
    app.refresh_output();
    for dark in [true, false] {
        app.dark = dark;
        let label = if dark { "dark" } else { "light" };
        capture(
            app.view(),
            &app.theme(),
            1280,
            860,
            &root.join(format!("error-{label}.png")),
        );
    }
}

fn dirty_app() -> super::App {
    let mut app = app_fixture();
    app.new_document(Some("#lang racket\n42\n".into()));
    app.documents[0].edit(iced::widget::text_editor::Action::Edit(
        iced::widget::text_editor::Edit::Insert(';'),
    ));
    app
}

#[test]
fn qa_cancel_dirty_close_preserves_document_and_session() {
    let mut app = dirty_app();
    let id = app.documents[0].id;
    let original = app.documents[0].text();
    app.session_doc = Some(id);
    app.active_id = Some(17);
    let _ = app.update(super::Message::CloseTab(id));
    assert!(app.pending.is_some());
    let _ = app.update(super::Message::Cancel);
    assert!(app.pending.is_none());
    assert_eq!(app.documents.len(), 1);
    assert_eq!(app.documents[0].text(), original);
    assert!(app.documents[0].dirty());
    assert_eq!(app.active_id, Some(17));
}

#[test]
fn qa_unrelated_save_completion_cannot_discard_pending_dirty_tab() {
    let mut app = dirty_app();
    let first = app.documents[0].id;
    let revision = app.documents[0].revision;
    let saved = std::sync::Arc::new(app.documents[0].text());
    app.new_document(Some("second".into()));
    app.documents[1].edit(iced::widget::text_editor::Action::Edit(
        iced::widget::text_editor::Edit::Insert('λ'),
    ));
    let second = app.documents[1].id;
    let _ = app.update(super::Message::CloseTab(second));
    let _ = app.update(super::Message::Saved {
        doc: first,
        revision,
        text: saved,
        result: Ok(Some(std::path::PathBuf::from("/tmp/qa-first.rkt"))),
    });
    assert!(app.documents.iter().any(|d| d.id == second && d.dirty()));
    assert!(app.pending.is_some());
}

#[test]
fn qa_shortcuts_cannot_change_dirty_modal_target() {
    let mut app = dirty_app();
    let id = app.documents[0].id;
    let _ = app.update(super::Message::CloseTab(id));
    let before = app.documents[0].text();
    let _ = app.update(super::Message::Shortcut(
        iced::keyboard::Key::Character("n".into()),
        iced::keyboard::Modifiers::COMMAND,
    ));
    assert_eq!(
        app.documents.len(),
        1,
        "new shortcut must not change pending close target"
    );
    let _ = app.update(super::Message::Undo);
    assert_eq!(
        app.documents[0].text(),
        before,
        "undo must not edit behind modal"
    );
}

#[test]
fn qa_check_must_finish_before_eval_is_sent() {
    let mut app = dirty_app();
    app.input.replace_all("(+ 1 2)".into());
    app.checking = Some((7, "(+ 1 2)".into()));
    app.handle_protocol(serde_json::json!({"event":"check","id":7,"status":"complete"}));
    assert!(
        app.active_id.is_none(),
        "check result precedes bridge done; do not race busy"
    );
    app.handle_protocol(serde_json::json!({"event":"done","id":7,"status":"ok"}));
    assert!(
        app.checking.is_none(),
        "completed reader check must clear its pending state"
    );
    // This fixture intentionally has no runtime. The attempted eval is then
    // correctly rejected; no busy state may be fabricated on failed send.
    assert!(app.active_id.is_none());
    assert!(
        app.notice
            .as_ref()
            .is_some_and(|s| s.contains("not running"))
    );
}

#[test]
fn qa_edit_during_reader_check_is_retained_and_not_submitted() {
    let mut app = dirty_app();
    app.input.replace_all("new input".into());
    app.checking = Some((7, "old input".into()));
    app.handle_protocol(serde_json::json!({"event":"check","id":7,"status":"complete"}));
    app.handle_protocol(serde_json::json!({"event":"done","id":7,"status":"ok"}));
    assert_eq!(app.input.text(), "new input");
    assert!(app.active_id.is_none());
    assert!(app.checking.is_none());
    assert!(
        app.notice.is_none(),
        "no send should be attempted for stale input"
    );
    assert!(app.status.contains("Input changed"));
}

#[test]
fn qa_run_cannot_overlap_pending_reader_check() {
    let mut app = dirty_app();
    app.checking = Some((7, "(+ 1 2)".into()));
    let _ = app.update(super::Message::Run);
    assert!(!app.starting);
    assert!(app.queued_run.is_none());
    assert!(app.active_id.is_none());
}

#[test]
fn qa_stale_output_cannot_overwrite_new_run() {
    let mut app = dirty_app();
    app.active_id = Some(42);
    app.output = "new result".into();
    app.handle_protocol(serde_json::json!({"event":"stdout","id":41,"text":"stale result"}));
    app.handle_protocol(serde_json::json!({"event":"done","id":41,"status":"ok"}));
    assert_eq!(app.output, "new result");
    assert_eq!(app.active_id, Some(42));
}

#[test]
fn qa_background_output_stays_in_current_session_only() {
    let mut app = dirty_app();
    let doc = app.documents[0].id;
    app.active_id = Some(42);
    app.pending_session = Some((
        doc,
        0,
        "/tmp/qa-session.rkt".into(),
        "qa-session.rkt".into(),
    ));
    app.handle_protocol(serde_json::json!({"event":"started","id":42,"op":"run"}));
    app.handle_protocol(serde_json::json!({"event":"done","id":42,"status":"ok"}));
    app.handle_protocol(
        serde_json::json!({"event":"stdout","id":42,"text":"late current output\n"}),
    );
    assert!(app.output.contains("late current output"));
    app.active_id = Some(43);
    app.handle_protocol(serde_json::json!({"event":"started","id":43,"op":"eval"}));
    app.handle_protocol(serde_json::json!({"event":"done","id":43,"status":"ok"}));
    app.handle_protocol(
        serde_json::json!({"event":"stdout","id":43,"text":"late interaction output\n"}),
    );
    assert!(app.output.contains("late interaction output"));
    app.active_id = Some(99);
    app.pending_session = Some((
        doc,
        0,
        "/tmp/new-session.rkt".into(),
        "new-session.rkt".into(),
    ));
    app.handle_protocol(serde_json::json!({"event":"started","id":99,"op":"run"}));
    app.handle_protocol(serde_json::json!({"event":"stdout","id":42,"text":"wrong old output"}));
    assert!(!app.output.contains("wrong old output"));
    app.handle_protocol(serde_json::json!({"event":"done","id":99,"status":"ok"}));
    app.handle_protocol(serde_json::json!({"event":"stdout","id":99,"text":"right new output"}));
    assert!(app.output.contains("right new output"));
    let _ = app.update(super::Message::ForceStop);
    let before = app.output.clone();
    app.handle_protocol(serde_json::json!({"event":"stdout","id":99,"text":"late killed output"}));
    assert_eq!(app.output, before);
}

#[test]
fn qa_rejected_send_keeps_session_input_and_idle_state() {
    let mut app = dirty_app();
    app.session_doc = Some(app.documents[0].id);
    app.runtime_ready = true;
    app.output = "previous result".into();
    let previous_session = app.session_doc;
    app.start_run(super::RunRequest {
        source: "#lang racket\n42".into(),
        path: None,
        cwd: std::path::PathBuf::from("/tmp"),
        doc: 999,
        revision: 0,
    });
    assert!(app.active_id.is_none());
    assert_eq!(app.output, "previous result");
    assert_eq!(app.session_doc, previous_session);
    app.input.replace_all("(+ 1 2)".into());
    let input = app.input.text();
    let _ = app.update(super::Message::Eval);
    assert!(app.active_id.is_none());
    assert!(app.checking.is_none());
    assert_eq!(app.input.text(), input);
    assert!(app.notice.is_some());
}

#[test]
fn qa_failed_or_cancelled_save_keeps_dirty_close_pending() {
    for result in [Err("disk unavailable".into()), Ok(None)] {
        let mut app = dirty_app();
        let doc = app.documents[0].id;
        let revision = app.documents[0].revision;
        let before = std::sync::Arc::new(app.documents[0].text());
        let _ = app.update(super::Message::CloseTab(doc));
        let _ = app.update(super::Message::Saved {
            doc,
            revision,
            text: before.clone(),
            result,
        });
        assert!(app.pending.is_some());
        assert_eq!(app.documents[0].text(), before.as_str());
        assert!(app.documents[0].dirty());
        let _ = app.update(super::Message::Cancel);
        assert_eq!(app.documents.len(), 1);
    }
}

#[test]
fn qa_diagnostic_uses_original_tab_and_refuses_stale_positions() {
    let mut app = app_fixture();
    app.new_document(Some("a\r\n\tλ你好🌱 x\r\nnext".into()));
    let doc = app.documents[0].id;
    let path = std::path::PathBuf::from("/tmp/qa-original.rkt");
    app.documents[0].path = Some(path.clone());
    app.session_source = Some(path.clone());
    app.session_doc = Some(doc);
    app.session_revision = app.documents[0].revision;
    app.active_id = Some(42);
    app.new_document(Some("other tab".into()));
    app.handle_protocol(serde_json::json!({"event":"error","id":42,"kind":"syntax",
        "message":"x: unbound identifier",
        "locations":[{"source":path,"line":2,"column":13,"position":9,"span":1}]}));
    let _ = app.update(super::Message::GoDiagnostic(0));
    assert_eq!(app.active, 0);
    assert_eq!(app.documents[0].content.selection().as_deref(), Some("x"));
    app.documents[0].edit(iced::widget::text_editor::Action::Edit(
        iced::widget::text_editor::Edit::Insert('z'),
    ));
    let cursor = app.documents[0].content.cursor();
    let _ = app.update(super::Message::GoDiagnostic(0));
    assert_eq!(app.documents[0].content.cursor(), cursor);
    assert!(app.notice.as_ref().is_some_and(|s| s.contains("changed")));
}

#[test]
fn qa_interaction_error_does_not_jump_to_wrong_definitions_line() {
    let mut app = dirty_app();
    app.session_doc = Some(app.documents[0].id);
    app.active_id = Some(42);
    app.documents[0]
        .content
        .perform(iced::widget::text_editor::Action::Move(
            iced::widget::text_editor::Motion::DocumentEnd,
        ));
    let cursor = app.documents[0].content.cursor();
    app.handle_protocol(serde_json::json!({"event":"error","id":42,"kind":"runtime",
        "message":"interaction failed",
        "locations":[{"source":"interactions","line":1,"column":0,"position":1,"span":4}]}));
    let _ = app.update(super::Message::GoDiagnostic(0));
    assert_eq!(app.documents[0].content.cursor(), cursor);
}

fn widget_events(
    app: &super::App,
    cache: &mut Cache,
    renderer: &mut iced::Renderer,
    events: &[iced::Event],
    position: iced::Point,
) -> Vec<super::Message> {
    let mut ui = UserInterface::build(
        app.view(),
        Size::new(1280.0, 860.0),
        std::mem::take(cache),
        renderer,
    );
    let mut messages = Vec::new();
    let _ = ui.update(
        &[iced::Event::Window(iced::window::Event::RedrawRequested(
            std::time::Instant::now(),
        ))],
        iced::mouse::Cursor::Available(position),
        renderer,
        &mut iced::advanced::clipboard::Null,
        &mut messages,
    );
    let _ = ui.update(
        events,
        iced::mouse::Cursor::Available(position),
        renderer,
        &mut iced::advanced::clipboard::Null,
        &mut messages,
    );
    *cache = ui.into_cache();
    messages
}

fn press(
    key: iced::keyboard::Key,
    modifiers: iced::keyboard::Modifiers,
    text: Option<&str>,
) -> iced::Event {
    iced::Event::Keyboard(iced::keyboard::Event::KeyPressed {
        modified_key: key.clone(),
        key,
        physical_key: iced::keyboard::key::Physical::Unidentified(
            iced::keyboard::key::NativeCode::Unidentified,
        ),
        location: iced::keyboard::Location::Standard,
        modifiers,
        text: text.map(Into::into),
        repeat: false,
    })
}

#[test]
fn qa_native_widget_typing_undo_and_command_bindings() {
    use iced::{
        keyboard::{Key, Modifiers, key::Named},
        mouse::{Button, Event},
    };
    let mut app = app_fixture();
    app.new_document(Some("#lang racket\n42\n".into()));
    let mut cache = Cache::new();
    let mut renderer = iced::Renderer::new(Font::with_name("Noto Sans"), Pixels(14.0));
    let definitions = iced::Point::new(420.0, 175.0);
    // Prime the initial PaneGrid child-order cache before user input.
    let _ = widget_events(&app, &mut cache, &mut renderer, &[], definitions);
    let clicked = widget_events(
        &app,
        &mut cache,
        &mut renderer,
        &[
            iced::Event::Mouse(Event::ButtonPressed(Button::Left)),
            iced::Event::Mouse(Event::ButtonReleased(Button::Left)),
        ],
        definitions,
    );
    assert!(
        clicked.iter().any(|m| matches!(m, super::Message::Edit(_))),
        "native definitions click must publish editor action, got {clicked:?}"
    );
    for message in clicked {
        let _ = app.update(message);
    }
    let before = app.documents[0].text();
    let typed = widget_events(
        &app,
        &mut cache,
        &mut renderer,
        &[press(
            Key::Character("λ".into()),
            Modifiers::empty(),
            Some("λ"),
        )],
        definitions,
    );
    assert!(
        typed.iter().any(|m| matches!(m, super::Message::Edit(_))),
        "native editor must receive typing"
    );
    for message in typed {
        let _ = app.update(message);
    }
    assert_ne!(app.documents[0].text(), before);
    assert!(app.documents[0].text().contains('λ'));
    let undo = widget_events(
        &app,
        &mut cache,
        &mut renderer,
        &[press(Key::Character("z".into()), Modifiers::COMMAND, None)],
        definitions,
    );
    assert!(
        undo.iter().any(|m| matches!(m, super::Message::Undo)),
        "Ctrl+Z must reach application undo"
    );
    for message in undo {
        let _ = app.update(message);
    }
    assert_eq!(app.documents[0].text(), before);
    for (key, expected) in [("s", "save"), ("r", "run")] {
        let messages = widget_events(
            &app,
            &mut cache,
            &mut renderer,
            &[press(Key::Character(key.into()), Modifiers::COMMAND, None)],
            definitions,
        );
        assert!(
            messages.iter().any(|m| match expected {
                "save" => matches!(m, super::Message::Save(false)),
                "run" => matches!(m, super::Message::Run),
                _ => false,
            }),
            "Ctrl+{key} must reach application {expected}"
        );
    }
    let definitions_enter = widget_events(
        &app,
        &mut cache,
        &mut renderer,
        &[press(Key::Named(Named::Enter), Modifiers::empty(), None)],
        definitions,
    );
    assert!(definitions_enter.iter().any(|m| matches!(
        m,
        super::Message::Edit(iced::widget::text_editor::Action::Edit(
            iced::widget::text_editor::Edit::Enter
        ))
    )));
    assert!(
        !definitions_enter
            .iter()
            .any(|m| matches!(m, super::Message::Eval))
    );
    let input = iced::Point::new(420.0, 785.0);
    let clicked = widget_events(
        &app,
        &mut cache,
        &mut renderer,
        &[
            iced::Event::Mouse(Event::ButtonPressed(Button::Left)),
            iced::Event::Mouse(Event::ButtonReleased(Button::Left)),
        ],
        input,
    );
    for message in clicked {
        let _ = app.update(message);
    }
    let evaluate = widget_events(
        &app,
        &mut cache,
        &mut renderer,
        &[press(Key::Named(Named::Enter), Modifiers::COMMAND, None)],
        input,
    );
    assert!(
        evaluate.iter().any(|m| matches!(m, super::Message::Eval)),
        "Ctrl+Enter must evaluate interactions"
    );
    let enter = widget_events(
        &app,
        &mut cache,
        &mut renderer,
        &[press(Key::Named(Named::Enter), Modifiers::empty(), None)],
        input,
    );
    assert!(
        enter.iter().any(|m| matches!(m, super::Message::Eval)),
        "plain Enter submits through real reader"
    );
    let shift_enter = widget_events(
        &app,
        &mut cache,
        &mut renderer,
        &[press(Key::Named(Named::Enter), Modifiers::SHIFT, None)],
        input,
    );
    assert!(
        shift_enter.iter().any(|m| matches!(
            m,
            super::Message::InputEdit(iced::widget::text_editor::Action::Edit(
                iced::widget::text_editor::Edit::Enter
            ))
        )),
        "Shift+Enter inserts explicit newline"
    );
    assert!(
        !shift_enter
            .iter()
            .any(|m| matches!(m, super::Message::Eval))
    );
    let typed = widget_events(
        &app,
        &mut cache,
        &mut renderer,
        &[press(
            Key::Character("λ".into()),
            Modifiers::empty(),
            Some("λ"),
        )],
        input,
    );
    for message in typed {
        let _ = app.update(message);
    }
    assert_eq!(app.input.text(), "λ");
    let undo = widget_events(
        &app,
        &mut cache,
        &mut renderer,
        &[press(Key::Character("z".into()), Modifiers::COMMAND, None)],
        input,
    );
    assert!(undo.iter().any(|m| matches!(m, super::Message::InputUndo)));
    assert!(
        !undo.iter().any(|m| matches!(m, super::Message::Undo)),
        "unfocused Definitions must not steal undo"
    );
    for message in undo {
        let _ = app.update(message);
    }
    assert!(app.input.text().is_empty());
    assert_eq!(app.documents[0].text(), before);
}

#[test]
fn qa_native_output_wheel_scrolling_changes_visible_transcript() {
    use iced::mouse::{Event, ScrollDelta};
    let mut app = app_fixture();
    app.new_document(Some("#lang racket\n42".into()));
    app.output = (0..100).map(|i| format!("Transcript line {i}\n")).collect();
    app.refresh_output();
    let dir = tempfile::tempdir().unwrap();
    let before = dir.path().join("before.png");
    let after = dir.path().join("after.png");
    capture(app.view(), &app.theme(), 1280, 860, &before);
    let mut cache = Cache::new();
    let mut renderer = iced::Renderer::new(Font::with_name("Noto Sans"), Pixels(14.0));
    let position = iced::Point::new(420.0, 650.0);
    let _ = widget_events(&app, &mut cache, &mut renderer, &[], position);
    let scrolled = widget_events(
        &app,
        &mut cache,
        &mut renderer,
        &[iced::Event::Mouse(Event::WheelScrolled {
            delta: ScrollDelta::Lines { x: 0.0, y: 3.0 },
        })],
        position,
    );
    assert!(scrolled.iter().any(|m| matches!(
        m,
        super::Message::OutputAction(iced::widget::text_editor::Action::Scroll { .. })
    )));
    for message in scrolled {
        let _ = app.update(message);
    }
    capture(app.view(), &app.theme(), 1280, 860, &after);
    assert_ne!(
        std::fs::read(before).unwrap(),
        std::fs::read(after).unwrap(),
        "scroll event must change the visible native transcript"
    );
}

fn pump_until(app: &mut super::App, condition: impl Fn(&super::App) -> bool) {
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(10);
    loop {
        let _ = app.update(super::Message::Tick);
        if condition(app) {
            return;
        }
        assert!(
            std::time::Instant::now() < deadline,
            "app runtime timed out: status={}, notice={:?}, output={}",
            app.status,
            app.notice,
            app.output
        );
        std::thread::sleep(std::time::Duration::from_millis(5));
    }
}

#[test]
#[ignore = "requires real Racket; set RACKET_EXECUTABLE"]
fn qa_real_app_run_reader_check_interactions_and_break() {
    let executable = std::env::var_os("RACKET_EXECUTABLE").expect("set RACKET_EXECUTABLE");
    let mut app = app_fixture();
    app.runtime = Some(
        super::Runtime::spawn(
            executable.into(),
            Path::new(env!("CARGO_MANIFEST_DIR")).join("runtime/bridge.rkt"),
        )
        .unwrap(),
    );
    pump_until(&mut app, |a| a.runtime_ready);
    app.new_document(Some("#lang racket\n(define (square x) (* x x))\n(define answer 40)\n(displayln \"Hello, OpenRacket λ\")\n(square 12)\n".into()));
    let document = app.documents[0].id;
    let _ = app.update(super::Message::Run);
    pump_until(&mut app, |a| a.active_id.is_none());
    assert_eq!(app.status, "Ready");
    assert_eq!(app.session_doc, Some(document));
    assert!(app.output.contains("144"));
    assert!(
        app.documents[0].path.is_none(),
        "Run must not force saving an unsaved buffer"
    );
    app.input.replace_all("(+ answer 2)".into());
    let _ = app.update(super::Message::Eval);
    pump_until(&mut app, |a| a.checking.is_none() && a.active_id.is_none());
    assert!(app.output.ends_with("42\n"), "{}", app.output);
    assert!(app.input.text().is_empty());
    assert!(
        app.diagnostics.is_empty(),
        "reader check must not race eval with busy error"
    );
    app.input.replace_all("(square 7)".into());
    let _ = app.update(super::Message::Eval);
    pump_until(&mut app, |a| a.checking.is_none() && a.active_id.is_none());
    assert!(app.output.ends_with("49\n"), "{}", app.output);
    app.refresh_output();
    capture(
        app.view(),
        &app.theme(),
        1280,
        860,
        &Path::new(env!("CARGO_MANIFEST_DIR")).join("qa/screenshots/editor-real-run.png"),
    );
    app.input.replace_all("(+ answer".into());
    let _ = app.update(super::Message::Eval);
    pump_until(&mut app, |a| a.checking.is_none() && a.active_id.is_none());
    assert!(app.input.text().starts_with("(+ answer"));
    app.input.replace_all("(let loop () (loop))".into());
    let _ = app.update(super::Message::Eval);
    pump_until(&mut app, |a| a.active_id.is_some() && a.checking.is_none());
    let _ = app.update(super::Message::Break);
    pump_until(&mut app, |a| a.active_id.is_none());
    assert!(
        app.runtime_ready,
        "cooperative break should preserve the runtime"
    );
    app.input.replace_all("(+ answer 3)".into());
    let _ = app.update(super::Message::Eval);
    pump_until(&mut app, |a| a.checking.is_none() && a.active_id.is_none());
    assert!(app.output.ends_with("43\n"), "{}", app.output);
    app.input
        .replace_all("(thread (lambda () (sleep 0.05) (displayln \"background arrived\")))".into());
    let _ = app.update(super::Message::Eval);
    pump_until(&mut app, |a| a.checking.is_none() && a.active_id.is_none());
    pump_until(&mut app, |a| a.output.contains("background arrived\n"));
    assert_eq!(app.session_doc, Some(document));
    let prior_output = app.output.clone();
    app.new_document(Some("#lang racket\n99\n".into()));
    let rejected_document = app.documents[1].id;
    app.start_run(super::RunRequest {
        source: "x".repeat(8 * 1024 * 1024 + 1),
        path: None,
        cwd: Path::new(env!("CARGO_MANIFEST_DIR")).into(),
        doc: rejected_document,
        revision: 0,
    });
    assert!(
        app.active_id.is_none(),
        "host-side oversized rejection must leave UI idle"
    );
    assert_eq!(
        app.output, prior_output,
        "failed send must retain prior results"
    );
    assert!(app.notice.is_some());
    assert_eq!(app.session_doc, Some(document));
    app.start_run(super::RunRequest {
        source: "x".repeat(2 * 1024 * 1024 + 1),
        path: None,
        cwd: Path::new(env!("CARGO_MANIFEST_DIR")).into(),
        doc: rejected_document,
        revision: 0,
    });
    pump_until(&mut app, |a| a.active_id.is_none());
    assert_eq!(app.status, "Finished with an error");
    assert!(app.output.contains("2,097,152"));
    assert_eq!(
        app.session_doc,
        Some(document),
        "rejected run must keep prior namespace's tab identity"
    );
    app.input.replace_all("(+ answer 4)".into());
    let _ = app.update(super::Message::Eval);
    pump_until(&mut app, |a| a.checking.is_none() && a.active_id.is_none());
    assert!(
        app.output.ends_with("44\n"),
        "oversized requests must not corrupt old namespace: {}",
        app.output
    );
}

#[test]
#[ignore = "run with cargo test --release --bin openracket qa_benchmark -- --ignored --nocapture"]
#[allow(clippy::assertions_on_constants)]
fn qa_benchmark_release_model_and_native_render() {
    assert!(!cfg!(debug_assertions), "benchmark must use --release");
    load_fonts();
    use iced::widget::text_editor::{Action, Edit};
    use std::time::Instant;
    let source = format!(
        "#lang racket\n{}",
        ";; A representative Racket source line for editor scaling.\n".repeat(18500)
    );
    let bytes = source.len();
    let start = Instant::now();
    let mut doc = super::Document::new(1, &source, None);
    let load_ms = start.elapsed().as_secs_f64() * 1000.0;
    let mut edits = Vec::new();
    for _ in 0..200 {
        let start = Instant::now();
        doc.edit(Action::Edit(Edit::Insert('λ')));
        doc.undo();
        edits.push(start.elapsed().as_secs_f64() * 1000.0);
    }
    assert_eq!(doc.text(), source);
    let mut app = app_fixture();
    app.new_document(Some(source));
    let mut renderer = iced::Renderer::new(Font::with_name("Noto Sans"), Pixels(14.0));
    let mut cache = Cache::new();
    let mut frames = Vec::new();
    for _ in 0..21 {
        let start = Instant::now();
        let mut ui =
            UserInterface::build(app.view(), Size::new(1280.0, 860.0), cache, &mut renderer);
        let mut messages = Vec::new();
        let _ = ui.update(
            &[iced::Event::Window(iced::window::Event::RedrawRequested(
                Instant::now(),
            ))],
            iced::mouse::Cursor::Unavailable,
            &mut renderer,
            &mut iced::advanced::clipboard::Null,
            &mut messages,
        );
        ui.draw(
            &mut renderer,
            &app.theme(),
            &iced::advanced::renderer::Style {
                text_color: app.theme().palette().text,
            },
            iced::mouse::Cursor::Unavailable,
        );
        let pixels =
            renderer.screenshot(Size::new(1280, 860), 1.0, app.theme().palette().background);
        assert_eq!(pixels.len(), 1280 * 860 * 4);
        cache = ui.into_cache();
        frames.push(start.elapsed().as_secs_f64() * 1000.0);
    }
    fn stats(mut values: Vec<f64>) -> serde_json::Value {
        values.sort_by(f64::total_cmp);
        serde_json::json!({"samples":values.len(), "min_ms":values[0],
            "median_ms":values[values.len()/2], "p95_ms":values[((values.len() as f64*0.95).ceil() as usize-1).min(values.len()-1)],
            "max_ms":values[values.len()-1]})
    }
    let first_frame = frames.remove(0);
    let result = serde_json::json!({
        "environment":"Debian 13 Linux cloud executor; Rust release; Iced 0.14 tiny-skia software renderer; no OS window",
        "source_bytes":bytes, "source_lines":18501, "initial_model_load_ms":load_ms,
        "edit_plus_undo":stats(edits), "first_layout_draw_raster_ms":first_frame,
        "warm_layout_draw_raster":stats(frames),
        "limits":"Timing covers model operations and CPU widget layout/draw/raster only, not OS startup, compositor, human-perceived latency, macOS, IME or file dialogs."
    });
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("qa/release-benchmark.json");
    std::fs::write(path, serde_json::to_string_pretty(&result).unwrap()).unwrap();
    println!("{}", serde_json::to_string_pretty(&result).unwrap());
}
