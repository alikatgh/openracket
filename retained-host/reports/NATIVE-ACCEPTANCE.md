# Native acceptance gate (not yet run)

A component bitmap is not evidence that a DrRacket window launched, that a native
layout works, or that stock workflows pass. This list remains open.

## Exact prerequisites

1. Complete the official DrRacket9.3 package transaction in the isolated profile.
   The first attempt was cancelled before committing installed packages. Sources
   cached before cancellation were only inspected; they were not used to bypass
   the cancelled install.
2. Use a permitted native graphical session. DISPLAY and WAYLAND_DISPLAY are
   absent. A separate normal-permission dummy-Xorg check could not create its
   local listening sockets, and no escalation/alternate display route was used.
3. On macOS, repeat with official stock9.3 on the same OS, display scale and
   settings as the supplied reference. Linux cannot pass the macOS gate.

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
