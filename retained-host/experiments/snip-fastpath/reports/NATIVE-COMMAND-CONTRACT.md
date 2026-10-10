# Scan-only native correctness contract

This source is separate from appearance changes. Start from full checksum-pinned
official Racket 9.3 and a fresh, deep-copied disposable candidate runtime.
No hardlinks or escaping symlinks may connect it to the pristine source runtime.
Use fresh, separate preferences/addon directories for each process.

## Install into the copied candidate only

Resolve the actual collection files with that arm's Racket executable. Verify
Framework text-misc and DrRacket unit hashes against fastpath-manifest.json.
Verify the generated helper/unit bytes against that manifest before installing.
Copy the helper to drracket/private/openracket-all-string-snips.rkt first, then
the patched unit.rkt to the resolved drracket/private/unit.rkt path. No Framework
file, appearance tool, toolbar patch, color-budget change or setting is added.

The read-only scripts/verify-installed-candidate.py accepts --root, --unit,
--framework, --helper and --mode stock|candidate. It refuses mismatched source,
paths outside the selected arm and symlinked source files. The pristine arm must
have no candidate helper. Verify both arms before/after tests. Native activation
is a separate assertion, not implied by these file hashes.

Compile the actual candidate helper and unit module, the complete DrRacket
entrypoint, and tests/independent-native-fastpath-test.rkt. Run the latter with
OPENRACKET_ALL_STRING_FAST_PATH=1 and a 60-second process bound. It asserts the
private module selection and real public interface, then compares 15 native
editor cases. Do not treat a compile error or a stock-only run as a pass.

## Retained-editor lexer equivalence

Run tests/native-lexer-equivalence.rkt once in each arm, 60-second process bound:

OPENRACKET_LEXER_OUTPUT=/absolute/result.json
OPENRACKET_LEXER_MODE=stock-or-candidate-label

The stock arm must have OPENRACKET_ALL_STRING_FAST_PATH unset; the candidate arm
must set it to 1. Keep OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS unset in both.
All appearance variables and initial preferences must be identical; preferably
leave the appearance environment unset in both arms. The fixture is built in,
so pass no command-line arguments. The actual shown DrRacket definitions editor
is used. Every edit waits for fresh stable lexer validity and snapshots every
position's token class/range, parenthesis graph and resolved style spans. A
separate Framework stateful lexer checks don't-stop continuity.

Compare the two complete JSONs with tests/compare-native-lexer.py. It rejects
partial cases, unequal appearance/preferences, dont-stop violations or any
text/token/paren/style difference. Full records are also emitted between
OPENRACKET_LEXER_CASE_JSON_BEGIN/END markers; summary markers are separate.

Correctness must pass before fresh paired timing. Timing uses the same common
harness/settings in both arms and independently logs actual activation. This
experiment does not establish general plugin compatibility, speed or latency
from source review alone. Preserve original runtime hashes throughout.
