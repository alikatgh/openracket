# Native Mac app launch acceptance, 11 October 2026

The destination-built OpenRacket app passed all **114 app orchestration records** in [run 38127332821](https://github.com/alikatgh/openracket/actions/runs/38127332821), commit `dae4b69d34a793404f1e8ddf35a65948d33ae980`, on the standard Apple Silicon macOS 15 runner with full official Racket 9.3. These are app acceptance results, not a new performance measurement or complete DrRacket parity claim.

The overall job is red: a separate stock-tool negative-control driver correctly exited 1, but its default exception renderer omitted the actual/expected details required by that gate. Both positive drivers passed. The six full Debugger, Macro Stepper and teaching workflow cases were skipped and remain unverified. This does not invalidate the independently collected app results.

## Accepted native work

- Actual isolated source setup, 20 native Racket builder cases, 32 native observer contract cases, and the separate 16-case corrected heartbeat regression passed.
- The Racket-only builder invoked the official native launcher generator. The bundle omitted `CFBundleDocumentTypes`, preserved the generated native executable's bytes, and refused existing output paths. Its 54,257,519-byte arm64 native executable had SHA-256 `acabdbb0f41782c8014cb903caef04b22581e99891f946ed312b7790167b9083`.
- Ordinary `/usr/bin/open -a` launched the real app. Nine native states passed across three sequences: cold empty → warm file → duplicate; cold file → second warm file → duplicate; and the same file sequence after moving only the app bundle. Unicode, apostrophes and spaces occurred in source, bundle and file paths.
- The observer verified the actual process/native executable/Cocoa bundle identity, isolated profile and loaded preview source, effective 256 MiB preference, native dark appearance, original editor/control identities, exact file contents, retained tab identities and same process within each sequence. This app gate did not independently measure the background worker's cap; the separate nine-trial memory matrix did.
- Cold empty “No language chosen” correctly had the stock Run/Stop toolbar. Real `#lang racket` file states required the full language-appropriate ordered tools. Duplicate opens preserved the observed tabs; this proves the visible state, not receipt of every possible duplicate event.
- Three bounded observer cleanups confirmed the processes were gone. They do not establish normal Quit or unsaved-document prompt behavior.
- Both complete official-runtime witnesses remained unchanged: 26,838 entries, including bytes, modes, modification times and symlink targets. The selected-runtime witness SHA-256 was `32314105d49bee5f4d24d068782a5299f5865e729dd4da5f39f81e905276d16e`. Original Racket preferences were unchanged.

## File associations and security

The runner began with UTI `org.racket-lang.source` and `.rkt` handler `com.apple.ScriptEditor2`. Read-only checks before building, after generation, each actual dispatch and stable observation, each cleanup and the final witness all preserved that association.

The previous failure had begun with no preferred handler. **This run did not reproduce an unset-handler baseline.** The source now omits automatic document-type claims, but native preservation of an initially unset handler remains an open case. No default setter or association reset was used to manufacture a pass.

The built app was unsigned with no usable signature; no Developer ID or notarization is claimed. Ordinary locally generated launch succeeded without dismissing a security warning or changing OS security. Downloaded/transferred-app Gatekeeper behavior remains unverified. A launch warning must be reported, not bypassed.

## Delivered source and prerequisites

The package contains the unchanged, previously delivered source preview and the exact tested Racket-only builder. Build on the destination Mac using a full official [Racket 9.3 installation](https://download.racket-lang.org/releases/9.3/). Python is not a product prerequisite. The resulting app is tethered to that installation and the separately prepared source/profile. Moving the app alone passed; moving its dependencies requires a rebuild.

No CI-path-dependent app binary is delivered. Self-contained distribution, signing/notarization, automatic Open With listings, Finder/Dock gestures, normal Quit and failure UX, and Intel Mac/Windows/Linux acceptance remain separate unfinished work.

The core still provides the measured autosave improvement and a 256 MiB default only for entirely fresh isolated profiles. Existing limits are preserved. The memory change is a capacity improvement; large-file coloring/analysis stalls remain. Experimental performance changes are disabled.

## Source and evidence integrity

- Core `CONTENTS-SHA256.json`: `2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552`, 155 manifest members plus manifest.
- Builder `CANDIDATE-SHA256.json`: `b4e5638c409b018a8dec030ea7dafb60291bfffc2645a5d087d7e91d4cfd77ee`, 14 members plus manifest.
- Read-only CI observer manifest: `3a4d1cdabbdbbcce4ecdcf40132748db168fc6515479112036c24df78aabb2e1`. The observer is not installed by this delivery.
- Full native log: `2fd65a4bd56ddcd3d23e2f83b4496bd6883c9ec15c9fbc32f71b2eaacf2fbd83`.
- Included final relocated-app screenshot: `60b8f80c2810d30bd86be386c9b6afdee8bde88378a20a68a6cdcd0e638fe7f9`, 1024×768. Independently inspected: genuine dark OpenRacket, two correctly named Unicode tabs, full language-appropriate toolbar, no modal dialog.

The `evidence/` folder contains the exact run summary, generated-app summary, three sequence acceptance records, final native READY record, image index and selected screenshot. Internal source reports retain their original historical wording; this report records the later native outcome without changing tested code.
