# macOS source installation and launcher acceptance

The actual portable setup and launcher gates passed on macOS 15 / Apple Silicon
using the full official Racket 9.3 distribution. This is an early runnable source
preview. It is not complete stock parity, a signed application, or a general
large-file responsiveness solution.

## Exact source and evidence

- Repository commit: `08442fd523fbdfaf1f00c7e8ec97d524984aea66`.
- [Native run 38064415026](https://github.com/alikatgh/openracket/actions/runs/38064415026).
- Tested portable snapshot: installer1531, 146 files.
- Source ZIP SHA256: `d6b524955cd3c0a7fb181a1fa55c6f6b443bf4d5b78d30ad103e580374656ace`.
- Inner `CONTENTS-SHA256.json` SHA256: `f47c9ca4cab3e06ccd0985f6bdeace32cafef0964212cc3617c1a1ec3024f57c`.
- Native job log SHA256: `1d4ab1bde98b4e8e6f142549f8aab8c16ecfcb0c673b5e404d559f2f52f8bb05`.
- Official prerequisite: [full Racket 9.3](https://download.racket-lang.org/releases/9.3/).

The overall job is red solely because a separate expansion-diagnostic mock test
compared two equivalent macOS temporary-directory spellings as strings. Every
installation, launcher, combined save/recovery and runtime-immutability gate
passed. Actual expansion capture/replay did not run in this job.

## What ran

The manifest-verified source was copied into a fresh directory named
`OpenRacket Portable Proof`, deliberately containing spaces. A separately copied
full official runtime was used for the install route. The real
`setup-openracket.sh --install` and `launch-openracket.sh --check` succeeded.
The setup reused accessible installation-scope dependencies, copied `gui-lib`
into the proof-local user profile, applied exact pinned overlays there, and
compiled with a profile-first cache. Resolution checks confirmed the intended
GUI copy, unchanged stock DrRacket unit and real appearance tool.

A CI-only, read-only observer package then watched the actual launcher-created
frame. It did not replace the entrypoint, open files, edit the document or change
preferences. Three fresh launcher processes passed:

- Default modern: 30 assertions; loaded autosave guard true; actual Cocoa explicit
  and effective DarkAqua; matching dark painter.
- Modern autosave opt-out: 30 assertions; loaded guard false; native dark unchanged.
- Stock comparison launcher: 25 assertions; guard false, original toolbar mode,
  native explicit appearance absent and effective Aqua.

Each observed the exact Unicode argv-opened filename and 63-character contents,
original registered editor/canvas classes, and the original horizontal toolbar
order: Check Syntax, Debug, Macro Stepper, Run, Stop. The native screenshot size
was 1024 by 768; the actual initial frame was 600 by 634 and retained stock compact
label adaptation. These observations are startup checks, not execution coverage
for every toolbar tool.

Two separate fresh-preferences callers exercised the installed combined modern
host with the guard enabled and disabled. Each passed 38 assertions covering
stock-default plain/rich save/copy, WXME, actual autosave recovery artifact reload,
and four real filesystem write-failure/retry cases. Verification-enabled format
conversion dialogs and crash/restart recovery UI remain unrun.

## Runtime isolation

The complete pristine and selected-runtime trees were hashed before setup and
compared after setup, launch and all subsequent work. Each contained 26,838 entries,
including regular-file bytes, compiled bytecode, directory/file modes and symlink
targets. Both stayed exactly unchanged:

`adaa2ac60b579a3219f189f1c8e56bc3f2ebb61913cfd62ea4cc692cbf427a60`

Preferences, user packages and rebuilt bytecode stayed in the writable proof
profile. No installed runtime mutation was needed.

## Genuine native image identities

- Default modern: `5b3d8eda819b8073d2b63576434ca60e9c78362c84925a685ad21a9b735ee5f2`.
- Modern opt-out: `38308f523e207c9280ecf8513fd82f1bbc37a810a03d25e23a5c1c5b918e5f3c`.
- Stock launcher: `738ac3fdd6cc0238e58868a044bc16182551295390d5ad60f318607744d2f113`.

## Performance and limits

The included autosave guard is the exact source measured separately in
[run 38061486888](https://github.com/alikatgh/openracket/actions/runs/38061486888).
Three matched Mac replacement-save pairs reduced median-arm command time from
267 ms to 172 ms (35.4%); median paired reduction was 24.6%. The direct queued GUI
probe agreed. Combined modern-build performance was not separately timed in this
installation run. The guard can reduce traversal callback counts for third-party
extensions on non-same-format saves; the documented opt-out restores the original
path.

Stock 20 ms lexer scheduling is retained. No scan fast-path or smaller-budget
experiment is enabled. Initial large-file coloring still takes tens of seconds
with multisecond UI stalls. Intermittent Stop delivery, broad Debug/Macro Stepper/
teaching acceptance, extension compatibility, IME/accessibility and crash/restart
recovery remain open. Intel Mac, Windows and Linux portable installation have not
been verified by this Mac-first gate. Source-level cross-platform structure alone
is not native platform acceptance.
