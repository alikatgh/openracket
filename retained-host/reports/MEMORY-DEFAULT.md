# Isolated preview memory-default implementation

Status: source/shell checks pass locally; real Racket/native Mac checks are
pending. This source is not a new native-accepted build. No UI, toolbar, tool,
evaluator, Run/Stop, lexer, autosave, or background-analysis implementation changed.

## Safety contract

- `setup-openracket.sh` calls the helper's internal `--reserve` before its first
  profile/package-directory creation. Atomic creation of a previously absent
  `profile/` establishes freshness. A pre-existing directory, even empty, is
  never fresh. The ordinary launchers never call the helper or set the key.
- The reservation records the absent preference-file snapshot: presence false,
  SHA-256 null, and an empty parsed snapshot. The allowed preference-store delta
  during package setup is empty. A newly appearing preference file (including an
  empty one) or an applicable legacy/config fallback preserves current behavior
  instead of applying the default. Invalid stores fail visibly.
- The random reservation token is passed directly through one setup invocation.
  It is not recovered from disk by repeated setup. Initialization moves its
  ownership state from pending to checking before source/API verification; a
  failure during that work cannot reuse the grant. Writing and restoring are
  distinct intermediate states, so an interrupted write is never guessed to
  have succeeded. If the filesystem itself refuses a state write, the command
  fails; repeated setup still treats the existing directory as existing.
- An automatically applied 256 MiB value becomes owned. An explicit initial
  `OPENRACKET_MEMORY_LIMIT_MIB` value becomes explicit, even if it is 256. Explicit
  `--set-mib`/`--unlimited` commands relinquish ownership before writing, including
  a same-value choice. `--restore` requires owned state, the known original 128,
  and persisted/effective 256. Divergent values are never overwritten by restore.
- Restore writes a single explicit 128 preference, not a global defaults reset
  or deletion of a preference file. It does not remove unrelated settings.
  Restored state is never automatically adopted again.
- All paths are bound to this source tree's `profile/`, with the exact isolated
  preference home/addon environment required. Ancestor/source-root aliases such
  as macOS `/var` → `/private/var` are normalized; symlinks at or below the profile
  boundary, including a preference file/parent or ownership file, are refused.
- A private file lock serializes helper operations. It does not block arbitrary
  GUI writes. Close all windows using the profile before setup/set/restore and
  restart after a change. A helper's independent API/disk readback is not evidence
  that an already-running GUI or evaluator has updated its cached value.
- The helper cannot identify a same-value GUI re-selection from disk equality.
  Restore is therefore an explicit user request for 128 when the current value
  still matches 256. The CLI's explicit setter records the user's choice even
  when the value remains 256, causing later restore to refuse.

## Original supported APIs

The helper pins Racket 9.3 and verifies both original source hashes before loading
the registered preference:

- `drracket/private/eval-helpers-and-pref-init.rkt`:
  `e32ed81fbbc6b85ce8149cbcf486c50321ece7fc3668931a394f36e91c401b62`
- `framework/preferences.rkt`:
  `59269376296892080cdbc7421e10015e99f8165d3a9c1051254ed7b81097af5c`

The original registration keeps 128 MiB and accepts `#f` (unlimited) or exact
integer bytes ≥ 8 MiB. The helper uses its original `preferences:get` and
`preferences:set`; it never registers an alternate default or calls a custodian
memory-limiting function. `racket/gui/dynamic` must report no initialized GUI
before and after loading/writing.

Only inside this short-lived helper, the documented
`preferences:low-level-put-preferences` parameter supplies an explicit isolated
filename to standard `put-preferences`. This retains the stock exclusive
read/merge/write lock and temporary-file/atomic-rename implementation. Independent
`get-preference` readback uses `#t` and that exact filename; a bounded parsed-store
comparison permits only the requested key change. No preference file is manually
rewritten by the helper.

Actual v9.3 implementation reference:
[racket/file.rkt, lines 919–1001](https://github.com/racket/racket/blob/v9.3/racket/collects/racket/file.rkt#L919-L1001)
(Git blob `ce2d90994ff94b364c91877773ea269ab86bc5b0`). The supplied filename is used
for the fresh read at 949, the key-only merge is 950–957, and atomic rename is 1000.
[Lines 793–827](https://github.com/racket/racket/blob/v9.3/racket/collects/racket/file.rkt#L793-L827)
show that an explicit filename bypasses legacy/config fallback. A historical
documentation sentence about a `defaults` collection is not the basis of this
implementation. The host process's preference functions are not parameterized.

## Verification

No installation or package download is performed by these checks:

```sh
python3 tests/portable-memory-profile-test.py -v
# Opt in only with an already available full official 9.3 runtime:
python3 tests/portable-memory-profile-test.py --racket "$RACKET" -v
```

The first command runs source-preservation, shell syntax and real-shell mocked
orchestration tests. Native tests require the second command and otherwise report
an explicit skip. They cover fresh 256, fresh 128/custom/explicit 256, existing
empty/no-key/custom/unlimited profiles, setup interruption, token consumption on
initialization failure, restore and subsequent setup, unrelated-key preservation,
divergent/missing values, same-value explicit choices, exact environment checks,
source-root aliases versus descendant links, stock write-lock failure, headless
loading, the shell wrapper, and separate stock preference behavior.

Actual native acceptance must additionally run the real setup, launch and
in-process read-only observer against the final source. It must observe fresh 256,
explicit 128/custom/unlimited preservation, restored 128 and separate stock
fallback; check the original runtime snapshot remains unchanged; and retain the
existing UI/tool/semantic gates. Observer readback verifies the real registered
preference in the launched GUI, not a newly invented whole-app RAM cap or direct
measurement of worker memory. Existing long analysis/editing latency remains
unresolved. Keep DELIVERED-BASE-CONTENTS.json as comparison evidence, not as a new
manifest of this candidate.
