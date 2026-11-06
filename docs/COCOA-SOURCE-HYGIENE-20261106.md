# Cocoa source hygiene and compile-first gaps — 2026-11-06

Scope: local source and documentation review of `cocoa-native-ci/`. No app build,
runtime installation, native launch, CI activation or remote Git action was run.
The retained-DrRacket host's historical results do not validate this Cocoa package.

## Source admission result

The checked-in package passes read-only admission through the adapter's new
`validate-package` mode:

| Input | Verified result |
| --- | --- |
| `PUBLIC-SOURCE.json` | Exact adapter SHA-256 pin, public schema, sorted safe unique paths, read-only modes, sizes and hashes for 1,159 members |
| `SOURCE-BUNDLE.json` | Exact pin, schema/format and integer accounting; 20,551,193 raw file bytes |
| `SOURCE-PARTS.json` and `source-parts/` | Exact descriptor pin, nine ordered regular parts, directory closure and each part's size/SHA-256 |
| Joined envelope | 4,689,100 bytes; SHA-256 `e9ee1056763f8e0b946d3a4e065b8136c4b1f445b2eed0e8342aa4896330b05d` |
| Decoded frame | One bounded XZ stream, exact embedded manifest and payload closure, every decoded member's SHA-256 |

No members were extracted or executed. `PUBLIC-SOURCE.json`, source parts and
their hash pins remain unchanged: review found no mismatch requiring repackaging.
The bundle descriptor's schema/format and accounting types are now checked
explicitly, including for future reviewed descriptor changes with updated pins.

The existing [`source_bundle.py`](../cocoa-native-ci/adapter/source_bundle.py)
implements this package's custom, pinned framing. Reusing its validator for both
extraction and in-memory checks avoids a second decoder or new dependency.
[`run_native_ci.py`](../cocoa-native-ci/adapter/run_native_ci.py) exposes the
check without entering native setup. The README now distinguishes the checked-in
runtime installation script from the installer it downloads, and describes the
actual workflow location and its external package dependency.

## Reproduce without compiling

Run from the repository root with Python 3.11+ and standard-library XZ support:

```sh
python3 -B cocoa-native-ci/adapter/run_native_ci.py validate-package
python3 -B -m unittest discover -s cocoa-native-ci/adapter -p 'test_source_hygiene.py' -v
git diff --check
```

All passed locally with Python 3.14.4. The focused suite has 16 tests covering
the real checked-in package, descriptor pin/schema/accounting rejection,
part tampering/order/closure/symlinks, invalid paths/modes/hashes, payload
corruption, decode bounds, truncated/concatenated/trailing streams, and refusal
before extraction writes. Fixtures stay in memory; `-B` suppresses bytecode.

The existing `validate-projection` mode expects a materialized source tree.
[`test_adapter.py`](../cocoa-native-ci/adapter/test_adapter.py) likewise resolves
`cocoa-native-ci/source` (or `OPENRACKET_ADAPTER_TEST_SOURCE`) during import and
creates temporary fixtures. That broader suite was **not run** under this task's
no-deletes/no-build restrictions. Passing the new suite does not replace it.

An independent read-only review reran package admission, all 16 focused tests
and the whitespace check, with no supported defects found. Successful on-disk
extraction and Python 3.11 execution were not tested; local execution used 3.14.4.

## Remaining compile-first CI gaps

These are source-level requirements and missing evidence, not observed native
failures. The workflow and native supervisor/bootstrap behavior were left intact.

| Gap | Current source evidence | Required next evidence or repair |
| --- | --- | --- |
| Exact runner/toolchain compatibility | [Workflow](../.github/workflows/cocoa-native.yml) selects `macos-15`; [runner reference](../cocoa-native-ci/RUNNER-REFERENCE.json) documents a historical `macos-15-arm64` image. The pinned [runtime script](../retained-host/scripts/ci/install-full-racket.sh) supports Darwin/arm64 only. Python 3.13+ process APIs and physical Xcode 16.4/SDK paths are required by native setup. | Verify the intended runner's actual architecture and installed tools, and reconcile labels/reference before an authorized run. No current hosted-runner facts were queried here. |
| Bootstrap process cleanup edge cases | [`bootstrap.py`](../cocoa-native-ci/adapter/bootstrap.py), `anchored_signal()`, still calls `getsid()` directly and propagates group-signal rejection. Cleanup after successful compilation can enter this path when its inventory scan is inconclusive or descendants remain. Existing bootstrap tests mock successful session lookup/signaling. | Add focused tests for an owned unreaped Darwin zombie's session lookup failure and rejected signals with/without proved quiescence; establish safe cleanup without weakening ownership. The packaged supervisor's separate recovery fixes do not cover bootstrap automatically. |
| Runtime clone after the full gate | `run()` checks clone equality at creation and after diagnostic smoke. The full mandatory gate then reuses it. `witness()` checks the original runtime, immutable source and workcopy source bytes, but omits the clone after that gate. | Add a post-gate clone witness and a mutation regression test. No clone mutation was observed; its final immutability is currently unproved. |
| Broader adapter verification | The read-only suite works from a fresh checkout. The existing adapter suite needs materialized source; native prerequisites additionally require the compiled inventory helper and Darwin. | Run the broader suite in an authorized writable test context. Obtain receipts for helper bootstrap and all three required Darwin native tests, with no native skips. |
| Compilation and mandatory acceptance | `run()` intends offline locked Rust compilation, Scintilla/Cocoa compilation, limited app smoke, and the unchanged mandatory native gate in fresh workcopies. Vendored Rust sources and Cargo source replacement are packaged inputs, not compilation proof. | An authorized native run must produce actual compiler/SDK/Rust/runtime identities, build and smoke receipts, app hashes, full-gate marker, final witnesses and complete evidence transport. No such result was produced by this task. |
| Observed native usability | README and workflow explicitly defer screenshots, VoiceOver, system IME, performance and DrRacket parity; smoke covers a limited workflow. | Inspect rendered screenshots and test the remaining real native journeys separately. Green builds or automated smoke alone cannot close these items. |

Any future cloud activation remains subject to the existing account, included
capacity and provider-enforced spend checks. This task authorizes no such run.

## Local storage and delivery

Session `01a1b037-20aa-7f30-b11c-ff6fee46652b` started with approximately 4.66 GiB
free, above the 1.5 GiB stop floor. Checks allocate only bounded in-memory data;
no scratch directory, bytecode cache, build output or download was created.
Retained deliverables are the README, adapter source/tests and this note, plus
the requested local Git commit. No cleanup deletion is needed or authorized.
A pre-commit storage check measured approximately 6.69 GiB free. The free-space
change is volume-wide and is not attributed to this task.
