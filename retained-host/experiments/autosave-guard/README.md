# Opt-in stock autosave format-scan experiment

This isolated Racket 9.3 candidate has not been installed or run natively. It
has no measured benefit. It is separate from the retained appearance, snip-scan
and coloring-budget experiments, and must stay disabled by default.

## Exact change

Framework's `clever-file-format-mixin` performs a private full string-snip scan
at the beginning of `can-save-file?` and `on-save-file`, then checks whether the
requested file format is `same`. For other formats the scan cannot affect its
format-conversion decision. The candidate adds a default-off guard before each
scan. Enabled with `OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD=1`, the guards skip
those two scans when the format is not `same`. Existing predicate expressions,
conversion prompts, file-format setters, inner hooks and return paths are kept
in their original order. `same` requests still follow the complete stock path.

The module exports its read-only activation value
`openracket-experimental-save-scan-guard?` so a future native test can verify what
was actually loaded. No cache, replacement save function, worker, new file
format, shortened autosave interval or disabled tool is introduced.

## Required autosave work remains

The original `editor-misc.rkt` autosave implementation performs its own required
scan to choose a safe saved format, then calls `(save-file auto-name 'copy #f)`.
That scan and save call remain byte-for-byte unchanged. So do the native editor's
save hooks, which receive the requested `copy` format. The candidate removes
only the two later format-conversion scans; it does not skip serialization,
rich-snip handling, write completion, recovery metadata or error handling.

Exact source copies and their hashes are in `vendor/` and
`reports/required-stock-save-sources.json`. The sole overlay is
`framework/private/text-misc.rkt`. Source and license provenance come from the
official Racket 9.3 gui-lib release package.

## Extension behavior boundary

The private scan calls virtual `find-first-snip` and each string snip's virtual
`next`. Stock built-in methods read fields, but an extension can override them
with visible side effects or exceptions. When enabled, the candidate deliberately
changes those scan callback counts for non-`same` formats. It therefore does not
claim identical arbitrary third-party callback behavior. The independent test
canary must expose that difference. Default-off and `same` requests preserve the
original scan sequence.

This boundary is not permission to remove save hooks or change stock rich-data
behavior. All built-in save, autosave and recovery outcomes must remain equal.

## Local checks

Run `python3 scripts/prepare-autosave.py`, then
`python3 -m unittest discover -s tests -p test_source.py`. The generator checks
raw upstream bytes and never installs or accesses the network. The five source
tests verify exact two-guard/config/export scope, deterministic output, CRLF and
content-tamper refusal, and unchanged required autosave/native save sources.
Independent parsed-source behavior tests under `tests/independent-*` pass 11
groups, including 3,456 ordinary format scenarios, 48 executions of parsed stock
autosave logic and 36 injected write failures. The explicit extension canary
records the changed callback counts and exceptions. Headless model checks do
not establish native editor/file-system parity. The native save/WXME/artifact
reload fixture is reader-checked only; real dialogs and crash/restart recovery
remain separate unrun gates.

## Native and measurement prerequisites

Use fresh deep copies of the checksum-pinned full official 9.3 runtime, with
only this overlay in the candidate. Keep the scan and coloring-budget experiments
off and appearance/settings identical. Verify source hashes and loaded activation
in every process. Test at least:

- Unmodified, empty and large Unicode text; exact saved and reloaded contents
- Rich WXME containing image, nested editor and custom snips, including recovery
- Explicit `same`, `copy`, `standard` and text save requests with stock dialogs
- Inner save-hook acceptance and rejection, and successful/failed writes
- Real `do-autosave` generation, fresh-editor recovery and saved format selection
- Default-off equivalence and the documented extension side-effect canary

Only after those gates pass, compare actual autosave elapsed/GUI heartbeat
latency, scan counts, file size, exact recovered source/payloads and allocation
in fresh matched processes. Keep the required scan and real disk write in both
arms. This is an autosave experiment, not a proposed explanation or fix for the
measured initial-coloring GC stalls. Do not enable it by default without a
measured benefit and the stock save/recovery gates.

## Coherent native candidate

This snapshot includes the independently reviewed genuine-host native caller and
actual-autosave benchmark. The caller runs stock, candidate-off and candidate-on
in fresh profiles, verifies source hashes and actual activation, and exercises
stock-default Unicode/WXME/save hooks, write-failure retry, recovery metadata and
fresh-editor artifact reload. It never changes stock preferences.

See `reports/INDEPENDENT-QA.md` for native invocation, compile requirements and
remaining verification-enabled dialog/crash-restart gaps. See
`reports/PERFORMANCE-WORKLOAD.md` for the matched stock/candidate measurement
contract, actual-new-artifact witness, pre-save state caveat and timing scope.
Native correctness must pass before timings; neither is claimed locally.
The 8 ms color-budget experiment is excluded and the stock 20 ms budget stays.
