# First native interval-map candidate gate

Run: [38119983626](https://github.com/alikatgh/openracket/actions/runs/38119983626)  
Commit: `1d272376354be24157ec60e23a060e99137d6890`  
Correctness source manifest: `88ab00b8e78d6eecdbf32fd21e8367a3448dd4de19c4a695b206b8ef7f0254f4`  
Telemetry manifest: `82bf5dba355c5374b5e0246a92a8b1064eafcffbed9ac3bba3eead52d1353f85`  
Full native log SHA-256: `d0f8ce60cefb247be4f8790a38db22f34fa4f214b6f45d103bcd7825e310144d`

## Passed on official Racket 9.3, macOS

- Actual stock, candidate-off and candidate-on modules and native test callers compiled.
- Both stock and candidate telemetry native preflights passed all 82 tests with zero skips, plus their memory-profile helper tests.
- Each of the three fresh differential processes (unset, `0`, `1`) passed 1,280 operations and 336,852 assertions, including ordered map contents, range queries, contracts, mutations and retained iterators.
- Four actual monitor/go trace captures completed: stock, stock-again, candidate-off and candidate-on. The complete bounded annotation/real rename semantic comparison passed. Exact raw producer order remains unequal, including the stock-to-stock control; the documented order-sensitive consumer projection and multiplicities are retained.
- The original runtime's complete 26,838-entry tree, including bytecode, remained unchanged.

## Blocking test defect

Both genuine Check Syntax hosts reached the same 54-character fixture and failed at the new postflight guard:

`interval-docs-postflight: RackUnit handler must raise`

The guard compared `(current-check-handler)` to `raise` using procedure identity after parameterization. Identity is not the behavior the gate needs to establish and can differ for contracted/wrapped procedures. This failure occurs before any documentation-map evidence is emitted. It does not establish a difference between the stock and candidate map implementations.

The narrow repair replaces that identity assumption with an actual deliberate-failure propagation witness while retaining fatal parameterization on the GUI handler and every documentation assertion. A separate-handler native regression must test the exact helper. Production overlay and telemetry remain unchanged.

## Still pending

The actual editor documentation-map postflight and its exact boundary comparison have not yet passed. Timing was correctly skipped. No speed improvement, complete GUI parity or adoption is claimed from this run. The candidate remains default-off and separate from the delivered preview.
