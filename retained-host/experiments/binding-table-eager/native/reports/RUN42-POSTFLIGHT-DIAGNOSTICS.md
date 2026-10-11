# Run 42: additive native postflight diagnosis

Run38137618373 is failed. Actual candidate-off Check Syntax printed the exact expected eight-edge graph and completed its original workflow, then failed a RackUnit assertion in postflight. Its old exception message was empty. The missing candidate-off bindings.json was a consequence; no timing ran. No particular expected witness field is changed based on this incomplete payload.

This revision adds only three postflight seams: the previously native-proven typed diagnostic import, a wrapper that reports and then rethrows the exact original failure, and best-effort actual scalar-state output before the existing witness assertions. Removing those exact additions reproduces the entire1102 postflight byte-for-byte (e885f5e08f37fed6846db28c0616e8c2dba9c11dcc3b146f470b829cb717cee6). Original graph, navigation, source/editor identity, flag and counter assertions remain exact. The native host and workload bytes are unchanged.

The two diagnostic modules are byte-identical to accepted run41. Their reporter contains arbitrary output/encoding failures, but the original assertion and rethrow stay outside that reporting boundary. A malformed state that cannot be encoded still reaches the original schema guard. Values are output-capped by the existing helper after formatting; the original outer process timeout bounds any custom-writer work. No failure is converted into acceptance.

Mandatory native preparation: explicitly compile native-tool-failure-diagnostics.rkt and native-tool-failure-diagnostics-standalone.rkt in all three native arms. Before the real host cases, run the standalone once with stock Racket9.3, each command under30seconds:

- Positive: no arguments, exit0; exactly one OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_OK typed-payload-preserved output-failures-contained; no injection/failure markers.
- Negative: --inject-failure, actual nonsignal/non-timeout nonzero exit; exactly one OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_INJECTING_FAILURE and exactly one OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_FAILURE exception=exn:test:check check=check-equal? actual=actual expected=deliberately-wrong; no success marker.

The real postflight emits OPENRACKET_BINDING_POSTFLIGHT_STATE for its actual public read-only scalar witness and OPENRACKET_BINDING_POSTFLIGHT_FAILURE for typed failure information. Neither marker replaces the unchanged successful graph document/terminal marker. Stock/off/on native gates and all correctness prerequisites still precede timing; the60-second small-host deadline remains unchanged.

Local validation:10 source/derivation checks and25 comparator checks pass. They prove exact additive preservation and payload helper pins, not native execution. Candidate-off actual failure remains to be identified from the next native evidence. The earlier run’s blank candidate editor screenshots also remain recorded observations; no screenshot-equivalence claim is made.
