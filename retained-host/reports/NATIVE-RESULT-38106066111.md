# Xref reply experiment: native correctness passes, no adoption

Mac source: `6165c48f71fe601cf9b2d2e4692347cacdb0a380`.
Run: [38106066111](https://github.com/alikatgh/openracket/actions/runs/38106066111).
Candidate xref SHA256:
`d2db0c6860040909c31c8fa9f7945ad5b94da3a03e751791447faeee7c27105f`.

## Verified native gates

- Actual official Racket 9.3 module and test compilation passed.
- All 54 actual-form stock/off/on service cases passed, with zero failures or
  errors, including deferred breaks, cancellation, result identity and helper
  cleanup.
- All 12 native observer protocol and kill-safety cases passed.
- All four fresh real Check Syntax handler captures completed. The bounded
  annotation/rename comparator passed; exact raw paint-order equality remains
  an explicitly unproven, separately reported property.
- Stock and enabled genuine DrRacket Check Syntax host cases passed.
- All six fresh matched GUI workload records completed and passed source,
  actual-worker activation, settings, instrumentation and outcome validation.
- The original runtime's 26,838 entries remained unchanged. No Actions artifacts
  were uploaded.

## Decision

Keep the experiment default-off. The measurements do not establish a reliable
responsiveness benefit. Paired open-to-completed-editor-workload observations
were approximately 42.33 to 37.70 seconds, 33.66 to 33.85 seconds, and 31.71 to
44.51 seconds. Deadline-to-editor p95 increased in each pair. These are three
pairs from one standard hosted Mac run, not a broad statistical characterization.

More importantly, all six actual final-source background requests reported
explicit out-of-memory termination at the unchanged stock 128 MiB limit. None
delivered a monitor trace. A valid benchmark record and lexer completion do not
mean successful full background analysis.

The production change is preserved as a tested, reversible experiment, not
included in the delivered preview. The next separately approved investigation
varies only the stock memory preference in fresh profiles, with the xref
candidate absent. That will measure configuration capacity and responsiveness;
it cannot establish an algorithmic speedup.

Full log SHA256:
`1d169089ebee26cbc4a829456304cf246c73f4ee3dd952d1b0022516084f676d`.
The performance report retains the complete pairs, failed tool outcomes,
latency distributions, memory and observer-overhead limitations.
