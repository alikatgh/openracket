# Narrow source review

Status: local-only source and portable Python checks. No native compilation,
Racket/GUI execution, archive retrieval, package installation, CI or publication.
No delivered preview or other freeze was changed.

## Unchanged provenance

The accepted host SHA256 is
`5d3fec70cb1ccae6ac91ea7ef2dc382011e7c173a2a8d34a51e6e01dad5fd448`.
The unchanged Check Syntax workflow SHA256 is
`b175a92754e8f0e8a0f524ae5947f5eae8da605b0f3274bbc098e20ce1de53bf`.
`PROVENANCE.json` contains all 21 unchanged source associations and their exact
SHA256 values, including all six required local tool dependencies and the full
original trace subtree. The actual native files remain in their original relative
layout; there is no dependency on a missing external tool tree.

## Added boundary

1. `native/bootstrap.rkt` verifies resolved executable/module containment, exact
   Racket 9.3 and source pins, original helper bytes, exact stock/off/on flags and
   exports, then source-loads the actual style module and invokes the unchanged
   accepted host. The wrapper is not a GUI observer. It does not call diagnostic
   state, named lookup, constructors, bindings getters or navigation.
2. `scripts/run_native.py` supplies fresh process/profile evidence, three ordinary
   host arms and four actual stock-xref handler/rename arms. A failed earlier arm
   does not prevent later collection. Timeout, absent/incomplete capture, launch
   failure, source mismatch or comparison failure blocks acceptance. Native
   execution remains an explicit future command; import and portable tests do
   not start a native process.
3. `scripts/compare_controls.py` checks one exact original graph line and ordinary
   host result/READY. All integers are exact Python ints, excluding bool/float;
   all eight edges and four zero spans are fixed. Host checks must be positive
   exact integers. Original false broad-parity/physical-timing scope fields must
   remain false. The same-editor filtering and duplicate removal of the accepted
   workflow are explicitly disclosed; no complete-table/getter claim is added.
4. Screenshot evidence requires actual exit0 and retained bounded PNG bytes with
   signature, structural chunk/CRC, positive dimensions and SHA256 checks. This
   verifies captured evidence, not pixel equivalence. Capture timeout is bounded
   by both 15 seconds and the remaining 60-second host deadline; completion at or
   after that deadline fails even if process exit is otherwise successful.
5. The named-style trace comparator is generated solely by the nine explicit
   external-label string substitutions in its separate generator. Reversing
   these substitutions reproduces the accepted comparator exactly. Semantic
   functions/validator are imported unchanged, and every inherited mutation test
   remains. No raw capture is rewritten and all four callers use `--mode stock`.

## Reviewable deltas

- `reports/external-labels.diff`: full comparator derivative against unchanged
  accepted source.
- `reports/new-controls.diff`: complete new wrapper, runner, comparator, generator
  and regression-test source as additions. Unchanged source copies are separately
  byte-pinned by `PROVENANCE.json` rather than repeated as an apparent code change.
- `reports/portable-*.log`: complete portable outcomes. These are synthetic/source
  tests, not evidence that a GUI, Racket module or native assertion has run.

## Remaining native requirements

The future outer matrix must verify pristine installation before/after, prepare
independent source-verified runtimes and isolated compiled caches, compile the
actual source plus every local native/runtime-path dependency, and authorize
native execution. The existing real-editor/WXME gate and full telemetry remain
independent requirements. Neither workload is duplicated or weakened here.
