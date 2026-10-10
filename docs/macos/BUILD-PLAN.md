# macOS build and packaging route

Status on 2026-10-10: prepared and locally linted in Linux only. No Mac build,
workflow dispatch, repository push, upload or release has been performed by this preparation.
Original core Rust/Racket files are byte-identical to the reviewed snapshot.

## Build-only default

The proposed repository is **public `alikatgh/openracket`**. It must remain public
throughout a run. Source publication and workflow execution need authorization first.

1. Review the source overlay and verify the public repository's exact owner/name,
   visibility and default branch. This draft expects `main`.
2. After approved publication, put `.github/workflows/macos-preview.yml` on `main`.
   It listens only for `workflow_dispatch`; pushes do not start it.
3. In the repository, open **Actions → Build macOS preview (manual, public only)**.
   Click **Run workflow**, select **main**, then click the final **Run workflow** button.
   The connected GitHub tool does not currently offer workflow dispatch; this is
   the exact manual step needed unless another separately authorized route exists.
4. Review the job result and its **Summary**. The immutable source commit is checked
   out; real Racket tests, build, bundle signing and archive round-trip checks must pass.
5. In this read-only build workflow, **the ZIP is not retained** when the runner exits.
   Logs and the job summary remain the result. No Actions artifact/cache is uploaded.

Do not enable a push trigger as a workaround without explicit authorization of the
trigger branch and execution. It is deliberately absent from this draft.

## Downloadable preview, only after separate authorization

`macos-publish-workflow.yml.example` is intentionally outside `.github/workflows`
and has a non-workflow suffix. It is an alternative to the build-only workflow.
It builds and tests in the same ephemeral job, then calls `publish-preview.sh`.
After explicit approval of public binary delivery, it can replace the build-only
workflow on `main`. The same manual UI dispatch steps apply, under its Publish title.

This alternative needs `contents: write` on its one job to create a preview tag,
draft release and assets in `alikatgh/openracket`. It uses only GitHub's existing
per-job `GITHUB_TOKEN`, passed only to the delivery step; no PAT, saved credential,
service account, OAuth grant, signing key or API key is created. Checkout does not
persist credentials. All other token permissions are unspecified/disabled.

Publication is staged as a draft, all uploaded files are downloaded and byte-compared,
then the helper checks live public visibility again and publishes the prerelease.
No files or releases are overwritten. If an upload/verification fails, a partial
DRAFT may remain and must be inspected before retrying; no automatic deletion occurs.
A unique run/attempt tag prevents accidentally replacing a prior preview.

Release assets: ZIP, ZIP checksum and actual macOS test report. The script has no
LFS, Packages, Actions cache, Actions artifact or paid action integration.

## What the build does

- Fails closed before allocating a runner unless the event identifies the expected
  public repo and `main`; checks current public metadata again at startup.
- Uses standard `macos-15`, currently Apple Silicon. It never chooses `-large`,
  `-xlarge`, a configurable runner label, a self-hosted machine or the user's Mac.
- Uses one official GitHub action: checkout v6.1.0 pinned to the verified commit
  `d23441a48e516b6c34aea4fa41551a30e30af803`.
- Uses the runner's preinstalled rustup to fetch official Rust 1.94.0 components.
- Downloads official Minimal Racket 9.3 CS into a temporary folder, verifies its
  hard-coded SHA-256 before extraction/execution, and checks version/VM/modules.
- Checks frozen core hashes, formatting, clippy, normal Rust tests, real supervisor
  and application tests, both Python runtime suites, then a locked release build.
- Creates `OpenRacket.app/Contents/{Info.plist,MacOS,Resources}` with embedded-core
  binary, notices/licenses and example. It does not embed Racket or register file types.
- Seals the bundle ad-hoc without a signing identity or network timestamp;
  verifies signature, OS-only dylib dependencies and ZIP extraction integrity.
- Emits SHA-256 and an honest run-specific report. No window is driven or captured.

## Cost evidence and limits

GitHub documents **standard GitHub-hosted runner use as free and unlimited for
public repositories**, and lists `macos-15` under those standard ARM64 runners:
https://docs.github.com/en/actions/reference/runners/github-hosted-runners

GitHub's billing docs distinguish artifact/cache storage from execution. The
workflow avoids both storage mechanisms entirely. GitHub also says workflow logs
and job summaries do not count toward artifact-storage allowance:
https://docs.github.com/en/billing/concepts/product-billing/github-actions

For binary delivery, GitHub documents release assets separately: at most 1,000
assets per release, each under 2 GiB, with no aggregate release-size or bandwidth
limit. It recommends Releases for distributing large binaries:
https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github

These documents support Releases as the normal delivery route without using
metered Actions artifact storage. The Releases page does **not literally promise
“all storage is always free”**, and this plan does not make that blanket claim.
No paid feature, plan upgrade, billing setting, spending limit or subscription is
configured. Re-check the current published terms and repository visibility just
before an authorized run. A visibility change during a running job or an owner
editing the guards is outside this workflow's ability to guarantee a zero bill.

## Racket provenance

Verified official release listing:
https://download.racket-lang.org/releases/9.3/

Exact test runtime archive:
https://download.racket-lang.org/releases/9.3/installers/racket-minimal-9.3-aarch64-macosx-cs.tgz

SHA-256: `93c498c54804945c53412395e9ec7b33c56834f541710c2b3e161182be0c2670`.
Downloaded bytes were independently hashed during Linux preparation and matched.
Archive layout includes `racket/bin/racket`; its Mach-O header identifies ARM64.
It was **not executed on Linux**. Unlike an installer app, unpacking this archive
requires no root privileges, installer agreement acceptance or system settings.
The full signed macOS disk-image download is the recommended user runtime install:
https://download.racket-lang.org/racket-9-3-aarch64-macosx-cs-dmg.html

## Signing and remaining platform checks

Apple describes ad-hoc sealing as having no signing identity:
https://developer.apple.com/documentation/security/seccodesignatureflags/adhoc

Apple notarization requires an appropriate Developer ID signature; ad-hoc signing
does not meet that requirement:
https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution

Therefore this can produce a development preview, not a notarized frictionless
consumer release. Gatekeeper may block a downloaded ZIP's application. Do not
remove quarantine, alter security settings, grant TCC permissions or override
warnings. A blocked launch is recorded as an outstanding release blocker.

Actual native compilation, dylib/signing behavior, normal Finder launch and all
items in `MANUAL-QA.md` remain unverified until a Mac runner/desktop performs them.
The current default-DrRacket feature gaps are unchanged by packaging.
