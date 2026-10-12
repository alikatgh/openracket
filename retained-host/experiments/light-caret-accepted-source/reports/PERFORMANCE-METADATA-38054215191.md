# Public-API settings check: native Linux and macOS

Run: https://github.com/alikatgh/openracket/actions/runs/38054215191

Both platforms completed the bounded metadata-only probe for pristine stock and
modern-dark. All four trials report complete metadata, no field errors, and no
process timeout. Paired language-settings objects and preserved preferences match
exactly; the language-settings object also matches across the four trials.

The captured configuration is explicitly **pending next Run configuration** from
`get-next-settings`, not a measurement of a currently running evaluator:

- Language: `Determine language from source`
- Annotations: `lang-default`
- Immutable fixture's public `read-language` default: `debug`
- Resolved pending annotations: `debug`
- Simple settings: `#(#t print mixed-fraction-e #f #t lang-default)`
- Serialized settings:
  `(#(#t print mixed-fraction-e #f #t lang-default) (default) #() #f #t #t ((test) (main)) #t)`
- Child-only memory limit: 134,217,728 bytes
- Online compilation and syntax coloring: enabled
- Inline overview and spelling preferences: disabled by the stock defaults

The probe opens the deterministic 100,000-character fixture but performs no full
lexer wait or warm-input workload. Its partial opening/heartbeat values are not
new performance comparisons. The previous ordinary paired baseline remains
unchanged. The earlier failed metadata fields are not retroactively repaired;
this new native evidence closes the public-API capture gap for this probe.

Raw records for each platform contain two trial objects plus two summaries in
`linux-metadata-records.json` and `macos-metadata-records.json`. Read-only capture
uses documented settings exports and public reader info; no settings, limits,
tools or instrumentation are changed to obtain the result.

This settings agreement does not establish overall acceptance: the same CI run
has an independent intermittent pristine-stock Stop test failure on Linux.
