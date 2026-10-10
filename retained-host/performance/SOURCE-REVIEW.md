# Retained DrRacket 9.3: performance review before native measurement

Status: benchmark source validated headlessly; native results pending. No performance
optimization was merged. This report identifies profiling targets, not proven
bottlenecks, and makes no speed claim.

## Exact sources

Inspected the already downloaded official9.3 release-package source archives as
read-only text. This did not install packages or launch a GUI. Provenance is recorded
in `vendor/PROVENANCE.md` and `reports/cached-packages.json`.

- `gui-lib/framework/private/color.rkt`, SHA256
  `da45ea64a5a0b413296a60ebe61d3e5ee69a27b53a6f1e13ae258701bdce1578`
- `gui-lib/framework/private/text-line-numbers.rkt`, SHA256
  `14ff8bd96dcaf07b8b8c115a85eb88a49f97f4e37cf7fbee03d50c5493a2f5e7`
- `drracket-core-lib/drracket/private/module-language.rkt`, SHA256
  `e76f13b6700df1ce1096f978353c938ef7816672efe9532483ffd38b710ffd53`
- `drracket-core-lib/drracket/private/unit.rkt`, SHA256
  `535a8a60592727cbba63bcd4485925cfaec49dbc3ebb9173715eb4ec5c7caff5`

## Verified behavior and implications

1. Coloring is already incremental. `color.rkt:388–451` checks an approximately20ms
   lexer slice, reuses invalid token trees when lexer modes converge, and retains
   parenthesis-token state. `634–672` applies styles inside edit sequences and
   reschedules unfinished work through low-priority eventspace callbacks.
   The slice threshold is not a hard event-loop latency ceiling: an individual
   lexer call and end-edit-sequence work can run past it. A naive replacement that
   repeatedly re-lexes the whole file would discard an existing optimization.

2. Some synchronous completion paths exist. `color.rkt:674–680` runs `finish-now`
   until the token states are complete; `734–760` calls it for freeze/thaw/recolor.
   These APIs have semantics. Removing them, forcing the colorer off, or measuring
   with stopped coloring would not preserve stock capability. Native profiles
   should establish whether any measured scenario actually reaches these paths.

3. Online expansion already uses a separate place, but preparing its input touches
   the editor. `module-language.rkt:1344–1368` allocates a full-buffer string and
   copies string-snip contents; rich content takes the standard serialized path.
   The timer path at `2373–2403` invokes this before `send-to-place`. This makes
   snapshot construction and post-edit expansion lifecycle worthwhile profile
   targets. It does not establish that expansion causes an observed pause.
   Chunking or incrementalizing the snapshot requires preserving edit-version,
   rich-document and cancellation semantics, so it is not a safe blind patch.

4. Stock file opening already batches edits. `unit.rkt:2462–2474` wraps normal
   `load-file/gui-error` in an edit sequence; the definitions editor's load hooks
   at `640–670` select the language, restore modification state, and complete the
   sequence. A benchmark must use this retained path and allow its normal lexer
   and tools to run. Directly loading a bare `text%` would be a different workload.

5. The modern toolbar patch does not change those editor algorithms. Its painter
   currently constructs color objects, measures visible labels, and draws vector
   geometry in `src/paint.rkt`. Caching immutable palette/geometry/label metrics
   could be considered if the native profile shows meaningful paint cost, with
   keys covering theme, locale, font, scale and label changes. It cannot plausibly
   be presented as an established cure for large-file open/jump pauses.

6. The user-program memory limit is an evaluator custodian setting, not the GUI
   process's resident memory: `rep.rkt:889` reads the configured child-only limit;
   `1356–1367` applies it to the evaluation custodian. The benchmark reads and
   preserves it, reports GUI managed/peak RSS separately, and does not enlarge or
   remove it to claim a win.

## Next decision after CI

First reject incomplete, timed-out or settings-mismatched comparisons. Compare
stock and modern distributions from the same runner/OS and exact fixtures. Inspect
synchronous action time, queue-fence time and heartbeat gaps together. Keep any
improvement that is demonstrated without regressions; treat an equal/slower result
as evidence that appearance alone has not achieved the performance goal.

A next optimization needs an observed expensive call path, isolated ownership,
explicit implementation approval, and regression coverage for incremental edits,
undo/redo, Unicode/IME, rich snips, theme/font changes, tool callbacks and cancellation
as applicable. Neither turning off tools nor replacing the full editor with the
older Rust/Syntect prototype is an equivalent comparison.
