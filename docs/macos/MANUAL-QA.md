# macOS release checks still required

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

Full DrRacket compatibility remains outside this frozen core: teaching-language tooling,
Check Syntax, debugger, macro stepper, WXME/snips and plugin integration are not included.
