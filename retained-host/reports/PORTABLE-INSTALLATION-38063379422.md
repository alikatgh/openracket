# First real Mac portable-installation gate

Source commit: `0cdb9d9a12672cd2fac1ea05ead03a9a44deb7ed`.
[Native run 38063379422](https://github.com/alikatgh/openracket/actions/runs/38063379422).

The actual setup script failed before applying either source overlay. Racket
reported that `drracket` was already installed in the wider `installation` scope,
while setup explicitly requested `user` scope. `--skip-installed` did not cover
this wider-scope case. Native launcher, observer and combined-save execution did
not run and are not counted as passing.

Preparation and all included headless native-runner checks passed. Both the
pristine distribution and independent selected installation retained all 26,838
original entries, including file bytes, compiled bytecode, modes and symlink
values. Their before/after tree SHA-256 was identical:
`adaa2ac60b579a3219f189f1c8e56bc3f2ebb61913cfd62ea4cc692cbf427a60`.

## Narrow repair prepared

Setup now calls the public `pkg-directory` query before each requested stock
package. Exact Racket 9.3 `pkg/private/pkg-db.rkt` searches accessible scopes under
read-only package locks. An existing valid directory is reused, a genuinely
missing package alone is requested from the official 9.3 catalog, and a query
error or broken registered directory stops setup rather than being treated as a
missing package. The GUI copy, isolated appliers and compilation roots are
unchanged.

Five new checks cover the full-distribution case, one missing package, both
missing packages, query failure and the actual public query finding installed
`base` from a fresh isolated addon. Mock cases exercise the real setup shell and
stop before any package operation; the real query is read-only. Eight existing
profile/launcher checks and four source-provenance checks were rerun successfully.

The repaired actual native setup/launcher route still needs its separate rerun.
