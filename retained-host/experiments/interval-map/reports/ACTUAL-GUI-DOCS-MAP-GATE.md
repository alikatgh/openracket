# Actual retained-editor documentation interval gate

## Result and verification boundary

The prepared gate reads the actual docs interval map from the retained DrRacket
54-character Check Syntax fixture. It compares stock against the enabled
interval-map candidate without replaying annotations or constructing a test map.

67 Python synthetic rejection/source checks pass. Python compilation and a static
Racket delimiter/string scan pass. These are source-side checks only. Racket and
a native GUI are absent here: no Racket module compilation, GUI execution,
installed-runtime docs capture, or native equivalence result is claimed.

## Source/API conclusion

The reviewed Racket 9.3 blueboxes source defines `get-docs-im` with
`define-local-member-name` at lines 82–96 (the getter name is line 89). Its getter at line 666 returns the existing
`docs-im`; `get/start-docs-im` would allocate and is deliberately never called.
The actual consumer at lines 673–677 stores exactly
`(list start (+ end 1) definition-tag path url-tag)` via `interval-map-set!`.
The GUI adapter at `gui.rkt` lines 658–663 forwards those exact fields.

A `send` compiled against an ordinary symbol in the test module would not name
that private member. The postflight instead compiles the one literal expression
`(lambda (editor) (send editor get-docs-im))` with `eval` in the namespace returned
by `module->namespace` for the already-instantiated, exact source-pinned
blueboxes module. It neither dynamically requires that module nor instantiates a
second copy. Missing namespace/inspector access fails the existing host failure
route; there is no fallback accessor or inspector bypass.

The supplied official local Racket 9.3 reference, `Namespaces.html`, specifies
that `module->namespace` returns the body namespace of an instantiated module in
the existing registry and raises if its inspector does not control that module.
The official Guide's `eval.html` demonstrates evaluation using the module's
original body bindings. These local shipped documents were inspected without
network use. Native compilation is still needed to exercise this exact access.

## Host and dependency layout

Run `python3 scripts/prepare-native-host.py /path/to/frozen-retained-host` to
reproduce the derivative. It requires the exact frozen host hash and unique
insertion seams, and verifies that removing its two inserted blocks restores the
original bytes. It adds only:

1. One runtime path for `interval-docs-postflight.rkt`.
2. One postflight call, on the real GUI handler thread, after the original
   follow-on case and before the original paint/screenshot stage.

The original startup, original two real Runs, original Check Syntax workflow,
timeouts, event turns, READY markers, cleanup and screenshot coordination are
unchanged. The postflight requires stock UI, `check-syntax`, and no appearance
case. The existing frozen workflow already raises RackUnit failures on the real
GUI handler; the postflight also installs and verifies a raising handler.

Three unchanged runtime-path dependencies are copied into experiment `tests/`:
`independent-native-workflows.rkt`,
`independent-native-appearance-workflows.rkt`, and
`independent-native-stop-returning.rkt`. Four unchanged transitive dormant
appearance dependencies are copied into experiment `tool/`:
`native-appearance.rkt`, `native-appearance-platform.rkt`,
`native-appearance-cocoa.rkt`, and `native-appearance-gtk.rkt`.
These are copied test support, not candidate runtime changes. This complete local
layout avoids depending on whether `raco make` follows dormant runtime paths.
Every copied byte is pinned; hashes are in `native-docs-host.json` and checked by
the generator and Python tests. The frozen inputs are not edited.

Base host SHA-256:
`5d3fec70cb1ccae6ac91ea7ef2dc382011e7c173a2a8d34a51e6e01dad5fd448`

Two-insertion host SHA-256:
`ad0ba1ec80fb8dbcec86f54e1a0088d6a938c62c052d6bcaf7cb12e251134fb8`

## Runtime contract

Required environment:

- `OPENRACKET_UI=stock`
- `OPENRACKET_NATIVE_CASE=check-syntax`
- `OPENRACKET_NATIVE_APPEARANCE_CHECK` unset or not `1`
- `OPENRACKET_INTERVAL_EXPECT_MODE=stock` or `candidate-on`
- `OPENRACKET_INTERVAL_RUNTIME_ROOT` is that arm's explicit canonical clone root
- `OPENRACKET_INTERVAL_DOCS_OUTPUT` is a new output JSON filename
- `OPENRACKET_INTERVAL_MAP_FAST_SET` unset for stock, exactly `1` for candidate-on

The test verifies Racket 9.3, actual executable containment, exact current module
sources and the real exported activation value. Stock must lack the export;
candidate-on must export boolean `#t`. The only candidate change remains
`data/interval-map.rkt`: stock SHA-256
`1e18a3dafc6e1e87fd79c6fc67b5fd1c5cfd803f3caebf7c9f0ab0801ebb45de`,
candidate SHA-256
`1f1636316c3ba3f307fcb33f44d68c00ee9804b775fac7d78916db01d87fec4d`.

Actual data, blueboxes getter, GUI adapter, traversals, xref and online-comp
source paths/hashes are included. Their pins are rechecked after reading.
Existing file paths must remain canonically within the supplied clone even when
filesystem-resolved, including the actual documentation path. No path string is
rewritten. The encoder replaces only that verified prefix in actual path-valued
data and preserves every remaining byte, with the original root bytes retained
separately. Only Unix native paths are reviewed (Linux/macOS); unsupported paths
or datum types fail closed.

No GUI preferences, tools, source text, selection, annotations or map contents
are changed by this postflight. The existing host actions still execute normally.
The postflight checks unchanged source, filename, modified state, selection,
definitions editor, tab, canvas, canvas/editor association and docs-map identity.
A second complete enumeration must equal the first.

## Snapshot and positive control

Schema: `openracket-actual-gui-docs-map/v1`.

Every actual interval is read in iterator order, including its actual start/end
and its complete five-field stored value. There is no sorting or deduplication;
nested duplicate data are retained. Datums encode strings, interned symbols,
exact integers, booleans, bytes, lists, pairs, vectors and verified path values
with distinct type tags. Unknown values and bounded depth/node excess fail;
there is no lossy `format` fallback.

The exact fixture is unchanged:

    #lang racket/base
    (define (bump x) (+ x 1))
    (bump 41)

The actual `+` is at position 36, its source end is 37, and the stored interval is
exactly `[36,38)`. Its definition tag must be `(def ((quote #%kernel) +))`, its
full path must target `reference/generic-numbers.html` inside the verified clone,
and its exact URL anchor is `(def._((quote._~23~25kernel)._+))`. The installed
reference HTML supplied locally contains that exact anchor. The full actual path
is retained and compared, not shortened to its basename.

`interval-map-ref/bounds` at 36 must return bounds 36/38 and the identical stored
plus value. Point 37 must return that identical value; point 38 must not return
it. The full typed point-37 and point-38 lookup values and returned bounds are
emitted. The comparator verifies those witnesses against the full interval map.

Successful capture emits one JSON file and compact `OPENRACKET_INTERVAL_DOCS_MAP`
marker. Existing output files and repeat postflight calls fail to avoid stale or
duplicate results. The host then continues its unchanged screenshot/READY route.

## Strict comparison and rejection coverage

Invoke:

    python3 tests/compare-docs-map.py stock.json candidate-on.json

Pair within the same platform/runtime layout. The comparison validates both
captures, distinct clone roots, exact field sets, pins, activation and positive
controls. It then compares every field recursively. Only validated arm/mode,
flag, activation, original clone root, and the approved interval-map source hash
are excluded; every other source hash and clone-relative source/executable path
must match, along with every stored datum and interval in exact order.

The JSON loader rejects duplicate fields at any depth, extra JSON documents and
non-JSON constants. Tests reject missing, duplicated, reordered or tampered
intervals, count/geometry changes, changed tags/paths/anchors, broken + query
boundaries, altered source/selection/identity flags, wrong handler/accessor,
changed source pins/resolved paths, changed activation/mode, extra fields,
unsupported/lossy values, path escape/noncanonical paths and root-byte mismatch.
Synthetic fixtures in the unit tests are expressly comparator inputs; they are
not evidence of a GUI run.
