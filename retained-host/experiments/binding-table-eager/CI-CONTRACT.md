# Eager binding-table stock-built-in experiment: native handoff

This snapshot is a default-off experiment. The delivered preview and app builder are not changed. Production changes only the pinned `drracket/private/syncheck/gui.rkt` and are enabled only by `OPENRACKET_BINDING_TABLE_EAGER=1`. The supported experimental domain and observable custom-equality/hash callback exclusions are in README.md and reports/SOURCE-AUDIT.md. A native result is still required; portable checks are not behavioral proof.

## Independent runtime preparation

Keep the original official full Racket 9.3 installation untouched and witness its complete tree before and after. Deep-copy independent stock and candidate runtimes. Use fresh purpose-specific preference/addon paths and the selected independent runtime's disposable compiled bytecode, matching the previously accepted measurement isolation; clear inherited experiment and collection/configuration overrides. Resolve the actual GUI module in each runtime and pin all unchanged supporting modules. Apply only to the candidate:

    python3 scripts/apply.py --runtime-root "$CANDIDATE" --target "$RESOLVED_GUI" --confirm-disposable-copy

The candidate source SHA256 is `80a32b3ebebbe741fe35a6c47f834cf35c0ea708c505961d0d98ce36ea37d6e3`; the original is `5aadb13833ad2e4a658c8b5d6a54d08831488a7f05ab84120252f9184667d13e`. Explicitly compile the actual selected GUI module, all four actual-form differential modules (`stock.rkt`, `candidate.rkt`, `stock-fault.rkt`, `candidate-fault.rkt` under `tests/generated`) and all native runtime-path helper dependencies with each selected runtime, without touching the original installation.

## Correctness before timing

Run the portable source/comparator checks, explicit native helper preflight, four actual-form processes, four unchanged stock-worker trace captures and three genuine GUI graph/navigation captures. Collect independent failures and keep timing blocked if any prerequisite fails. All processes remain externally bounded; an absent marker, skipped native gate, timeout, nonzero exit, incomplete output or source mismatch fails acceptance.

1. Run `tests/source-test.py` (30 cases), `native/scripts/prepare-host.py --check`, and `python3 -m unittest discover -s native/tests -p 'test_*.py'` (35 cases).
2. Run `tests/bindings-differential.rkt off` with the binding flag unset, `0`, and `unexpected`, and `tests/bindings-differential.rkt on` with flag `1`. Require exit 0 and exactly one final `BINDINGS_EAGER_DIFFERENTIAL passed mode=... checks=...` marker. The actual-form test raises on every failed assertion. Custom callback-boundary lines are expected disclosed exclusions, not general extension parity.
3. The trace/ subtree specifies the unchanged monitor/go and real rename-channel gate. Its four captures use the original worker implementation; this does not itself exercise the changed GUI consumer. Keep the stock-to-stock control, ordered consumer semantics, duplicate multiplicity and real rename-answer associations mandatory. Raw trace/paint order remains a diagnostic with its existing documented limits.
4. Run `native/tests/independent-native-host.rkt` in fresh stock, candidate-off and candidate-on profiles, with original stock appearance and stock 128 MiB for the small correctness fixture. Set `OPENRACKET_NATIVE_CASE=check-syntax`, `OPENRACKET_UI=stock`, `OPENRACKET_BINDINGS_EXPECT_MODE`, fresh absolute `OPENRACKET_BINDINGS_OUTPUT`, and canonical `OPENRACKET_BINDINGS_RUNTIME_ROOT`. Flags are unset, `0`, and `1`, respectively. Use the established READY/capture handshake and 60-second process bound. Require the ordinary native host success and exactly one `OPENRACKET_NATIVE_BINDINGS_OK complete-graph real-navigation escaped-table` marker. Compare with `native/tests/compare-bindings.py --stock stock.json --candidate-off off.json --candidate-on on.json`.

The native graph gate preserves all eight directed edges, including zero spans, and dispatches five actual registered navigation commands. Its eager-specific schema/witness requires eight real immediate eager writes, three existing public keys, first public exposure, zero in-flight/unsupported/failure fallback, no pending bindings and zero materializations. The public table is fully current before its first getter. It does not initialize or modify the table to manufacture those conditions.

## Conditional measurement

The performance/ subtree owns its exact CLI/schema and independently frozen manifest. It applies identical common completion/heartbeat observation to both selected runtimes only after correctness. Six new processes run in order stock/candidate, candidate/stock, stock/candidate, with the same real 1 MiB GUI workload and actual 256 MiB worker preference. No other production experiment is enabled. Keep all six records, all failures and the complete graph digest/count comparison.

Ordinary application completion, terminal delivery and lexer readiness are primary endpoints. The first and second public binding getters run afterward and have separate measured costs. The first call must only discard private read caches and return the already current original hash. Its candidate duration must be at most 1.000 ms in every trial, a fixed predeclared benchmark gate that cannot be widened after seeing results. This is not a universal real-time guarantee. Complete graph validation and final source/currentness/deadline checks remain outside getter command timing. The accepted candidate must show meaningful completed eager writes and active lookup caches before that call, then no cache/pending/materialization activity after it. Full graph counts/digests must match all stock arms. Source review does not authorize default adoption or a universal extension-compatibility claim.

## Run42 test/diagnostic repair

The candidate GUI, all four generated method modules, trace and performance subtrees are unchanged from1102. Native run38137618373 passed enabled3216 assertions but three disabled tests attempted to count a stock-poisoned hash after a deliberate custom callback exception. See reports/RUN42-FAULT-AUDIT.md for the exact runtime source and corrected bounded observation/cleanup. The180-second differential bound remains; stage output is flushed.

Before graph hosts, compile native/tests/native-tool-failure-diagnostics{,-standalone}.rkt in all arms. Run the exact standalone stock-runtime positive and --inject-failure controls under30seconds each. Require the unique typed markers/nonzero-negative policy specified in native/reports/RUN42-POSTFLIGHT-DIAGNOSTICS.md. Preserve independent failures and block timing on any failed control. All existing candidate-off graph/witness expectations are unchanged: its actual failing field remains to be identified by the added typed failure and scalar-state output.

The unchanged inherited trace README contains older INDEX flag examples; this eager retry must use OPENRACKET_BINDING_TABLE_EAGER for the outer off/on runtime environments, as the reviewed adapter does. All native-trace CLI --mode arguments remain stock because the worker is unmodified. No lazy INDEX flag is enabled.
