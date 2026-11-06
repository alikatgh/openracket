# macOS prototype status and remaining release checks

Status on 2026-11-06: the newest public engineering branch is
`prototype/retained-drracket` at `0aa912f` (2026-10-22). `main` is the older
`64c0f45` tip (2026-10-11), a documentation/website update. No October 27–30
engineering work is present in the recovered repository history.
**There is no notarized macOS app.** See the
[repository overview](../../README.md#repository-and-macos-status--2026-11-06)
for the separate Rust/Iced, retained-DrRacket and Cocoa tracks.

## Open retained-DrRacket blockers

- Stock Stop completion timeouts remain unresolved. Later strict Stop tests
  passed both Mac arms, but intermittent completion and full parity remain open.
- Large-file readiness and analysis stalls remain unresolved. The tested 1 MiB
  workload completed at 256 MiB after failing at 128 MiB, still taking about
  33–39 seconds; this capacity improvement does not establish responsive editing.

The [earlier status snapshot](../../retained-host/reports/status.json) records
macOS core passes alongside these failures. See the
[later evidence summary](../RECOVERY-AND-GAP-2026-11-06.md#open-blockers-with-the-age-of-the-evidence-preserved)
for the scope of subsequent results. Those historical results are not fresh
validation of this checkout or a complete release pass.

## Historical Rust/Iced preview checklist

The checklist below belongs to the original Rust preview. It is not a list of
missing features in the retained DrRacket host, nor evidence of an existing ZIP.

Do not mark these passed from a headless test, offscreen screenshot or a running process alone.
Do not grant Accessibility, Automation, screen-recording, camera, microphone or other TCC
permissions or change Gatekeeper/quarantine settings to get a pass.

- Download the exact ZIP, verify SHA-256, unpack, inspect its signature and try a normal Finder launch. If blocked, record the exact warning and stop that launch path. Ad-hoc signing is not notarization.
- Install official Racket 9.3 CS for Apple Silicon separately. Verify normal Finder launch discovers the conventional installation without relying on the CI environment.
- Confirm Definitions above Interactions, readable fonts, dark/light theme, HiDPI layout, window resize and the split handle.
- Open a trusted UTF-8 file using the native picker; open a second tab, edit, Save and Save As. Exercise Cancel and dirty-close Save/Discard/Cancel. Verify external-change protection.
- Test Cmd+N/O/S/W, Cmd+Shift+S, Cmd+R/F5, Cmd+., Cmd+Z/Shift+Cmd+Z, Cmd+F, Cmd+B and focus-sensitive clipboard/navigation.
- Run unsaved definitions, relative imports, fractions, Unicode, multiple values, multiline input, errors with locations, stdin/EOF, repeated Run, Break and Force stop. Editing must remain responsive under output floods.
- Test switching tabs with a live runtime, native window close with unsaved work, dialogs dismissed with Escape/Cancel, and repeated commands.
- Verify clipboard round trips, IME/dead keys, VoiceOver, scrolling, focus return from dialogs, app switching, Dock label and About/menu behavior.
- Document Finder file-open events and file associations as unsupported until explicitly implemented and verified. The preview does not register .rkt as a document type.
- Check first-launch and reopened launch on a clean macOS 15 Apple Silicon account. Do not claim Intel or earlier macOS support from this build.
- Record observed launch time, editing delay and memory with reproducible workloads before making performance claims. CI rendering benchmarks alone do not establish perceived UI speed.

Full DrRacket compatibility remains outside this Rust/Iced core: teaching-language tooling,
Check Syntax, debugger, macro stepper, WXME/snips and plugin integration are not included.
