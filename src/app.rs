use crate::{
    document::Document,
    files::{self, LoadedFile},
    preferences::{self, Preferences},
    runtime::{Runtime, RuntimeEvent},
    theme as paint,
};
use iced::widget::{
    button, column, container, opaque, operation, pane_grid, row, scrollable, space, stack, text,
    text_editor, text_input,
};
use iced::{Center, Color, Element, Fill, Font, Subscription, Task, Theme, keyboard, window};
use serde_json::{Value, json};
use std::{
    collections::VecDeque,
    path::{Path, PathBuf},
    sync::{Arc, Mutex},
    time::{Duration, Instant},
};

const MONO: Font = Font::with_name("Noto Sans Mono");
const UI: Font = Font::with_name("Noto Sans");
const SAMPLE: &str = include_str!("../examples/welcome.rkt");
const OUTPUT_LIMIT: usize = 192 * 1024;
#[derive(Debug, Clone, Copy)]
enum Pane {
    Definitions,
    Interactions,
}
#[derive(Debug, Clone)]
enum Pending {
    Close(u64),
    Quit,
}
#[derive(Debug, Clone)]
struct Diagnostic {
    doc: Option<u64>,
    source: String,
    revision: Option<u64>,
    position: Option<usize>,
    line: usize,
    column: usize,
    span: usize,
    message: String,
    kind: String,
}
#[derive(Debug, Clone)]
struct RunRequest {
    source: String,
    path: Option<PathBuf>,
    cwd: PathBuf,
    doc: u64,
    revision: u64,
}
#[derive(Clone)]
pub enum Message {
    New,
    Sample,
    Open,
    OpenPath(PathBuf),
    Opened(Result<LoadedFile, String>),
    Save(bool),
    Saved {
        doc: u64,
        revision: u64,
        text: Arc<String>,
        result: Result<Option<PathBuf>, String>,
    },
    SelectTab(usize),
    CloseTab(u64),
    ConfirmSave,
    ConfirmDiscard,
    Cancel,
    Edit(text_editor::Action),
    InputEdit(text_editor::Action),
    OutputAction(text_editor::Action),
    Undo,
    Redo,
    InputUndo,
    InputRedo,
    CloseActive,
    ToggleSidebar,
    ToggleTheme,
    ToggleWrap,
    ToggleSearch,
    SearchChanged(String),
    SearchNext(bool),
    Resize(pane_grid::ResizeEvent),
    Run,
    Break,
    ForceStop,
    Tick,
    RuntimeSpawned {
        generation: u64,
        result: Result<Arc<Mutex<Option<Runtime>>>, String>,
    },
    Eval,
    History(bool),
    ClearOutput,
    SendInput(bool),
    StdinChanged(String),
    ChooseFolder,
    FolderChosen(Option<PathBuf>),
    WorkspaceLoaded(Vec<PathBuf>),
    AddLanguage,
    GoDiagnostic(usize),
    DismissNotice,
    ToggleSettings,
    RuntimePath(String),
    FontSize(bool),
    WindowClose(window::Id),
    Shortcut(keyboard::Key, keyboard::Modifiers),
    PreferencesSaved(Result<(), String>),
    ExitReady,
    Noop,
}
impl std::fmt::Debug for Message {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "WorkbenchMessage({:?})", std::mem::discriminant(self))
    }
}

pub struct App {
    documents: Vec<Document>,
    active: usize,
    next_doc: u64,
    panes: pane_grid::State<Pane>,
    sidebar: bool,
    dark: bool,
    wrap: bool,
    font_size: f32,
    workspace: PathBuf,
    workspace_files: Vec<PathBuf>,
    search_open: bool,
    search: String,
    search_note: String,
    notice: Option<String>,
    pending: Option<Pending>,
    saving: bool,
    settings: bool,
    runtime_path: String,
    runtime: Option<Runtime>,
    bridge_temp: Option<tempfile::TempDir>,
    runtime_ready: bool,
    starting: bool,
    boot_started: Option<Instant>,
    spawn_generation: u64,
    queued_run: Option<RunRequest>,
    active_id: Option<u64>,
    next_request: u64,
    session_doc: Option<u64>,
    session_revision: u64,
    session_name: String,
    session_source: Option<PathBuf>,
    pending_session: Option<(u64, u64, PathBuf, String)>,
    session_first_request: Option<u64>,
    session_last_request: Option<u64>,
    status: String,
    racket_version: String,
    run_started: Option<Instant>,
    last_elapsed: Option<Duration>,
    diagnostics: Vec<Diagnostic>,
    output: String,
    output_content: text_editor::Content,
    input: Document,
    input_history: VecDeque<String>,
    history_index: Option<usize>,
    checking: Option<(u64, String)>,
    check_status: Option<String>,
    input_requested: bool,
    stdin_text: String,
    window_id: Option<window::Id>,
    closing: bool,
    preferences_writing: bool,
    preferences_queued: Option<Preferences>,
}
impl App {
    pub fn new() -> (Self, Task<Message>) {
        let workspace = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
        let (preferences, preferences_notice) = match preferences::load() {
            Ok(p) => (p, None),
            Err(e) => (
                Preferences::default(),
                Some(format!(
                    "Preferences could not be loaded; using defaults. {e}"
                )),
            ),
        };
        let runtime_path = if std::env::var_os("RACKET_BIN").is_some() {
            find_racket()
        } else {
            preferences.racket_path.clone().unwrap_or_else(find_racket)
        };
        let state = Self {
            documents: vec![],
            active: 0,
            next_doc: 1,
            panes: pane_grid::State::with_configuration(pane_grid::Configuration::Split {
                axis: pane_grid::Axis::Horizontal,
                ratio: 0.62,
                a: Box::new(pane_grid::Configuration::Pane(Pane::Definitions)),
                b: Box::new(pane_grid::Configuration::Pane(Pane::Interactions)),
            }),
            sidebar: preferences.sidebar,
            dark: preferences.dark,
            wrap: preferences.wrap,
            font_size: preferences.font_size,
            workspace: workspace.clone(),
            workspace_files: vec![],
            search_open: false,
            search: String::new(),
            search_note: String::new(),
            notice: preferences_notice,
            pending: None,
            saving: false,
            settings: false,
            runtime_path,
            runtime: None,
            bridge_temp: None,
            runtime_ready: false,
            starting: false,
            boot_started: None,
            spawn_generation: 0,
            queued_run: None,
            active_id: None,
            next_request: 1,
            session_doc: None,
            session_revision: 0,
            session_name: String::new(),
            session_source: None,
            pending_session: None,
            session_first_request: None,
            session_last_request: None,
            status: "Ready when you are".into(),
            racket_version: String::new(),
            run_started: None,
            last_elapsed: None,
            diagnostics: vec![],
            output: String::new(),
            output_content: text_editor::Content::new(),
            input: Document::new(0, "", None),
            input_history: VecDeque::new(),
            history_index: None,
            checking: None,
            check_status: None,
            input_requested: false,
            stdin_text: String::new(),
            window_id: None,
            closing: false,
            preferences_writing: false,
            preferences_queued: None,
        };
        let mut tasks = vec![Task::perform(
            async move { files::workspace_files(&workspace) },
            Message::WorkspaceLoaded,
        )];
        if let Some(path) = std::env::args().nth(1).filter(|s| !s.starts_with('-')) {
            tasks.push(Task::perform(
                async move { files::load(PathBuf::from(path)) },
                Message::Opened,
            ));
        }
        (state, Task::batch(tasks))
    }
    pub fn theme(&self) -> Theme {
        paint::theme(self.dark)
    }
    pub fn title(&self) -> String {
        self.documents
            .get(self.active)
            .map(|d| {
                format!(
                    "{}{} · OpenRacket",
                    if d.dirty() { "● " } else { "" },
                    d.title()
                )
            })
            .unwrap_or("OpenRacket".into())
    }
    pub fn subscription(&self) -> Subscription<Message> {
        let ticks = if self.runtime.is_some() || self.starting {
            iced::time::every(Duration::from_millis(
                if self.active_id.is_some() || self.starting || self.checking.is_some() {
                    33
                } else {
                    500
                },
            ))
            .map(|_| Message::Tick)
        } else {
            Subscription::none()
        };
        Subscription::batch([
            ticks,
            iced::event::listen_with(|event, status, _| match event {
                iced::Event::Window(window::Event::CloseRequested) => None,
                iced::Event::Keyboard(keyboard::Event::KeyPressed { key, modifiers, .. })
                    if matches!(status, iced::event::Status::Ignored) =>
                {
                    Some(Message::Shortcut(key, modifiers))
                }
                _ => None,
            }),
            window::close_requests().map(Message::WindowClose),
        ])
    }
    pub fn new_document(&mut self, source: Option<String>) {
        let id = self.next_doc;
        self.next_doc += 1;
        self.documents
            .push(Document::new(id, source.as_deref().unwrap_or(""), None));
        self.active = self.documents.len() - 1;
    }
    fn request_id(&mut self) -> u64 {
        let id = self.next_request;
        self.next_request += 1;
        id
    }
    fn send(&mut self, value: Value) -> bool {
        let id = value["id"].as_u64();
        let result = self
            .runtime
            .as_ref()
            .ok_or_else(|| "The Racket session is not running. Run definitions again.".to_owned())
            .and_then(|runtime| runtime.send(value));
        if let Err(e) = result {
            self.notice = Some(e);
            if self.active_id == id {
                self.active_id = None;
                self.run_started = None;
            }
            if self.checking.as_ref().map(|(n, _)| *n) == id {
                self.checking = None;
                self.check_status = None;
            }
            self.status = "Request not sent".into();
            false
        } else {
            true
        }
    }
    fn append_output(&mut self, value: &str) {
        self.output.push_str(value);
        if self.output.len() > OUTPUT_LIMIT {
            let mut cut = self.output.len() - OUTPUT_LIMIT;
            while !self.output.is_char_boundary(cut) {
                cut += 1;
            }
            self.output.drain(..cut);
            self.output.insert_str(
                0,
                "[Earlier output trimmed to keep the editor responsive]\n",
            );
        }
    }
    fn refresh_output(&mut self) {
        self.output_content = text_editor::Content::with_text(&self.output);
        self.output_content
            .perform(text_editor::Action::Move(text_editor::Motion::DocumentEnd));
    }
    fn current(&self) -> Option<&Document> {
        self.documents.get(self.active)
    }
    fn save(&mut self, save_as: bool) -> Task<Message> {
        if self.saving {
            return Task::none();
        }
        let Some(d) = self.current() else {
            return Task::none();
        };
        let doc = d.id;
        let revision = d.revision;
        let text = Arc::new(d.text());
        let old_path = d.path.clone();
        let title = d.title();
        let expected = if save_as { None } else { d.disk_text.clone() };
        let directory = self.workspace.clone();
        self.documents[self.active].break_undo_group();
        self.saving = true;
        Task::perform(
            async move {
                let chosen = if save_as || old_path.is_none() {
                    rfd::AsyncFileDialog::new()
                        .set_title("Save Racket file")
                        .set_directory(directory)
                        .set_file_name(title)
                        .add_filter("Racket", &["rkt", "ss", "scm"])
                        .save_file()
                        .await
                        .map(|f| f.path().to_path_buf())
                } else {
                    old_path
                };
                let result = match chosen {
                    Some(path) => files::save(path, text.clone(), expected, save_as).map(Some),
                    None => Ok(None),
                };
                (doc, revision, text, result)
            },
            |(doc, revision, text, result)| Message::Saved {
                doc,
                revision,
                text,
                result,
            },
        )
    }
    fn start_run(&mut self, request: RunRequest) {
        let id = self.request_id();
        if !self.send(json!({"id":id,"op":"run","source":request.source,"path":request.path.as_ref().map(|p|p.to_string_lossy().into_owned()),"cwd":request.cwd.to_string_lossy()})){return;}
        // The bridge can reject an oversized/invalid request before resetting
        // its old namespace. Commit session identity only after `started`.
        self.pending_session = Some((
            request.doc,
            request.revision,
            request
                .path
                .clone()
                .unwrap_or_else(|| request.cwd.join("untitled.rkt")),
            self.documents
                .iter()
                .find(|d| d.id == request.doc)
                .map(Document::title)
                .unwrap_or_default(),
        ));
        self.active_id = Some(id);
        self.run_started = Some(Instant::now());
        self.status = "Running definitions".into();
    }
    fn close_now(&mut self, id: u64) {
        if let Some(index) = self.documents.iter().position(|d| d.id == id) {
            self.documents.remove(index);
            if self.active >= self.documents.len() {
                self.active = self.documents.len().saturating_sub(1);
            } else if index < self.active {
                self.active -= 1;
            }
        }
    }
    fn continue_pending(&mut self) -> Task<Message> {
        match self.pending.take() {
            Some(Pending::Close(id)) => self.close_now(id),
            Some(Pending::Quit) => {
                if let Some(d) = self.documents.iter().find(|d| d.dirty()) {
                    self.active = self.documents.iter().position(|x| x.id == d.id).unwrap();
                    self.pending = Some(Pending::Quit);
                } else {
                    return self.exit_after_cleanup();
                }
            }
            None => {}
        }
        Task::none()
    }
    fn queue_preferences(&mut self) -> Task<Message> {
        self.preferences_queued = Some(Preferences {
            dark: self.dark,
            font_size: self.font_size,
            racket_path: Some(self.runtime_path.trim().to_owned()),
            wrap: self.wrap,
            sidebar: self.sidebar,
        });
        self.write_next_preferences()
    }
    fn write_next_preferences(&mut self) -> Task<Message> {
        if self.preferences_writing {
            return Task::none();
        }
        if let Some(preferences) = self.preferences_queued.take() {
            self.preferences_writing = true;
            Task::perform(
                async move { preferences::save(&preferences) },
                Message::PreferencesSaved,
            )
        } else {
            Task::none()
        }
    }
    fn exit_after_cleanup(&mut self) -> Task<Message> {
        self.closing = true;
        self.spawn_generation += 1;
        self.starting = false;
        self.queued_run = None;
        self.status = "Closing Racket session…".into();
        let runtime = self.runtime.take();
        Task::perform(
            async move {
                if let Some(runtime) = runtime {
                    let _ = runtime.hard_stop();
                    // This runs on the async executor, never the UI thread. Give the
                    // supervisor time to kill/reap before the main process exits.
                    let deadline = Instant::now() + Duration::from_secs(3);
                    while runtime.is_running() && Instant::now() < deadline {
                        std::thread::sleep(Duration::from_millis(10));
                    }
                }
            },
            |_| Message::ExitReady,
        )
    }
    pub fn update(&mut self, message: Message) -> Task<Message> {
        if self.closing
            && !matches!(
                message,
                Message::ExitReady | Message::RuntimeSpawned { .. } | Message::PreferencesSaved(_)
            )
        {
            return Task::none();
        }
        // A confirmation is a real modal boundary: stale keyboard, navigation and file-open messages cannot change its target.
        if self.pending.is_some()
            && !matches!(
                message,
                Message::ConfirmSave
                    | Message::ConfirmDiscard
                    | Message::Cancel
                    | Message::Saved { .. }
                    | Message::Tick
                    | Message::RuntimeSpawned { .. }
                    | Message::WindowClose(_)
                    | Message::DismissNotice
                    | Message::PreferencesSaved(_)
            )
        {
            return Task::none();
        }
        match message {
            Message::New => {
                self.new_document(None);
                return operation::focus("definitions");
            }
            Message::Sample => {
                self.new_document(Some(SAMPLE.into()));
                return operation::focus("definitions");
            }
            Message::Open => {
                let dir = self.workspace.clone();
                return Task::perform(
                    async move {
                        rfd::AsyncFileDialog::new()
                            .set_title("Open Racket file")
                            .set_directory(dir)
                            .add_filter("Racket / Scheme", &["rkt", "ss", "scm", "rktd"])
                            .pick_file()
                            .await
                            .map(|f| files::load(f.path().into()))
                    },
                    |r| r.map(Message::Opened).unwrap_or(Message::Noop),
                );
            }
            Message::OpenPath(path) => {
                return Task::perform(async move { files::load(path) }, Message::Opened);
            }
            Message::Opened(result) => match result {
                Ok(file) => {
                    if let Some(index) = self
                        .documents
                        .iter()
                        .position(|d| d.path.as_ref() == Some(&file.path))
                    {
                        self.active = index;
                    } else {
                        let id = self.next_doc;
                        self.next_doc += 1;
                        self.documents
                            .push(Document::new(id, &file.text, Some(file.path.clone())));
                        self.active = self.documents.len() - 1;
                    }
                    if let Some(parent) = file.path.parent() {
                        self.workspace = parent.into();
                        let path = self.workspace.clone();
                        return Task::batch([
                            operation::focus("definitions"),
                            Task::perform(
                                async move { files::workspace_files(&path) },
                                Message::WorkspaceLoaded,
                            ),
                        ]);
                    }
                }
                Err(e) => self.notice = Some(e),
            },
            Message::Save(save_as) => return self.save(save_as),
            Message::Saved {
                doc,
                revision,
                text,
                result,
            } => {
                self.saving = false;
                match result {
                    Ok(Some(path)) => {
                        if let Some(d) = self.documents.iter_mut().find(|d| d.id == doc) {
                            d.mark_saved(revision, text, path);
                        }
                        let can_continue = self
                            .documents
                            .iter()
                            .find(|d| d.id == doc)
                            .is_none_or(|d| !d.dirty());
                        let pending_matches = match self.pending {
                            Some(Pending::Close(id)) => id == doc,
                            Some(Pending::Quit) => self.current().is_some_and(|d| d.id == doc),
                            None => false,
                        };
                        if can_continue && pending_matches {
                            return self.continue_pending();
                        }
                    }
                    Ok(None) => {}
                    Err(e) => self.notice = Some(e),
                }
            }
            Message::SelectTab(index) => {
                if index < self.documents.len() {
                    self.active = index;
                }
                return operation::focus("definitions");
            }
            Message::CloseActive => {
                if let Some(d) = self.current() {
                    return self.update(Message::CloseTab(d.id));
                }
            }
            Message::CloseTab(id) => {
                if self.documents.iter().any(|d| d.id == id && d.dirty()) {
                    self.pending = Some(Pending::Close(id));
                    self.active = self.documents.iter().position(|d| d.id == id).unwrap();
                } else {
                    self.close_now(id);
                }
            }
            Message::ConfirmSave => return self.save(false),
            Message::ConfirmDiscard => {
                match self.pending.clone() {
                    Some(Pending::Close(id)) => self.close_now(id),
                    Some(Pending::Quit) => {
                        if let Some(d) = self.current() {
                            self.close_now(d.id);
                        }
                    }
                    None => {}
                }
                return self.continue_pending();
            }
            Message::Cancel => {
                self.pending = None;
                if self.settings {
                    self.settings = false;
                    return self.queue_preferences();
                }
            }
            Message::Edit(action) => {
                if self.pending.is_none()
                    && let Some(d) = self.documents.get_mut(self.active)
                {
                    d.edit(action);
                }
            }
            Message::InputEdit(action) => {
                if self.pending.is_none() {
                    self.input.edit(action);
                    self.history_index = None;
                }
            }
            Message::OutputAction(action) => {
                if !action.is_edit() {
                    self.output_content.perform(action);
                }
            }
            Message::Undo => {
                if let Some(d) = self.documents.get_mut(self.active) {
                    d.undo();
                }
            }
            Message::Redo => {
                if let Some(d) = self.documents.get_mut(self.active) {
                    d.redo();
                }
            }
            Message::InputUndo => self.input.undo(),
            Message::InputRedo => self.input.redo(),
            Message::ToggleSidebar => {
                self.sidebar = !self.sidebar;
                return self.queue_preferences();
            }
            Message::ToggleTheme => {
                self.dark = !self.dark;
                if !self.settings {
                    return self.queue_preferences();
                }
            }
            Message::ToggleWrap => {
                self.wrap = !self.wrap;
                return self.queue_preferences();
            }
            Message::ToggleSearch => {
                self.search_open = !self.search_open;
                if self.search_open {
                    return operation::focus("search");
                }
            }
            Message::SearchChanged(s) => {
                self.search = s;
                self.search_note.clear();
            }
            Message::SearchNext(back) => {
                if let Some(d) = self.documents.get_mut(self.active) {
                    self.search_note = match d.find(&self.search, back) {
                        Some((line, _)) => format!("Line {line}"),
                        None => "No matches".into(),
                    };
                }
                return operation::focus("definitions");
            }
            Message::Resize(e) => self.panes.resize(e.split, e.ratio.clamp(0.25, 0.82)),
            Message::Run => {
                if self.active_id.is_some() || self.starting || self.checking.is_some() {
                    return Task::none();
                }
                let Some(d) = self.current() else {
                    return Task::none();
                };
                let request = RunRequest {
                    source: d.text(),
                    path: d.path.clone(),
                    cwd: d
                        .path
                        .as_ref()
                        .and_then(|p| p.parent())
                        .map(Path::to_path_buf)
                        .unwrap_or(self.workspace.clone()),
                    doc: d.id,
                    revision: d.revision,
                };
                if self.runtime_ready && self.runtime.as_ref().is_some_and(Runtime::is_running) {
                    self.start_run(request);
                } else {
                    self.queued_run = Some(request);
                    self.starting = true;
                    self.boot_started = Some(Instant::now());
                    self.spawn_generation += 1;
                    self.status = "Starting Racket".into();
                    self.runtime = None;
                    self.session_first_request = None;
                    self.session_last_request = None;
                    self.pending_session = None;
                    self.runtime_ready = false;
                    let directory = match tempfile::tempdir() {
                        Ok(d) => d,
                        Err(e) => {
                            self.starting = false;
                            self.notice = Some(e.to_string());
                            return Task::none();
                        }
                    };
                    let bridge = directory.path().join("bridge.rkt");
                    if let Err(e) = std::fs::write(&bridge, include_str!("../runtime/bridge.rkt")) {
                        self.starting = false;
                        self.notice = Some(e.to_string());
                        return Task::none();
                    }
                    self.bridge_temp = Some(directory);
                    let executable = PathBuf::from(&self.runtime_path);
                    let generation = self.spawn_generation;
                    return Task::perform(
                        async move {
                            Runtime::spawn(executable, bridge)
                                .map(|runtime| Arc::new(Mutex::new(Some(runtime))))
                        },
                        move |result| Message::RuntimeSpawned { generation, result },
                    );
                }
            }
            Message::RuntimeSpawned { generation, result } => {
                if generation != self.spawn_generation {
                    return Task::none();
                }
                match result {
                    Ok(holder) => {
                        self.runtime = holder.lock().ok().and_then(|mut r| r.take());
                    }
                    Err(e) => {
                        self.starting = false;
                        self.queued_run = None;
                        self.status = "Racket unavailable".into();
                        self.notice = Some(format!(
                            "{e}\nInstall Racket and set its executable in Runtime settings."
                        ));
                        self.settings = true;
                    }
                }
            }
            Message::Break => {
                if let Some(r) = &self.runtime {
                    if let Err(e) = r.break_then_kill() {
                        self.notice = Some(e);
                    } else {
                        self.status = "Interrupting…".into();
                    }
                }
            }
            Message::ForceStop => {
                self.spawn_generation += 1;
                self.starting = false;
                self.boot_started = None;
                self.queued_run = None;
                self.pending_session = None;
                self.session_first_request = None;
                self.session_last_request = None;
                if let Some(r) = self.runtime.take() {
                    let _ = r.hard_stop();
                }
                self.runtime_ready = false;
                self.active_id = None;
                self.checking = None;
                self.input_requested = false;
                self.status = "Session stopped".into();
            }
            Message::Tick => {
                if self.starting
                    && self
                        .boot_started
                        .is_some_and(|t| t.elapsed() > Duration::from_secs(10))
                {
                    let _ = self.update(Message::ForceStop);
                    self.notice=Some("Racket did not become ready within 10 seconds. Check the executable path in Runtime settings.".into());
                }
                let events = self
                    .runtime
                    .as_ref()
                    .map(Runtime::drain)
                    .unwrap_or_default();
                let mut output_changed = false;
                for event in events {
                    match event {
                        RuntimeEvent::Protocol(value) => {
                            output_changed |= self.handle_protocol(value);
                        }
                        RuntimeEvent::Fault(e) => {
                            self.notice = Some(e);
                        }
                        RuntimeEvent::Exited { code, success } => {
                            self.runtime = None;
                            self.session_first_request = None;
                            self.session_last_request = None;
                            self.pending_session = None;
                            self.runtime_ready = false;
                            self.starting = false;
                            self.active_id = None;
                            self.checking = None;
                            self.input_requested = false;
                            self.status = if success {
                                "Session ended".into()
                            } else {
                                format!(
                                    "Session stopped (exit {})",
                                    code.map(|c| c.to_string())
                                        .unwrap_or_else(|| "signal".into())
                                )
                            };
                        }
                        RuntimeEvent::DroppedOutput { count } => {
                            self.append_output(&format!(
                                "\n[{count} output events omitted to keep the editor responsive]\n"
                            ));
                            output_changed = true;
                        }
                    }
                }
                if output_changed {
                    self.refresh_output();
                }
            }
            Message::Eval => {
                if self.active_id.is_some() || self.checking.is_some() {
                    return Task::none();
                }
                if !self.runtime_ready || self.session_doc.is_none() {
                    self.notice=Some("Run a definitions buffer first. Interactions use the namespace from that run.".into());
                    return Task::none();
                }
                let source = self.input.text();
                if source.trim().is_empty() {
                    return Task::none();
                }
                let id = self.request_id();
                self.checking = Some((id, source.clone()));
                self.check_status = None;
                self.send(json!({"id":id,"op":"check","source":source}));
            }
            Message::History(back) => {
                if self.input_history.is_empty() {
                    return Task::none();
                }
                let index = if back {
                    self.history_index
                        .unwrap_or(self.input_history.len())
                        .saturating_sub(1)
                } else {
                    self.history_index
                        .map(|n| (n + 1).min(self.input_history.len()))
                        .unwrap_or(self.input_history.len())
                };
                self.history_index = Some(index);
                self.input = Document::new(
                    0,
                    self.input_history
                        .get(index)
                        .map(String::as_str)
                        .unwrap_or(""),
                    None,
                );
                self.input
                    .content
                    .perform(text_editor::Action::Move(text_editor::Motion::DocumentEnd));
                return operation::focus("interactions-input");
            }
            Message::ClearOutput => {
                self.output.clear();
                self.refresh_output();
            }
            Message::StdinChanged(s) => self.stdin_text = s,
            Message::SendInput(eof) => {
                let id = self.request_id();
                if self.send(json!({"id":id,"op":"input","text":if eof{String::new()}else{format!("{}\n",self.stdin_text)},"eof":eof})){self.stdin_text.clear();self.input_requested=false;}
            }
            Message::ChooseFolder => {
                return Task::perform(
                    async {
                        rfd::AsyncFileDialog::new()
                            .set_title("Open workspace folder")
                            .pick_folder()
                            .await
                            .map(|f| f.path().into())
                    },
                    Message::FolderChosen,
                );
            }
            Message::FolderChosen(Some(path)) => {
                self.workspace = path.clone();
                return Task::perform(
                    async move { files::workspace_files(&path) },
                    Message::WorkspaceLoaded,
                );
            }
            Message::FolderChosen(None) => {}
            Message::WorkspaceLoaded(files) => self.workspace_files = files,
            Message::AddLanguage => {
                if let Some(d) = self.documents.get_mut(self.active) {
                    d.add_racket_language();
                }
                self.notice = None;
                return operation::focus("definitions");
            }
            Message::GoDiagnostic(index) => {
                if let Some(diag) = self.diagnostics.get(index).cloned()
                    && let Some(i) = self.documents.iter().position(|d| Some(d.id) == diag.doc)
                {
                    self.active = i;
                    if diag
                        .revision
                        .is_some_and(|r| r != self.documents[i].revision)
                    {
                        self.notice=Some("This source changed after the diagnostic. Run again to get current locations.".into());
                        return Task::none();
                    }
                    if let Some(position) = diag.position {
                        self.documents[i].goto_offset(position, diag.span.max(1));
                    } else {
                        self.documents[i].goto(
                            diag.line.saturating_sub(1),
                            diag.column,
                            diag.span.max(1),
                        );
                    }
                    return operation::focus("definitions");
                }
            }
            Message::DismissNotice => self.notice = None,
            Message::ToggleSettings => self.settings = !self.settings,
            Message::RuntimePath(s) => self.runtime_path = s,
            Message::FontSize(up) => {
                self.font_size = (self.font_size + if up { 1.0 } else { -1.0 }).clamp(11.0, 24.0)
            }
            Message::WindowClose(id) => {
                self.window_id = Some(id);
                if let Some(index) = self.documents.iter().position(Document::dirty) {
                    self.active = index;
                    self.pending = Some(Pending::Quit);
                } else {
                    return self.exit_after_cleanup();
                }
            }
            Message::Shortcut(key, mods) => {
                if let Some(message) = shortcut(&key, mods) {
                    return self.update(message);
                }
            }
            Message::PreferencesSaved(result) => {
                self.preferences_writing = false;
                if let Err(e) = result {
                    self.notice = Some(format!(
                        "Preferences could not be saved; changes still apply this launch. {e}"
                    ));
                }
                return self.write_next_preferences();
            }
            Message::ExitReady => return iced::exit(),
            Message::Noop => {}
        }
        Task::none()
    }
    fn accepts_output(&self, id: Option<u64>) -> bool {
        id.is_some()
            && (id == self.active_id
                || matches!((id,self.session_first_request,self.session_last_request),(Some(id),Some(first),Some(last)) if id>=first&&id<=last))
    }
    fn handle_protocol(&mut self, value: Value) -> bool {
        let event = value["event"].as_str().unwrap_or("");
        let id = value["id"].as_u64();
        match event {
            "ready" => {
                if value["protocol"].as_u64() != Some(1) {
                    self.notice = Some("Unsupported Racket bridge protocol.".into());
                    return false;
                }
                self.runtime_ready = true;
                self.starting = false;
                self.boot_started = None;
                self.racket_version = value["racket_version"].as_str().unwrap_or("").into();
                if let Some(request) = self.queued_run.take() {
                    self.start_run(request);
                } else {
                    self.status = "Racket ready".into();
                }
            }
            "started"
                if id == self.active_id && id.is_some() && value["op"].as_str() == Some("run") =>
            {
                if let Some((doc, revision, source, name)) = self.pending_session.take() {
                    self.session_first_request = id;
                    self.session_last_request = id;
                    self.session_doc = Some(doc);
                    self.session_revision = revision;
                    self.session_source = Some(source);
                    self.session_name = name;
                    self.output.clear();
                    self.refresh_output();
                    self.diagnostics.clear();
                    self.input_requested = false;
                    return true;
                }
            }
            "started"
                if id == self.active_id && id.is_some() && value["op"].as_str() == Some("eval") =>
            {
                self.session_last_request = id;
            }
            "stdout" | "stderr" | "value" if self.accepts_output(id) => {
                let value = value["text"].as_str().unwrap_or("");
                self.append_output(value);
                if event == "value" && !value.ends_with('\n') {
                    self.append_output("\n");
                }
                return true;
            }
            "error" if id == self.active_id && id.is_some() => {
                let msg = value["message"]
                    .as_str()
                    .unwrap_or("Racket error")
                    .to_string();
                let kind = value["kind"].as_str().unwrap_or("runtime").to_string();
                self.append_output(&format!("\n{msg}\n"));
                let location = value["locations"].as_array().and_then(|l| l.first());
                let source = location
                    .and_then(|l| l["source"].as_str())
                    .unwrap_or("")
                    .to_string();
                let doc = if source.is_empty() {
                    if kind == "missing-language" {
                        self.session_doc
                    } else {
                        None
                    }
                } else if self
                    .session_source
                    .as_ref()
                    .is_some_and(|p| p.to_string_lossy() == source)
                {
                    self.session_doc
                } else {
                    self.documents
                        .iter()
                        .find(|d| {
                            d.path
                                .as_ref()
                                .is_some_and(|p| p.to_string_lossy() == source)
                        })
                        .map(|d| d.id)
                };
                let revision = doc.and_then(|id| {
                    if Some(id) == self.session_doc {
                        Some(self.session_revision)
                    } else {
                        self.documents
                            .iter()
                            .find(|d| d.id == id && !d.dirty())
                            .map(|d| d.revision)
                    }
                });
                let doc = doc.filter(|_| revision.is_some());
                self.diagnostics.push(Diagnostic {
                    doc,
                    source,
                    revision,
                    position: location
                        .and_then(|l| l["position"].as_u64())
                        .map(|p| p as usize),
                    line: location.and_then(|l| l["line"].as_u64()).unwrap_or(1) as usize,
                    column: location.and_then(|l| l["column"].as_u64()).unwrap_or(0) as usize,
                    span: location.and_then(|l| l["span"].as_u64()).unwrap_or(1) as usize,
                    message: msg,
                    kind,
                });
                return true;
            }
            "done" if id == self.active_id && id.is_some() => {
                self.pending_session = None;
                self.active_id = None;
                self.input_requested = false;
                self.last_elapsed = self.run_started.take().map(|t| t.elapsed());
                self.status = match value["status"].as_str() {
                    Some("ok") => "Ready",
                    Some("interrupted") => "Interrupted",
                    _ => "Finished with an error",
                }
                .into();
            }
            "input-request" if id == self.active_id && id.is_some() => {
                self.input_requested = true;
                self.status = "Waiting for input".into();
            }
            "truncated" if self.accepts_output(id) => {
                self.append_output("\n[Runtime output limit reached]\n");
                return true;
            }
            "check" if self.checking.as_ref().map(|(i, _)| *i) == id => {
                self.check_status = value["status"].as_str().map(str::to_owned);
            }
            "done" if self.checking.as_ref().map(|(i, _)| *i) == id && id.is_some() => {
                let (_, source) = self.checking.take().unwrap();
                let status = self.check_status.take();
                if source != self.input.text() {
                    self.status =
                        "Input changed while checking. Press Enter again when ready.".into();
                    return false;
                }
                match status.as_deref() {
                    Some("incomplete") => {
                        self.input
                            .edit(text_editor::Action::Edit(text_editor::Edit::Enter));
                        self.status = "More input needed. Continue the expression below.".into();
                    }
                    Some("complete") | Some("error") => {
                        let eval_id = self.request_id();
                        if !self.send(json!({"id":eval_id,"op":"eval","source":source})) {
                            return false;
                        }
                        self.active_id = Some(eval_id);
                        self.run_started = Some(Instant::now());
                        self.append_output(&format!("> {}\n", source.trim_end()));
                        self.input = Document::new(0, "", None);
                        self.input_history.push_back(source.clone());
                        if self.input_history.len() > 100 {
                            self.input_history.pop_front();
                        }
                        self.history_index = None;
                        self.status = "Evaluating interaction".into();
                        return true;
                    }
                    _ => {
                        self.notice = Some("The runtime returned an unknown reader status.".into());
                    }
                }
            }
            _ => {}
        }
        false
    }
    pub fn view(&self) -> Element<'_, Message> {
        let palette = paint::colors(&self.theme());
        let busy = self.active_id.is_some() || self.starting || self.checking.is_some();
        let toolbar = container(
            row![
                button(text("◧").size(19))
                    .padding([8, 10])
                    .style(paint::subtle)
                    .on_press(Message::ToggleSidebar),
                container(text("λ").font(MONO).size(22).color(palette.accent)).padding([2, 8]),
                column![
                    text("OpenRacket").size(15),
                    text("RACKET, RECONSIDERED").size(9).color(palette.muted)
                ]
                .spacing(0),
                space::horizontal(),
                button(text("Open").size(12))
                    .padding([8, 12])
                    .style(paint::subtle)
                    .on_press(Message::Open),
                button(text(if self.saving { "Saving…" } else { "Save" }).size(12))
                    .padding([8, 12])
                    .style(paint::subtle)
                    .on_press_maybe(
                        (self.current().is_some() && !self.saving).then_some(Message::Save(false))
                    ),
                container(text("│").color(palette.border)).padding([0, 4]),
                button(
                    row![
                        text("▶").size(11),
                        text(if busy { "Running…" } else { "Run" }).size(12)
                    ]
                    .spacing(8)
                    .align_y(Center)
                )
                .padding([8, 16])
                .style(paint::primary)
                .on_press_maybe((self.current().is_some() && !busy).then_some(Message::Run)),
                button(text("■ Break").size(12))
                    .padding([8, 12])
                    .style(paint::subtle)
                    .on_press_maybe(busy.then_some(Message::Break)),
                button(text(if self.dark { "☼" } else { "◐" }).size(18))
                    .padding([6, 10])
                    .style(paint::subtle)
                    .on_press(Message::ToggleTheme),
                button(text("⚙").size(17))
                    .padding([6, 10])
                    .style(paint::subtle)
                    .on_press(Message::ToggleSettings)
            ]
            .spacing(4)
            .align_y(Center),
        )
        .padding([9, 14])
        .style(paint::chrome);
        let panes = pane_grid(&self.panes, |_, pane, _| {
            pane_grid::Content::new(match pane {
                Pane::Definitions => self.definitions(),
                Pane::Interactions => self.interactions(),
            })
        })
        .spacing(1)
        .on_resize(6, Message::Resize)
        .height(Fill);
        let mut body = row![];
        if self.sidebar {
            body = body.push(self.sidebar_view());
        }
        body = body.push(panes);
        let cursor = self
            .current()
            .map(|d| {
                let p = d.content.cursor().position;
                let chars = d
                    .content
                    .line(p.line)
                    .map(|l| l.text[..p.column.min(l.text.len())].chars().count())
                    .unwrap_or(0);
                format!("Ln {}, Col {}", p.line + 1, chars + 1)
            })
            .unwrap_or_default();
        let session_stale = self
            .session_doc
            .and_then(|id| self.documents.iter().find(|d| d.id == id))
            .is_some_and(|d| d.revision != self.session_revision);
        let bottom = container(
            row![
                text(if busy { "●" } else { "○" }).size(10).color(if busy {
                    palette.accent
                } else {
                    palette.muted
                }),
                text(&self.status).size(11).color(palette.muted),
                text(
                    self.last_elapsed
                        .filter(|_| !busy)
                        .map(|d| format!("  {:.0} ms", d.as_secs_f64() * 1000.0))
                        .unwrap_or_default()
                )
                .size(10)
                .color(palette.muted),
                space::horizontal(),
                text(if session_stale {
                    "Definitions changed since Run"
                } else {
                    ""
                })
                .size(10)
                .color(palette.accent),
                text(cursor).size(10).color(palette.muted),
                text("UTF-8").size(10).color(palette.muted),
                text("Racket").size(10).color(palette.muted)
            ]
            .spacing(14)
            .align_y(Center),
        )
        .padding([7, 17])
        .style(paint::chrome);
        let mut layout = column![toolbar];
        if let Some(notice) = &self.notice {
            layout = layout.push(
                container(
                    row![
                        text(notice).size(12).color(palette.error),
                        space::horizontal(),
                        button("×")
                            .style(paint::subtle)
                            .on_press(Message::DismissNotice)
                    ]
                    .align_y(Center)
                    .spacing(12),
                )
                .padding([9, 18])
                .style(paint::panel),
            );
        }
        layout = layout.push(body.height(Fill)).push(bottom);
        let base: Element<_> = container(layout)
            .width(Fill)
            .height(Fill)
            .style(paint::surface)
            .into();
        if self.pending.is_some() {
            stack![base, self.confirm_modal()].into()
        } else if self.settings {
            stack![base, self.settings_modal()].into()
        } else {
            base
        }
    }
    fn sidebar_view(&self) -> Element<'_, Message> {
        let p = paint::colors(&self.theme());
        let name = self
            .workspace
            .file_name()
            .map(|s| s.to_string_lossy().into_owned())
            .unwrap_or("workspace".into());
        let mut files = column![].spacing(3);
        for path in &self.workspace_files {
            let label = path
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .into_owned();
            let active = self.current().and_then(|d| d.path.as_ref()) == Some(path);
            files = files.push(
                button(
                    row![
                        text("λ").font(MONO).size(12).color(if active {
                            p.accent
                        } else {
                            p.muted
                        }),
                        text(label).size(12)
                    ]
                    .spacing(10),
                )
                .width(Fill)
                .padding([7, 10])
                .style(move |theme, status| {
                    let mut s = paint::subtle(theme, status);
                    if active {
                        s.background = Some(paint::colors(theme).border.into());
                    }
                    s
                })
                .on_press(Message::OpenPath(path.clone())),
            );
        }
        if self.workspace_files.is_empty() {
            files = files.push(text("No Racket files here yet.").size(11).color(p.muted));
        }
        let panel = column![
            row![
                text("WORKSPACE").size(10).color(p.muted),
                space::horizontal(),
                button("+").style(paint::subtle).on_press(Message::New)
            ]
            .align_y(Center),
            button(row![text("▾").size(11), text(name).size(12)].spacing(7))
                .padding([7, 8])
                .style(paint::subtle)
                .on_press(Message::ChooseFolder),
            scrollable(files).height(Fill),
            column![
                button(text("+  New file").size(12))
                    .padding([8, 10])
                    .width(Fill)
                    .style(paint::subtle)
                    .on_press(Message::New),
                button(text("Open folder…").size(12))
                    .padding([8, 10])
                    .width(Fill)
                    .style(paint::subtle)
                    .on_press(Message::ChooseFolder),
                text("A little room to think.").size(10).color(p.muted)
            ]
            .spacing(7)
        ]
        .spacing(10);
        container(panel)
            .padding([18, 14])
            .width(220)
            .height(Fill)
            .style(paint::panel)
            .into()
    }
    fn definitions(&self) -> Element<'_, Message> {
        let p = paint::colors(&self.theme());
        if self.documents.is_empty() {
            return self.welcome();
        }
        let mut tabs = row![].spacing(2);
        for (index, d) in self.documents.iter().enumerate() {
            let selected = index == self.active;
            let color = if selected { p.text } else { p.muted };
            tabs = tabs.push(
                container(
                    row![
                        button(
                            row![
                                text("λ").font(MONO).size(11).color(if selected {
                                    p.accent
                                } else {
                                    p.muted
                                }),
                                text(d.title()).size(12).color(color),
                                text(if d.dirty() { "●" } else { "" })
                                    .size(8)
                                    .color(p.accent)
                            ]
                            .spacing(8)
                            .align_y(Center)
                        )
                        .padding([11, 12])
                        .style(paint::subtle)
                        .on_press(Message::SelectTab(index)),
                        button(text("×").size(14).color(p.muted))
                            .padding([5, 7])
                            .style(paint::subtle)
                            .on_press(Message::CloseTab(d.id))
                    ]
                    .align_y(Center),
                )
                .style(move |_| container::Style {
                    background: Some(if selected { p.background } else { p.chrome }.into()),
                    border: iced::Border {
                        color: if selected { p.accent } else { p.chrome },
                        width: if selected { 1.0 } else { 0.0 },
                        radius: 4.into(),
                    },
                    ..Default::default()
                }),
            );
        }
        tabs = tabs.push(
            button("+")
                .padding([7, 10])
                .style(paint::subtle)
                .on_press(Message::New),
        );
        let d = &self.documents[self.active];
        let language = d
            .content
            .line(0)
            .map(|l| l.text.into_owned())
            .filter(|s| s.starts_with("#lang "))
            .unwrap_or_else(|| "Plain text".into());
        let header = container(
            row![
                text("DEFINITIONS").size(9).color(p.muted),
                text("/ ").size(10).color(p.border),
                text(language).font(MONO).size(10).color(p.muted),
                space::horizontal(),
                button(text("Find").size(10))
                    .padding([3, 8])
                    .style(paint::subtle)
                    .on_press(Message::ToggleSearch),
                button(text(if self.wrap { "Wrap on" } else { "Wrap off" }).size(10))
                    .padding([3, 8])
                    .style(paint::subtle)
                    .on_press(Message::ToggleWrap)
            ]
            .spacing(8)
            .align_y(Center),
        )
        .padding([8, 16]);
        let editor = text_editor(&d.content)
            .id("definitions")
            .on_action(Message::Edit)
            .font(MONO)
            .size(self.font_size)
            .padding([10, 24])
            .height(Fill)
            .wrapping(if self.wrap {
                text::Wrapping::Word
            } else {
                text::Wrapping::None
            })
            .highlight_with::<iced::highlighter::Highlighter>(
                iced::highlighter::Settings {
                    token: "lisp".into(),
                    theme: if self.dark {
                        iced::highlighter::Theme::Base16Ocean
                    } else {
                        iced::highlighter::Theme::InspiredGitHub
                    },
                },
                paint::syntax_format,
            )
            .style(paint::editor)
            .key_binding(|event| {
                if !matches!(event.status, text_editor::Status::Focused { .. }) {
                    return None;
                }
                if let Some(m) = shortcut(&event.key, event.modifiers) {
                    Some(text_editor::Binding::Custom(m))
                } else {
                    text_editor::Binding::from_key_press(event)
                }
            });
        let mut layout = column![
            container(
                scrollable(tabs).direction(scrollable::Direction::Horizontal(
                    scrollable::Scrollbar::new()
                ))
            )
            .style(paint::chrome),
            header
        ];
        if self.search_open {
            layout = layout.push(
                container(
                    row![
                        text_input("Find in current file…", &self.search)
                            .id("search")
                            .on_input(Message::SearchChanged)
                            .on_submit(Message::SearchNext(false))
                            .padding(8)
                            .size(12),
                        text(&self.search_note).size(11).color(p.muted),
                        button("↑")
                            .style(paint::subtle)
                            .on_press(Message::SearchNext(true)),
                        button("↓")
                            .style(paint::subtle)
                            .on_press(Message::SearchNext(false)),
                        button("×")
                            .style(paint::subtle)
                            .on_press(Message::ToggleSearch)
                    ]
                    .spacing(5)
                    .align_y(Center),
                )
                .padding([4, 16]),
            );
        }
        layout = layout.push(editor);
        let has_language = d.content.lines().take(20).any(|l| {
            l.text.trim_start().starts_with("#lang") || l.text.trim_start().starts_with("#reader")
        });
        if !has_language && !d.content.is_empty() {
            layout = layout.push(
                container(
                    row![
                        text("Choose a language to run this plain-text buffer.")
                            .size(11)
                            .color(p.muted),
                        space::horizontal(),
                        button(text("Add #lang racket").size(11))
                            .padding([6, 10])
                            .style(paint::subtle)
                            .on_press(Message::AddLanguage)
                    ]
                    .align_y(Center),
                )
                .padding([6, 16])
                .style(paint::panel),
            );
        }
        container(layout.height(Fill)).style(paint::surface).into()
    }
    fn welcome(&self) -> Element<'_, Message> {
        let p = paint::colors(&self.theme());
        let hero = column![
            text("λ").font(MONO).size(54).color(p.accent),
            text("Make room for an idea.").size(28),
            text("A focused place for Racket. Write above, explore below.")
                .size(13)
                .color(p.muted),
            space::vertical().height(12),
            row![
                button(text("New file").size(12))
                    .padding([10, 18])
                    .style(paint::primary)
                    .on_press(Message::New),
                button(text("Open a file").size(12))
                    .padding([10, 18])
                    .style(paint::subtle)
                    .on_press(Message::Open),
                button(text("Try an example →").size(12))
                    .padding([10, 18])
                    .style(paint::subtle)
                    .on_press(Message::Sample)
            ]
            .spacing(10),
            space::vertical().height(18),
            row![
                text("⌘ / Ctrl + N   New").size(10).color(p.muted),
                text("⌘ / Ctrl + R   Run").size(10).color(p.muted)
            ]
            .spacing(24)
        ]
        .spacing(10);
        container(container(hero).max_width(650))
            .padding(42)
            .center_x(Fill)
            .center_y(Fill)
            .style(paint::surface)
            .into()
    }
    fn interactions(&self) -> Element<'_, Message> {
        let p = paint::colors(&self.theme());
        let busy = self.active_id.is_some() || self.starting;
        let session = if self.session_doc.is_some() {
            format!("{}  ·  Racket {}", self.session_name, self.racket_version)
        } else {
            "Run a file to begin a session".into()
        };
        let mut header = row![
            text("INTERACTIONS").size(10).color(p.text),
            container(
                text(if busy {
                    "BUSY"
                } else if self.runtime_ready {
                    "READY"
                } else {
                    "IDLE"
                })
                .size(8)
                .color(if busy || self.runtime_ready {
                    p.accent
                } else {
                    p.muted
                })
            )
            .padding([3, 6])
            .style(paint::card),
            text(session).size(10).color(p.muted),
            space::horizontal(),
            button(text("Clear").size(10))
                .padding([4, 7])
                .style(paint::subtle)
                .on_press(Message::ClearOutput)
        ]
        .spacing(10)
        .align_y(Center);
        if busy {
            header = header.push(
                button(text("Force stop").size(10))
                    .padding([4, 7])
                    .style(paint::danger)
                    .on_press(Message::ForceStop),
            );
        }
        let mut layout =
            column![container(header).padding([11, 16]).style(paint::chrome)].spacing(0);
        if !self.diagnostics.is_empty() {
            let mut list = column![].spacing(3);
            for (i, diag) in self.diagnostics.iter().enumerate().take(4) {
                let msg = diag.message.lines().next().unwrap_or("Racket error");
                list = list.push(
                    button(
                        row![
                            text("!").color(p.error).size(12),
                            text(format!(
                                "{} · {}:{}    {}",
                                diag.kind,
                                if diag.source == "interactions" {
                                    "Interactions".into()
                                } else {
                                    Path::new(&diag.source)
                                        .file_name()
                                        .map(|s| s.to_string_lossy().into_owned())
                                        .unwrap_or_else(|| "Definitions".into())
                                },
                                diag.line,
                                msg
                            ))
                            .size(11)
                            .color(p.error)
                        ]
                        .spacing(10),
                    )
                    .padding([6, 12])
                    .style(paint::subtle)
                    .on_press_maybe(diag.doc.map(|_| Message::GoDiagnostic(i))),
                );
            }
            layout = layout.push(container(list).style(paint::panel));
        }
        if self.output.is_empty() {
            layout=layout.push(container(column![text("Your program, in conversation.").size(14).color(p.muted),text("Results appear here. After Run, try an expression using your definitions.").size(11).color(p.muted)].spacing(9)).padding([18,24]).height(Fill));
        } else {
            layout = layout.push(
                text_editor(&self.output_content)
                    .on_action(Message::OutputAction)
                    .font(MONO)
                    .size(self.font_size - 1.0)
                    .padding([12, 24])
                    .height(Fill)
                    .style(paint::editor)
                    .key_binding(|event| {
                        if !matches!(event.status, text_editor::Status::Focused { .. }) {
                            return None;
                        }
                        match event.key.as_ref() {
                            keyboard::Key::Character("c") if event.modifiers.command() => {
                                Some(text_editor::Binding::Copy)
                            }
                            keyboard::Key::Character("a") if event.modifiers.command() => {
                                Some(text_editor::Binding::SelectAll)
                            }
                            keyboard::Key::Character("z" | "y") if event.modifiers.command() => {
                                Some(text_editor::Binding::Custom(Message::Noop))
                            }
                            _ => text_editor::Binding::from_key_press(event),
                        }
                    }),
            );
        }
        if self.input_requested {
            layout = layout.push(
                container(
                    row![
                        text("stdin ›").font(MONO).size(12).color(p.accent),
                        text_input("Program is waiting for input…", &self.stdin_text)
                            .on_input(Message::StdinChanged)
                            .on_submit(Message::SendInput(false))
                            .size(12)
                            .padding(8),
                        button("Send")
                            .style(paint::primary)
                            .on_press(Message::SendInput(false)),
                        button("EOF")
                            .style(paint::subtle)
                            .on_press(Message::SendInput(true))
                    ]
                    .spacing(8)
                    .align_y(Center),
                )
                .padding([8, 16])
                .style(paint::panel),
            );
        }
        let input = text_editor(&self.input.content)
            .id("interactions-input")
            .placeholder("Enter a Racket expression…")
            .on_action(Message::InputEdit)
            .font(MONO)
            .size(self.font_size - 1.0)
            .height(75)
            .padding([9, 12])
            .style(paint::editor)
            .key_binding(|event| {
                if !matches!(event.status, text_editor::Status::Focused { .. }) {
                    return None;
                }
                match event.key.as_ref() {
                    keyboard::Key::Character("z") if event.modifiers.command() => {
                        Some(text_editor::Binding::Custom(if event.modifiers.shift() {
                            Message::InputRedo
                        } else {
                            Message::InputUndo
                        }))
                    }
                    keyboard::Key::Character("y") if event.modifiers.command() => {
                        Some(text_editor::Binding::Custom(Message::InputRedo))
                    }
                    keyboard::Key::Named(keyboard::key::Named::Enter)
                        if !event.modifiers.shift() =>
                    {
                        Some(text_editor::Binding::Custom(Message::Eval))
                    }
                    keyboard::Key::Named(keyboard::key::Named::ArrowUp)
                        if event.modifiers.alt() =>
                    {
                        Some(text_editor::Binding::Custom(Message::History(true)))
                    }
                    keyboard::Key::Named(keyboard::key::Named::ArrowDown)
                        if event.modifiers.alt() =>
                    {
                        Some(text_editor::Binding::Custom(Message::History(false)))
                    }
                    _ => text_editor::Binding::from_key_press(event),
                }
            });
        layout = layout.push(
            container(
                row![
                    text("›").font(MONO).size(20).color(p.accent),
                    input,
                    column![
                        button(text("Evaluate ↵").size(11))
                            .padding([8, 12])
                            .style(paint::subtle)
                            .on_press_maybe(
                                (!busy && self.checking.is_none()).then_some(Message::Eval)
                            ),
                        row![
                            button(text("↑").size(12))
                                .style(paint::subtle)
                                .on_press(Message::History(true)),
                            button(text("↓").size(12))
                                .style(paint::subtle)
                                .on_press(Message::History(false))
                        ]
                        .spacing(2)
                    ]
                    .spacing(3)
                ]
                .spacing(8)
                .align_y(Center),
            )
            .padding([7, 16])
            .style(paint::chrome),
        );
        container(layout.height(Fill)).style(paint::surface).into()
    }
    fn confirm_modal(&self) -> Element<'_, Message> {
        let p = paint::colors(&self.theme());
        let name = self.current().map(Document::title).unwrap_or_default();
        let card = container(
            column![
                text("Keep your changes?").size(21),
                text(format!("{} has unsaved edits.", name))
                    .size(13)
                    .color(p.muted),
                text("Save them before closing, or keep this file open.")
                    .size(12)
                    .color(p.muted),
                space::vertical().height(7),
                row![
                    button("Cancel")
                        .padding([9, 14])
                        .style(paint::subtle)
                        .on_press(Message::Cancel),
                    space::horizontal(),
                    button("Discard")
                        .padding([9, 14])
                        .style(paint::danger)
                        .on_press(Message::ConfirmDiscard),
                    button(if self.saving {
                        "Saving…"
                    } else {
                        "Save changes"
                    })
                    .padding([9, 14])
                    .style(paint::primary)
                    .on_press_maybe((!self.saving).then_some(Message::ConfirmSave))
                ]
                .spacing(8)
            ]
            .spacing(12),
        )
        .padding(26)
        .width(490)
        .style(paint::card);
        modal(card.into())
    }
    fn settings_modal(&self) -> Element<'_, Message> {
        let p = paint::colors(&self.theme());
        let card=container(column![row![text("Make yourself at home").size(21),space::horizontal(),button("×").style(paint::subtle).on_press(Message::Cancel)],text("RACKET EXECUTABLE").size(10).color(p.muted),text_input("racket or /path/to/racket",&self.runtime_path).on_input(Message::RuntimePath).padding(11).size(13),text("Requires a local Racket installation. Applied to the next new session.\nSaved with your appearance settings. RACKET_BIN overrides it on launch.").size(11).color(p.muted),row![text("Editor type size").size(13),space::horizontal(),button("−").style(paint::subtle).on_press(Message::FontSize(false)),text(format!("{} px",self.font_size)).size(12),button("+").style(paint::subtle).on_press(Message::FontSize(true))].spacing(10).align_y(Center),row![text("Appearance").size(13),space::horizontal(),button(if self.dark{"Switch to light"}else{"Switch to dark"}).style(paint::subtle).on_press(Message::ToggleTheme)],text("Plain-text Racket preview").size(12).color(p.accent),text("Real Racket evaluation, persistent interactions, files and editing.\nTeaching tools, macro stepper, WXME and DrRacket plugins are not included yet.").size(11).color(p.muted),button("Done").padding([9,15]).style(paint::primary).on_press(Message::Cancel)].spacing(18)).padding(28).width(570).style(paint::card);
        modal(card.into())
    }
}
fn modal<'a>(card: Element<'a, Message>) -> Element<'a, Message> {
    opaque(
        container(card)
            .width(Fill)
            .height(Fill)
            .center_x(Fill)
            .center_y(Fill)
            .style(|_| container::Style {
                background: Some(Color::from_rgba(0.0, 0.0, 0.0, 0.58).into()),
                ..Default::default()
            }),
    )
}
fn shortcut(key: &keyboard::Key, mods: keyboard::Modifiers) -> Option<Message> {
    if mods.command() {
        match key.as_ref() {
            keyboard::Key::Character("w") => Some(Message::CloseActive),
            keyboard::Key::Character("n") => Some(Message::New),
            keyboard::Key::Character("o") => Some(Message::Open),
            keyboard::Key::Character("s") => Some(Message::Save(mods.shift())),
            keyboard::Key::Character("r") => Some(Message::Run),
            keyboard::Key::Character("f") => Some(Message::ToggleSearch),
            keyboard::Key::Character("b") => Some(Message::ToggleSidebar),
            keyboard::Key::Character("z") => Some(if mods.shift() {
                Message::Redo
            } else {
                Message::Undo
            }),
            keyboard::Key::Character("y") => Some(Message::Redo),
            keyboard::Key::Character(".") => Some(Message::Break),
            _ => None,
        }
    } else {
        match key {
            keyboard::Key::Named(keyboard::key::Named::F5) => Some(Message::Run),
            _ => None,
        }
    }
}
fn find_racket() -> String {
    if let Ok(path) = std::env::var("RACKET_BIN") {
        return path;
    }
    // PATH is preferred. These are conventional app-bundle locations, never a downloaded executable.
    if std::env::var_os("PATH").is_some_and(|paths| {
        std::env::split_paths(&paths).any(|p| {
            p.join(if cfg!(windows) {
                "racket.exe"
            } else {
                "racket"
            })
            .is_file()
        })
    }) {
        return "racket".into();
    }
    for p in [
        "/Applications/Racket v9.3/bin/racket",
        "/Applications/Racket v9.2/bin/racket",
        "/Applications/Racket/bin/racket",
        "/opt/homebrew/bin/racket",
        "/usr/local/bin/racket",
    ] {
        if Path::new(p).is_file() {
            return p.into();
        }
    }
    "racket".into()
}
pub fn run() -> iced::Result {
    iced::application(App::new, App::update, App::view)
        .title(App::title)
        .theme(App::theme)
        .subscription(App::subscription)
        .default_font(UI)
        .font(include_bytes!("../assets/NotoSans-Regular.ttf").as_slice())
        .font(include_bytes!("../assets/NotoSansMono-Regular.ttf").as_slice())
        .window_size((1280.0, 860.0))
        .window(window::Settings {
            size: iced::Size::new(1280.0, 860.0),
            min_size: Some(iced::Size::new(860.0, 600.0)),
            exit_on_close_request: false,
            ..Default::default()
        })
        .run()
}
#[cfg(test)]
#[path = "../qa/offscreen.rs"]
mod offscreen;
