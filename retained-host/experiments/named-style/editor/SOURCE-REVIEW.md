# Source proof and review limits

All links use exact official 9.3 source commits. Full individual-file Git blob
identity, SHA256 and byte lengths are verified in PROVENANCE.json; vendored
files are read-only evidence, never imported by the native test.

## Actual Racket mode and colorer

Official GUI commit 6f0213fa0535d87dd4e35f56c8266d948c8c089e:

- [framework/private/racket.rkt 298–356](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-lib/framework/private/racket.rkt#L298-L356)
  defines the actual token color categories and named-style mapping. Whitespace
  maps to the parenthesis style; this fixture does not invent a mapping.
- [1306–1368](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-lib/framework/private/racket.rkt#L1306-L1368)
  selects the official module lexer/wrapper, style mapper and real parentheses.
  [1459–1473](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-lib/framework/private/racket.rkt#L1459-L1473)
  composes the actual editor and installs its mode.
- [framework/racket.scrbl 424–436](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-doc/scribblings/framework/racket.scrbl#L424-L436)
  documents the public class/mixin used by this fixture.
- [framework/private/color.rkt 454–487](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-lib/framework/private/color.rkt#L454-L487)
  uses the actual editor style list for named lookups.
  [563–674](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-lib/framework/private/color.rkt#L563-L674)
  invalidates state, dispatches low-priority callbacks and marks completion.
  [1133–1175](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-lib/framework/private/color.rkt#L1133-L1175)
  supplies actual token readback; the gate waits for completion *before* reading,
  because those APIs could otherwise force pending lexing.
- The full [public color API contract](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-doc/scribblings/framework/color.scrbl)
  establishes observer, validity, classification, range and navigation methods.

The initial string begins at an explicit whole-editor forward `find-string`
result, checked against source-derived character position 31 and the exact
three-character actual range `"λ"`; get-text must match the complete source.
The pinned [find-string contract, lines 644–667](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-doc/scribblings/gui/text-class.scrbl#L644-L667)
defines the omitted start as the selection, while
[insert, lines 1203–1216](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-doc/scribblings/gui/text-class.scrbl#L1203-L1216)
places that selection at inserted-text end. Native cursor-at-EOF and absent-query
negative controls preserve this distinction. `SEARCH-REPAIR.json` binds the
historical four-arm failure evidence without inventing an unlogged target value.
Replacing the actual range with [1 2] must produce a matching
five-character bracket form, with forward end start + 5 and backward start
start. Every other position and navigation endpoint is still captured.

## Styles and rich content

- Official snip commit 3e6cf73c7bea6bd292462188e51ebabf8384ae53,
  [style.rkt 821–879](https://github.com/racket/snip/blob/3e6cf73c7bea6bd292462188e51ebabf8384ae53/snip-lib/racket/snip/private/style.rkt#L821-L879)
  supplies public names, attributes, deltas and graph edges.
  [1260–1272](https://github.com/racket/snip/blob/3e6cf73c7bea6bd292462188e51ebabf8384ae53/snip-lib/racket/snip/private/style.rkt#L1260-L1272)
  defines public index order and exact object lookup. The snapshot uses this
  order, not private members order or first-seen IDs.
- [Style read/write implementation](https://github.com/racket/snip/blob/3e6cf73c7bea6bd292462188e51ebabf8384ae53/snip-lib/racket/snip/private/style.rkt#L1382-L1620)
  writes explicit base/shift indices and delta/color data; public style indices
  are therefore a meaningful order and aliasing check.
- [wxme/editor.rkt 607–616](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-lib/mred/private/wxme/editor.rkt#L607-L616)
  reuses the stream's style-list identity and installs it when necessary.
  [editor-snip-class.rkt](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-lib/mred/private/wxme/editor-snip-class.rkt)
  reads the real embedded editor, borders, margins/insets and size constraints.
- Full public [editor](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-doc/scribblings/gui/editor-intf.scrbl),
  [text](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-doc/scribblings/gui/text-class.scrbl),
  [snip](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-doc/scribblings/gui/snip-class.scrbl),
  [editor-snip](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-doc/scribblings/gui/editor-snip-class.scrbl)
  and [image-snip](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-doc/scribblings/gui/image-snip-class.scrbl)
  documentation is retained, including set-style-list, save-file, load-file,
  find-snip, content/style getters and embedded geometry.
- Public [eventspace APIs](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-doc/scribblings/gui/eventspace-funcs.scrbl)
  supply a genuine handler thread and ordinary queue/yield behavior. This
  harness does not substitute an event dispatcher.

## Review and open native risk

A bounded independent review by the performance owner found and resolved three
concrete issues before the handoff: huge-number overflow in typed validation,
a launch failure incorrectly marked native-executed, and a final cache-valid
requirement not guaranteed by the real style-mutator ordering. Each correction
has a regression test. Callback failures are additionally retained and rejected.
Parent review also tightened the runner's actual PLTLINKS, compiled/debug resolver,
Python optimization and profile/XDG contamination exclusions.

The source review establishes the chosen APIs and evidence surface. It cannot
prove macro expansion, native GUI availability, actual framework startup-order
stability or rich serialization equivalence on a particular native runtime.
Those remain mandatory native gates. A stock-again difference is diagnostic
evidence and a blocker, never permission to weaken ordered comparison.
