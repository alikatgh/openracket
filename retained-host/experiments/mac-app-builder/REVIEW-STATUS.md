# No-claim packaging correction: review pending

Prepared 2026-10-11 from the unchanged 0752 freeze. Only production code change:
remove the generated and inherited CFBundleDocumentTypes key during decoration.
The native launcher, all shell entrypoints/dispatchers, error transport, and the
155-file retained preview are unchanged. No native execution, Launch Services
registration/default edit, remote publication, or security change was performed.

Current checks: 28 portable checks passed. They include the original 20 Python
reference fixtures, which retain their previous plist policy, and eight source
checks. Only source checks cover this new policy here. The changed 20-case
RackUnit suite has NOT RUN; case 03 now checks inherited claims are stripped,
no claim is added to an input without the key, unrelated icon metadata survives,
and the native executable remains unchanged. Native plist/default-resolution and
cold/warm file delivery are NOT RUN for this correction. No local Racket runtime
was available, and no runtime was downloaded or installed.

Current implementation hashes:

- make-app.rkt: `12f635b329f2d021b9c714e82ca8895365a0361cf94a2c4a53ae9b647120af8d`
- test-app.rkt: `e6894532a532628b4b9c905938d9bc00f4dd0aaf8b7789dffd83428cf7c40663`

The exact 14-file candidate manifest is regenerated in CANDIDATE-SHA256.json.
Independent review is requested; the historical review below applies only to
the older implementation hashes and must not be attributed to this correction.

## Historical 0752 review (unchanged record)

# Independent source review and verification status

Reviewed 2026-10-11. This is source-level evidence, not Racket/native acceptance.

A separate read-only reviewer found no definite blocking defect in the final
builder APIs, plist representations, subprocess exit/argv handling, canonical
paths, isolated startup, or exclusive staging/publication flow against pinned
Racket 9.3 source. It checked the explicit source fixture/pin validation and
trailing-slash/dot config-to-dispatch test additions. No reviewer ran Racket,
RackUnit, a generator, a GUI or downloaded/installed runtime/packages.

Reviewed implementation hashes:

- `make-app.rkt`: `7ddf5ef4bfda7e44e926fe5187bccbe733c3aea5d49957f85533c58ac0c75167`
- `test-app.rkt`: `2539bcc5fd53824b15964754d260d069eb343bdf4c0ed6bc6568f1e85e4124b3`

Final local source checks: 27 passed. Twenty are the unchanged Python reference
oracle's tests against the byte-identical shell resources; seven cover source
pins, delimiter balance, shell syntax, script equality, a fake interpreter's
entry environment, test-case presence and lack of Python in product entrypoints.
They do not execute or establish equivalence of the Racket builder.

The reviewed Python prototype's 11 top-level files and the frozen 155-file source
manifest/content hashes were rechecked and remain unchanged. Candidate file hashes
are recorded in `CANDIDATE-SHA256.json`.

Release-blocking next evidence remains actual Racket parsing/compilation, all20
RackUnit cases, native app generation and the complete Mac acceptance document,
including whole-runtime mutation witness, Finder/Dock identity, cold/warm file
Apple events, failure UX, signatures/Gatekeeper and retained-source regressions.
The destination-built app remains tethered, with full official Racket 9.3 required;
self-contained distribution and Developer ID/notarization are later work.
