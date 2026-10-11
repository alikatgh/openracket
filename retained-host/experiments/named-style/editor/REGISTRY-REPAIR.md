# Fresh-eventspace editor-snip registry setup

## Proven cause

Run 38159705157 produced identical failure evidence in all four arms. The
original `read-from-file` returned exactly `#f`; its stream changed from OK to
non-OK at logical item position 312. The partial editor contained all eight
styles and no inserted root snips. The actual embedded snip's stock `wxmedia`
version 4 class was absent from the current registry before and after loading.

The four losslessly recovered files are exactly 1,595 bytes, SHA256
`586f073086243701ac65ded8a10bd32c744becab99ea2ec41fe5a07c23d4949f`.
Their class header has only `wxtext`, `wxtab`, and `wximage`. The embedded
editor record starts with class map index -1. `reports/REGISTRY-CAUSE.json`
binds each capture digest, actual reader/registry evidence, and the exact
logical-item interpretation to the preserved raw result paths.

The pinned official source explains the full sequence:

1. `vendor/mred.rkt:73–76` creates every fresh eventspace while parameterizing
   a newly constructed snip-class registry.
2. `vendor/snip.rkt:1443–1453,1520–1526` initializes that registry with text,
   tab, and image only. The editor-class addition there is commented out.
3. `vendor/editor-snip-class.rkt:73–75` adds the stock `wxmedia` class once
   when that GUI module is instantiated. Our fixture imports GUI/framework
   first, then creates its separate eventspace. The later registry does not
   inherit that prior addition. `vendor/editor-snip.rkt:78` assigns this
   exact module's class object to the actual embedded editor snip.
4. `vendor/stream.rkt:29,60–70` captures the current registry and returns -1
   for a class omitted from its written class table. `vendor/editor.rkt:1517–1544`
   writes that -1, but writes no optional-length field because the actual
   `wxmedia` class remains required.
5. `vendor/editor.rkt:647–657` reads -1 as unknown and therefore consumes the
   following style index 0 as a zero optional length. The next record starts
   inside the nested editor payload. Its type 1 becomes `wxtab`, border 1
   becomes style, left margin 2 becomes string flags, top margin 3 becomes
   byte length, and right margin 4 becomes a nonexistent byte-string ID.
   `vendor/snip.rkt:382–395,733–748,771–787` and
   `vendor/stream.rkt:412–420` explain the final bad-state transition at 312.
   The single raw byte-string ID in the file is 0 (the PNG), never 4.

This establishes missing per-eventspace fixture setup. It does not establish
a named-style candidate defect or a different-module class instance. No
alternate reader, modified serialized bytes, or relaxed accepted shape is used.

## Documented setup and exact repair

`vendor/snip-class-list-intf.scrbl:6–17` documents a separate registry for
each eventspace, required for loading snips, with public `add` support.
`vendor/editor-funcs.scrbl:167–174` identifies the getter as the current
eventspace's registry. All new review sources are Git-blob/SHA256 verified
against the same pinned GUI commit in `PROVENANCE.json`.

The new `native/registry-setup.rkt` runs on the existing genuine GUI handler
after the rich fixture is constructed and before its unchanged real save.
It requires the embedded snip's class to be the exact installed stock
`the-editor-snip-class` object from the already source-pinned module. It uses
bounded `number`/`nth`/`find-position` observations, rejects an existing
same-name different object or version before mutation, and adds only the
missing exact object. It then requires exact registration plus unchanged
earlier class identities and indices. No `find` autoload or replacement occurs.

The docs say duplicate-name `add` ignores the new class; the pinned source
instead replaces the old entry. This fixture relies on neither behavior:
it rejects conflicts before calling `add` and never adds an already-present
exact object.

`registry_setup` records bounded before/after class order, versions, index,
and identity outcomes. The comparator additively requires the exact fresh
three-class list followed by those same three entries plus `wxmedia` version
4 at index 3. It compares that evidence across all four arms. Existing
comparator behavior is byte-identical after mechanically removing just these
additions, enforced by the historical SHA256 in a portable regression test.

Mandatory native isolated fake-registry controls exercise the same helper:
absent-class validation fails; registration appends once; an exact existing
class is not added again; conflicting identity/version is rejected before
mutation; ignored, wrong-object, or reordered addition fails; wrong requested
version fails. They never modify the live GUI registry.

## Scope and validation

Every original lexer, style, identity, nested-editor, image, ordered WXME
round-trip and final-yield assertion remains. The same one real save/load and
the diagnostic observer remain. The production candidate, telemetry, bootstrap,
snapshot, runner, and all 30/40/180-second acceptance clocks are unchanged.

50 portable methods pass both ordinarily and with TMPDIR explicitly set to a
symlink alias. These are Python/source/synthetic/mocked checks only. This repair
and its new mandatory native controls have not been executed in Racket locally
or in CI. A fresh official Mac run must validate them and the unchanged complete
editor/WXME acceptance before any performance result can be accepted.
