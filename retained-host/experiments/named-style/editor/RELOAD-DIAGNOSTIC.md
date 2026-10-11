# Failure-only WXME read diagnostics

This is an observational derivative of the exact 16:20 editor package. It is
not a proposed product or fixture repair. Run 38156051663 failed identically in
stock, stock-again, off and on after actual search/incremental lexer success and
rich save/identity checks. The exception was:

`insert-file in text%: error loading the file (read-from-file-failed)`

All available semantic snapshots match across the four arms under the existing
typed comparator. Each process recorded a 1,595-byte WXME with SHA256
`586f073086243701ac65ded8a10bd32c744becab99ea2ec41fe5a07c23d4949f`.
Those bytes were not transported, and the terminal run has no artifact holding
them. A specific serialization defect cannot be inferred from the digest.

## Source-backed boundary

Exact official source bytes and original Git identities are in PROVENANCE.json.
The four additional review-only vendor files are never imported by the harness.

- `vendor/public-editor.rkt`, lines 175–255: the ordinary public load-file wrapper
  opens the path, performs the standard load and propagates the original error.
- `vendor/wxme-text.rkt`, lines 2810–2845: the observed error means WXME detection,
  version and global-header checks completed, then read-from-file returned false.
- `vendor/wxme-text.rkt`, lines 2904–2927: the reader delegates to the actual
  read-snips-from-file implementation. Supported reader calls contain one, two,
  or three arguments including the stream, matching vendor/text-class.scrbl
  lines 1840–1859; the actual public load uses two.
- `vendor/editor.rkt`, lines 607–719: headers, style mapping, registered snip
  readers, nested state and footer checks can produce a false return.
- `vendor/snip.rkt`, lines 1402–1411 and 1459–1526: name-based class lookup may
  autoload/register a class. Diagnostics instead inspect the actual class's
  existing find-position/nth identity, without calling find or add.
- `vendor/stream.rkt`, lines 678–704: ok? reads status; tell also writes pos-map for modern
  WXME. The observer calls tell only after an original single-false return or
  raise. Stock load-file then aborts before any later stream reads. The reported
  position is a logical item index, not a byte offset. No tell occurs before
  reading or after a successful return.

No source-proven misuse was found in the standard load signature, UTF-8 style
names, 3×2 inlined image, or shared outer/nested style list. Existing assertions
and exact ordered comparisons must remain in force.

## Narrow changes

The restored editor is a test-local text% subclass. Its read-from-file overloads
call the corresponding super method once with the same actual arguments. The
observer preserves every returned value, including false, and rethrows the same
original raised object. Before/returned/raised observations are bounded to eight
events, containing actual argument count/arguments, result, and public stream
failure-only logical item position and ok state. Invalid observation state becomes unavailable evidence; it
cannot change the reader's result.

The original load-file call remains the sole load attempt. If it throws, the
failure observer adds `reload_failure` to capture.json with:

- `wxme`: exact ordered byte-array, count, SHA256 and encoding. Both file-size
  check and read are bounded by the existing strict 256 KiB file cap. An ordered
  byte array fits the existing recursive chunked evidence transport.
- `registry_before` / `registry_after`: relevant actual snip class/version and
  existing registry index/object-identity observations. No class is registered.
- `reader`: the bounded events described above.
- `partial_restored`: a best-effort snapshot using the unchanged editor-view.
- `original_error`: a bounded message accompanying the original exception that
  is still rethrown unchanged.

Each field is independently best-effort. JSON is checked before publishing the
whole record, so malformed diagnostic values cannot poison the normal failure
capture. An exception in the diagnostic reader, serialization or record sink
is suppressed only inside this failure observer; the same original load error
is always rethrown. There is no diagnostic acceptance path and no alternate
reader. Success produces no new capture fields and uses the unchanged strict
schema/comparator.

The original 30-second workload deadline, 40-second handler bound and 180-second
process bound remain. Mandatory pure native fault controls run before entering
the GUI fixture, inside the original outer process bound. They cover original
exception and arbitrary-raised-value identity; a single false result; multiple
returned values; exact overload arguments; exactly one super call; failing
observers; malformed JSON; and writes to a closed output port. They are source
prepared, not natively executed yet.

44 portable test methods pass, including delimiter lint and focused static
contracts. This is not Racket compilation or native proof. The original
comparator, snapshot, bootstrap and native runner bytes are unchanged. No
production, controls, performance, adapter, stock runtime or preview was edited.
Native publication/execution remains on hold until the parent authorizes the
next official Mac CI run.

If load-file returns false without raising, the unchanged check still fails;
this exact raised-load diagnostic wrapper adds no reload_failure record in that
separate case. It never substitutes that false return or changes acceptance.

Mandatory native fake-stream controls additionally require zero tell calls for
nonfailed observations, exactly one tell call and position17 after failure, and
preservation of the original false result when tell itself throws. The latter
control goes through the same observer boundary and keeps the false result in
the diagnostic event while marking only its stream detail unavailable.
