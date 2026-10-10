# Native acceptance gate (partially run)

A component bitmap is not evidence that a DrRacket window launched, that a native
layout works, or that stock workflows pass. First Linux CI compiled the real host
and passed the native toolbar/canvas tests; later fixture assertions failed. The
remaining dynamic gates below stay open. See `ci-first-run.json`.

## Environment status

1. The official full Racket 9.3 distribution installed in the authorized Linux
   CI environment. Local package transactions remain cancelled and untouched.
2. Linux CI provides a permitted native display. The separate local display
   attempt could not create sockets and remains blocked without retry.
3. macOS CI must get past its public-repository metadata precheck, then use the
   official stock 9.3 distribution on the same OS/display scale/settings as the
   supplied reference. Linux cannot pass the macOS gate.

## Ordered checks

- Run tests/native-toolbar-test.rkt against the stock source and the patched copy.
  This exercises the real switchable-button% callback identity, event transitions,
  disabled behavior, command semantics, labels, compact metrics and paint call.
- Compare stock/modern main windows at reference size and narrow widths. Check
  same filename/definition selectors at left; same registered toolbar ordering,
  language-dependent visibility and compact behavior at right. No reordered or
  synthetic stock controls are allowed.
- Compare actual stock idle, edited, running, Stop then Kill, debugging, resumed,
  cancelled, and teaching-language states. Component proof states are input
  fixtures only and are not captures of these workflow states.
- Verify Run/Stop, default errortrace/instrumentation, 128MB setting where selected,
  persistent input/EOF and errors, Check Syntax arrows/rename, debugger stepping,
  Macro Stepper, teaching Step/check-expect, dialogs and menu commands.
- Round-trip WXME with image/XML/comment boxes, undo/redo, clipboard, protected
  interactions, links, rich values, saves/recovery and multi-tab switching.
- Check active/inactive selection, line numbers, editor scroll/focus/IME, native
  accessibility, HiDPI glyphs, theme switching and typography changes.
- Compare stock and modern process with identical programs/settings: cold startup,
  warm startup, large-file edits, scrolling, Run, Check Syntax, tool opening and
  output bursts. Record medians/tails and hardware. No speed claims before this.
- Restart in OPENRACKET_UI=stock; verify original painter/measurement values.
  This flag does not restore previously saved editor theme/font preferences.
  Use Restore Previous Appearance before disabling the tool and reopen windows;
  revert the source with scripts/apply-overlay.py --revert. Alternatively discard
  the entire disposable profile, keeping every original installation untouched.

Stock class/source preservation is strong architectural evidence, but does not
replace these dynamic tests. It does not certify every third-party plugin.
