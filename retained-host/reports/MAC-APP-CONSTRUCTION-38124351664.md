# Racket-only Mac app construction: native build passed, launch pending

[Mac run 38124351664](https://github.com/alikatgh/openracket/actions/runs/38124351664), commit `a304077a884fa01f0a9f211e8c96d77e2bc6ee9b`, generated the destination-built OpenRacket bundle using full official Racket 9.3 on Apple Silicon. It remains tethered to that installation and the separately prepared preview source/profile. A runner-local bundle is not a portable download for another Mac.

## Passed

- Actual preview setup and preflight, including the fresh isolated 256 MiB preference.
- All 20 Racket builder cases and 21 observer contract/state cases; the independent corrected heartbeat passed 16 native cases.
- Official native launcher generation and Racket-only decoration with Unicode, apostrophes and spaces in paths; plist/executable and existing-output refusal gates.
- The generated arm64 native executable contains 54,257,519 bytes, SHA256 `acabdbb0f41782c8014cb903caef04b22581e99891f946ed312b7790167b9083`. Its name and bytes survived decoration; an independently generated official reference happened to have the same digest.
- Both complete original/selected runtime witnesses, 26,838 entries each, retained exact bytes, modes, modification times and links. Original user preferences were unchanged. The preferred `.rkt` UTI and its null default handler were unchanged.

## Failed prerequisite and bounded repair

The CI observer package link was installed, but its following setup invocation could not resolve the user-linked collection. The CI prefix used `-U`, which disables user-specific collection search even when `-A` selects the intended private addon directory. The previously proven portable observer registration uses explicit private `-A`/`-R` without `-U`.

The frozen CI-observer README inherited the same incorrect registration recipe; this report records the correction without rewriting that historical freeze. The reviewed correction changes only the CI registration/setup prefix. Builder/headless isolation, all product/observer bytes and private profile/runtime boundaries remain intact. Native launch acceptance is still required. No Launch Services process or file-event case ran in this failed job.

## Signature and delivery limits

Whole-bundle `codesign` inspection and verification returned exit 1 with “code object is not signed at all.” Gatekeeper assessment returned exit 3 with “rejected” and “source=no usable signature.” Those are retained failures/observations, not a signed or notarized app claim. No security policy or quarantine setting was changed. No launch warning was bypassed.

Real bundle/PID identity, cold/warm file events, app-only relocation, Dock/Finder behavior and further lifecycle/product acceptance remain pending. The source preview is still the user-facing tested baseline; this construction result does not establish a normal launchable, self-contained or signed app, nor a performance improvement.

## Pins

- Raw native log: `bc5748a786b03e6b466e72ef724899a63e2a640df77b3acacdec9c48d247f3fb`
- Builder manifest: `db7b3e766da0532630237e8dd3bc42fb6eab9d7130753a69a17e70faf0574f67`
- Observer manifest: `ba3741d74751421427ae4772fdfe86fb8948cb36437e565b08549c144a02a1ce`
- Preview source manifest: `2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552`
- Both runtime byte/mode/mtime tree digests: `32314105d49bee5f4d24d068782a5299f5865e729dd4da5f39f81e905276d16e`

Artifact count was zero. This report was prepared from the terminal native log and summary; no frozen source or evidence was changed.
