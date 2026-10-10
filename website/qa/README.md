# Real-browser website checks

These tests are for the static project website only. They are not native
OpenRacket or DrRacket application tests.

The workflow is restricted before runner allocation to the exact public
`alikatgh/openracket` repository and `website/openracket` branch, then rechecks
current public status using the job's existing read-only GitHub token. It uses
one standard `ubuntu-24.04` runner with a 15-minute limit. The checkout action is
pinned, credentials are not persisted, and there are no external AI services,
paid runners, deployments, caches, artifact uploads or release uploads.

Pinned official `playwright` and `axe-core` npm packages are installed only on the
disposable runner. The production website has no dependency on these packages.
The harness deliberately rejects local browser launches and serves the website
only on the disposable runner's loopback interface. Website external resource
requests are blocked and reported as failures.

The real Chromium checks cover desktop and mobile-emulated layouts, horizontal
overflow, local assets and anchor destinations, plain informational structure, readable typography, section navigation, keyboard
focus and selected WCAG rules. External link syntax and destinations are inspected;
this is not a claim that all external services are available. Automated checks
do not replace manual screen-reader or real-device testing.

PNG evidence is limited to five viewport screenshots, at most 350 KiB each and
1,500 KiB combined. Indexed 3,072-character base64 chunks, byte lengths and SHA-256
hashes are written to ordinary job logs. Decode retrieved completed-job logs with:

```sh
python3 website/qa/decode-screenshots.py job.log output-directory
```

The decoder rejects reordered, missing, modified, truncated, or duplicate images.
Inspect actual image pixels before reporting visual approval. Evidence is not
committed to the repository, uploaded as Actions artifacts or published as releases.

Verified cost basis:
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners

GitHub documents standard public-repository runner use as free; ordinary job logs
and summaries do not count toward artifact storage. This workflow must not be
expanded to private repositories or larger runners without separate review.
