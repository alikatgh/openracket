# Light current-line number contrast: local review package

This is an unexecuted native verification package and an exact one-entry product
patch. It is not a native pass, a screenshot contrast measurement, or a complete
accessibility audit. No native execution or remote publication was performed.

## Product decision

Only OpenRacket Light / `framework:line-numbers-current-line-number-foreground`
changes from `#(36 94 219)` (`#245EDB`) to `#(35 91 215)` (`#235BD7`). The unchanged
current-line background is `#(220 228 239)` (`#DCE4EF`). All other bytes of
`tool/info.rkt`, including shared keyword/value blues and the complete dark
palette, are unchanged. No layout, renderer, widget, behavior, or memory change.

For the opaque intended sRGB pair, using the standard unrounded relative
luminance calculation:

- Original: 4.43009856144889:1
- Patched: 4.617119494850047:1

The original arm is expected to reproduce its exact sub-4.5 baseline. Only the
patched arm must also satisfy the unrounded `>= 4.5` threshold. The source code
and actual loaded color values establish this narrow mathematical claim;
anti-aliased screenshot glyph pixels have not been measured.

`production.patch` is the reviewable/reversible one-line product delta.
`production/tool/info.rkt` is its complete output. `native-host.patch` is a
separate, insertion-only test derivative and is not a production change.

## Exact inputs and provenance

- Accepted0520 product manifest: 155 members, SHA-256
  `2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552`.
- Original `tool/info.rkt`: SHA-256
  `b5cf6c820be53a5d4b95bb814947638ba49d126410003ea3d4560dae33b0c7d2`.
- Frozen1553 native overlay: 16 explicitly listed files; allowlist SHA-256
  `85185f6682f917385ce61809ecf94c26885344f6d8b0c091a31f5239f3080d98`.
- Exact light host input: SHA-256
  `402c4b4fffbbf03f4593a17a0c13a116d59fb497dfd873030d6ddd3366d22451`.
- Official racket/gui v9.3 annotated tag
  `ee75bb8250f43bc9db2f328c79b07b44b5be0f14`, commit
  `6f0213fa0535d87dd4e35f56c8266d948c8c089e`.
- [Official line-number renderer](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-lib/framework/private/text-line-numbers.rkt):
  Git blob `1d84b47aed5abfeef65dba32b2b82a125c0cd96d`, SHA-256
  `14ff8bd96dcaf07b8b8c115a85eb88a49f97f4e37cf7fbee03d50c5493a2f5e7`.
- [Official Cocoa color behavior](https://github.com/racket/gui/blob/6f0213fa0535d87dd4e35f56c8266d948c8c089e/gui-lib/mred/private/wx/cocoa/procs.rkt):
  Git blob `786b064d7ecd6015e995856ec270ab64540889af`, SHA-256
  `b6ce80e7673088f57edb9cd1fc5535a35741190c3f1197eedb55ddde850c00ca`.

The renderer identifies the current paragraph only when editor selection start
and end are equal. Cocoa returns false from `get-highlight-text-color`, so this
branch draws the dedicated current-line colors. Existing wide light screenshots
selected `lang`; that state does not exercise this branch. This package does not
alter or call the renderer's private routines.

## Portable verification

`python3 -B tests/test_package.py` runs source, contrast and adapter checks.
These cover exact input hashes, reversible one-entry scope, unchanged host waits
and diagnostics, source-pinned actual editor observations, malformed state,
wrong colors, viewport failures, positive and intentional-negative control
receipts, fixed outer deadline, capture/ack ordering, and exact source receipts.
A genuine symlinked TMPDIR run exercises path aliases without requiring a
case-sensitive filesystem. Lexical Racket delimiter checks are only screening;
a real Racket reader and compiler remain required.

The two real source-only compositions were verified against all155 accepted
members. They contain175 files each and differ only in `tool/info.rkt`.
Composition receipts contain relative members and hashes, with no local paths.
No input baseline or frozen source was changed. Detailed native prerequisites and
acceptance rules are in `NATIVE-CONTRACT.md`.
