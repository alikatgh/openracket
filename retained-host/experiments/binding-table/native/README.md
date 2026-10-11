# Native binding graph and arrow navigation gate

Source-only preparation; no new native result is claimed. This gate supplements the candidate's actual-form differential tests and the existing worker annotation/rename comparator. A worker-only trace does not exercise the changed GUI consumer.

The host differs from the exact delivered 0520 host only by a runtime-path import and postflight after the unchanged genuine Check Syntax case. Its fixture runs through the real Run and Check Syntax controls. The stock Check Syntax button is disabled during traversal and re-enabled by cleanup after queued expansion/traversal work; the original workflow polls its enabled state before its first public binding-table query. That query must materialize an enabled candidate, and the later witness must prove real same-owner accepted entries, one public exposure, no unsupported fallback, and no remaining pending work.

The postflight exports every key and immutable equal?-set endpoint from the live public mutable hash, preserving source-editor associations and exact integer ranges. Only the inherently unordered hash/set enumeration is sorted. All eight directed edges, including zero-width endpoints, are required. This expected stock graph was already recorded twice in successful native run38121983444; it is not inferred from the candidate. The full new stock/off/on graph and metadata must match.

It then dispatches the actual registered stock keymap functions for jump-to-binding, next and previous bound occurrence. Five fixed selections must be produced for `bump` and its parameter, then the initial selection is restored. Editor/canvas/tab identities, source, filename, modified state, public table identity and graph remain exact. It does not synthesize arrows, initialize tables, call custom replacement navigation, or alter the fixture. This tests registered command dispatch, not physical keyboard delivery.

Authoritative pinned source: `syncheck/gui.rkt` SHA2565aadb138… at1827–1909 defines those navigation consumers;2889–2897 registers the commands. `gui-lib/mred/private/wxme/keymap.rkt`739–750 resolves chained named functions and returns true after the real callback. Manual Check Syntax init/traversal/cleanup are at2663–2833. Public table getter is498–527; no normal navigation consumer reads it.

## Commands for the native owner

Assemble the selected runtime's complete proven source host, then replace/add this directory's test files. Copy `binding-native-pins.json` beside `binding-postflight.rkt`. The helper and workflow dependencies are included. Compile the host, postflight, workflow, appearance workflow, returning-Stop dependency and failure-propagation helper explicitly with the selected full Racket9.3 runtime and isolated profile/compiled roots.

Use fresh profiles for all three processes, existing strict60s native host/READY/capture supervision, stock appearance and stock128MiB for this small correctness fixture:

- stock: original GUI module, OPENRACKET_BINDING_TABLE_INDEX unset, OPENRACKET_BINDINGS_EXPECT_MODE=stock
- candidate-off: candidate GUI module, OPENRACKET_BINDING_TABLE_INDEX=0, OPENRACKET_BINDINGS_EXPECT_MODE=candidate-off
- candidate-on: candidate GUI module, OPENRACKET_BINDING_TABLE_INDEX=1, OPENRACKET_BINDINGS_EXPECT_MODE=candidate-on

For each set OPENRACKET_UI=stock, OPENRACKET_NATIVE_CASE=check-syntax, OPENRACKET_BINDINGS_RUNTIME_ROOT to the canonical selected runtime, and OPENRACKET_BINDINGS_OUTPUT to a fresh absolute JSON output path. Use the unchanged READY/capture handshake. Output success additionally prints `OPENRACKET_NATIVE_BINDINGS_OK complete-graph real-navigation escaped-table`.

Compare without editing evidence:

```
python3 tests/compare-bindings.py --stock stock.json --candidate-off off.json --candidate-on on.json
```

The comparison normalizes only verified mode/activation, canonical clone-root display, permitted GUI hash and validated witness state. All source-relative module paths, other pins, complete fixture graph, command order/results and preservation assertions must match. The candidate GUI pin in `tests/binding-native-pins.json` is checked against the production overlay by the coherent source manifest. Native execution is still pending.

The separate large-workload performance harness owns ordinary full application completion and a separately labeled first-public-getter measurement. This small fixture is correctness evidence, not a speed benchmark or proof of arbitrary custom-equality extension parity.
