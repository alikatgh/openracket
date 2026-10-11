# Bounded Mac packaging construction and metadata audit

This adapter runs only the frozen relative-launcher probe from
`openracket-relative-launcher-probe-freeze-20261011-1608`. Its 23 files are verified
against `MANIFEST.json`, SHA-256
`5c2967fe016ff7d7b1c5acf87de9050e4693ee9fa3f4ccb383b1ad9b6ab268a1`.
The later profile/code split is excluded. No accepted product/runtime integration
is changed. Publish this workflow only after the current named-style speed retry
has finished and the host has independently reviewed the exact final allowlist.

## Scope and exact order

The unchanged checksum-pinned official installer first obtains full Racket 9.3
CS in the disposable runner directory. Its existing version, VM and setup/dirs
verification queries run before the adapter boundary below. The later original
runtime witness therefore does not cover installation or those installer queries.

1. Independently inventory the entire original installed runtime, including every
   file's SHA-256/size, modes, nanosecond modification times, directories and
   symlink targets, before loading probe code or executing probe Racket imports.
2. Take the current account's read-only `.rkt` default-handler baseline with the
   frozen observer, sanitized native environment and a fresh private profile.
3. Run the mandatory frozen Python portable tests. These do not launch Racket.
4. Run the exact CLI `python3 supervise.py audit-runtime ORIGINAL --output
   FRESH/runtime-audit.json`. Validate its complete inventory against step1.
5. Run the exact CLI `python3 supervise.py build --runtime ORIGINAL --work
   FRESH/build-work --expected-runtime-digest EXACT_AUDIT_DIGEST`.
6. Independently query the default handler again only after a validated successful
   build, or if no native build was attempted and earlier native work is safe.
   Always attempt the final read-only original-runtime comparison independently.
7. Transport all explicit diagnostics and report construction/audit status.

The frozen builder itself takes its own pre-generation handler witness, reads and
compiles every probe Racket module, invokes the official generator once, copies
the complete runtime, verifies the copy's byte/mode/time/link inventory, and
records all nested plist/Mach-O/declaration metadata. It then records the handler
again and original source/runtime invariance. Native commands retain their exact
120-second wall and1MiB combined-profile-log bounds, plus a separate5-second
owned-process-group cleanup deadline. No automatic retry is added. The outer
workflow's35-minute emergency step bound does not extend those native deadlines.

There is no application-launch phase. The adapter never invokes the source `run`
subcommand, ProbeNative, ProbeBootstrap, `open`, or any Launch Services execution.
No-claim metadata also remains no-launch. Claims are reported as actual diagnostic
evidence with status `audit-complete-launch-blocked-by-declarations`; construction
can complete while launch acceptance remains blocked and untested. No metadata is
stripped from the runtime copy. The frozen generator's outer-skeleton edits and
intrinsic ad-hoc signing are disclosed in its unchanged source documentation;
there is no additional/manual signing, quarantine removal, default-handler setter,
security-setting change or application registration.

## Failure behavior

A failed build, missing receipt, malformed receipt or interrupted build leaves
native state unresolved. Every subsequent native query is blocked, including the
otherwise read-only handler observer. Its absence is explicit incomplete evidence,
never an unchanged-handler claim. The original filesystem witness still runs.
Frozen partial reports and logs remain runner-local; no cleanup removes them.
The next native stage is not attempted. A declaration block cannot be turned into
an application-acceptance result, and no log transport failure becomes green.

## Evidence transport

The existing `emit-replay-evidence.py`, `decode-replay-evidence.py` and
`decode-light-tools-evidence.py` are reused byte-for-byte. Explicit diagnostic
files are carried in hash/size-checked8192-byte base64 chunks inside the existing
bounded JSON transport. This covers oversized JSON strings/arrays, raw malformed
JSON and separate original stdout/stderr without truncation. Each file is bounded
at16MiB; exceeding the bound fails transport rather than silently dropping data.
Native runtime/bundle binaries and arbitrary profile files are never emitted.

Complete original inventories stay runner-local, identified by exact raw file
SHA-256, byte length, entry count and canonical inventory digest. All changed paths
and their complete before/after entries are emitted. `runtime-audit-metadata.json`
retains every audit field except the bulky inventory mapping, including every
plist/declaration/Mach-O/loader-context row; it adds the original full-report hash
and inventory summary. The full unchanged `build.json` is transported. The
unchanged general `runtime-tree-check.py` does not witness mtimes, so this adapter
uses its own independent stricter lstat witness rather than weakening that gate.

Decode downloaded job logs locally with the unchanged decoder:

    python3 retained-host/scripts/ci/decode-light-tools-evidence.py JOB.log FRESH_OUTPUT

`evidence-index.json` lists every explicitly expected path, presence, transport
status, size and hash. Missing successful-build diagnostics fail transport.
`handler-witness.json`, `runtime-witness.json` and `result.json` distinguish actual
observations, failed/incomplete evidence and mandatory no-launch status.

## Local-only validation

    PYTHONDONTWRITEBYTECODE=1 python3 retained-host/scripts/ci/test-packaging-audit-adapter.py
    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s retained-host/experiments/relative-launcher-probe/tests -v

Adapter tests cover source pins, runtime bytes/modes/mtime/link evidence, strict
status/declaration/schema handling, unconditional no-launch, exact CLI/digest/order,
failed-build blocking, independent witnesses, partial malformed diagnostics,
lossless large/non-UTF8 transport, incomplete output rejection and public-runner
workflow guards. They are synthetic and do not establish native app acceptance.

The workflow retains standard public macos-15 only, read-only permissions, pinned
checkout and public-metadata actions, exact tested commit, no persisted checkout
credentials, and no artifacts, caches, paid services or deployment. Work remains
sequential under the existing non-cancelling native concurrency group. Original
runtime/default handler preservation, actual native compilation/construction and
metadata rows remain pending until the parent runs this reviewed workflow.
