# Fresh-profile capacity candidate: integration review

This candidate starts from the exact delivered 146-file Mac source archive, SHA-256 `d6b524955cd3c0a7fb181a1fa55c6f6b443bf4d5b78d30ad103e580374656ace`. The original delivery is unchanged.

The new setup helper uses the stock registered `drracket:child-only-memory-limit` preference. Automatic 256 MiB requires an entirely absent profile atomically created during this setup invocation and an unchanged absent preference store. Existing profiles and explicit choices are preserved. Launchers and proof-env remain byte-identical. Guarded restore writes explicit 128 MiB only for a still-owned automatic default. Close the profile's windows before explicit changes.

All delivered `src/`, `overlay/`, `tool/`, `vendor/` and `performance/` files remain byte-identical. No evaluator, stock limit enforcement, tool protocol or lexer budget changes. The read-only portable observer adds exact GUI preference assertions while retaining every original source line and the original capture handshake.

Independent local review covered state transitions, one-key supported persistence, source pins, root-alias/descendant-link handling, explicit choice/restore boundaries and the whole-store readback. Nine source/real-shell orchestration checks and four existing mocked dependency checks pass; shell/Python syntax checks pass. The old dependency suite's separate actual-Racket case cannot execute here because its default runtime path is absent. Eighteen new native helper cases and 15 Racket observer contracts are prepared but unrun locally. Racket compilation and real Mac setup/launch/effective-value/restore/runtime-immutability acceptance remain required.

The included memory report is independently reviewed and its five analyzer tests pass. 256 MiB completed this tested 1 MiB file's analysis 3/3 times; 128 failed 3/3. This is a capacity change. Successful analysis still took 33–39 seconds; no responsiveness improvement is claimed.

## First native attempt and targeted repair

[Run 38110208795](https://github.com/alikatgh/openracket/actions/runs/38110208795), commit `e6702fa92d4a82ed0120233c8b775d8507739656`, compiled the new helper and passed the pre-existing profile/dependency/source checks. Its helper suite then rejected the exact profile boundary before setup. Both original runtime trees remained unchanged. Log SHA-256: `0cac5c5fe38a5352042c44584fa116bbbc4cab05c7b8313bd2152c424b89d2f7`.

The exact Racket 9.3 path contract explains the failure: find-relative-path returns an absolute path for identical inputs unless #:more-than-same? is false. The repaired guard specifies that keyword; split-path now retains directory-valued alias names. Parent, sibling and descendant-link refusal remains strict. Ten local checks pass; 20 native helper cases await rerun. Their direct path unit gate now runs first through raco test with its cache outside the not-yet-created profile. No policy, UI, evaluator, limit enforcement or launcher changed.
