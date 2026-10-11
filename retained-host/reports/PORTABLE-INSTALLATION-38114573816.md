# Mac preview: verified installation, capacity default and rollback

The complete native acceptance run **passed** on Apple Silicon macOS 15 with full official Racket 9.3. This is an early runnable source preview, not a signed standalone application or complete tool-parity release.

- [Native run 38114573816](https://github.com/alikatgh/openracket/actions/runs/38114573816)
- [Exact tested commit 80e51d7](https://github.com/alikatgh/openracket/commit/80e51d78526d718a50c45f3662058a042c3038f7)
- Tested source: 155 files, manifest SHA-256 `2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552`

## What passed

The actual setup and launcher ran from a fresh directory containing spaces. A CI-only observer inspected the launcher-created real DrRacket frame and argv-opened Unicode file without opening it itself, replacing the entrypoint or changing preferences. Original editor/canvas classes, toolbar order, callback-bearing objects, theme state and loaded autosave activation were checked.

| Actual launch | Registered limit | Result |
|---|---:|---|
| Modern fresh profile | 256 MiB, automatically owned | Pass |
| Modern autosave opt-out | 256 MiB | Pass |
| Separate stock launcher | 128 MiB | Pass |
| Modern after restoring automatic default | 128 MiB, restored | Pass |
| Modern explicit stock limit | 128 MiB, explicit | Pass |
| Modern explicit custom limit | 384 MiB, explicit | Pass |
| Modern after repeated actual setup | 384 MiB, still explicit | Pass |
| Separate stock launcher afterward | 128 MiB | Pass |

Each modern launch passed 32 assertions and each stock launch passed 27. Genuine OS screenshots were captured for all eight launches. Modern Cocoa DarkAqua and the inherited stock Aqua state were verified. The fresh-default screenshot was visually inspected: the retained editor, filename/status surfaces and toolbar render in dark appearance with the original control placement.

The 31-test profile suite passed, including 20 real native cases for existing empty/no-key/custom/unlimited profiles, explicit choices, ownership, interruption, restore, source aliases, descendant-link refusal and write failure. The contract group passed all 35 tests after correcting a test-only JSON hash-kind comparison. The actual observer and product code were not changed by that correction.

Both independently hashed runtime trees remained identical across installation, repeated setup and every launch: **26,838 entries each**, including bytecode, file modes, directories and symlink targets. The original DrRacket unit, evaluation preference registration and colorer sources retained their exact pins. Only the isolated profile's GUI package copy contains the retained appearance and autosave overlays.

The combined installed host also passed both autosave-on and autosave-off save/recovery callers: 38 assertions per mode, with four actual filesystem failure/retry cases each, plain/rich reloads and exact recovery TOC mappings. These independent save callers used fresh **stock-128 profiles**; they are not a claim of a new save benchmark or save test specifically at 256 MiB. Verification-enabled conversion dialogs and crash/restart recovery UI remained unrun.

## Meaning of the new default

Automatic 256 MiB applies only when setup atomically reserves an entirely absent preview profile and its preference store remains absent. Existing profiles and explicit limits are preserved. The stock installation is unchanged. The same original preference affects both Run and background-analysis jobs; it is not a whole-app RAM cap. Launchers do not rewrite the setting. Restore changes only a still-owned automatic default to explicit 128 MiB; a user-selected value is not silently overwritten.

This is a **capacity fix**. In [the separate nine-trial Mac experiment](https://github.com/alikatgh/openracket/actions/runs/38107957744), the tested 1 MiB workload completed analysis in all three 256 MiB trials while all three 128 MiB trials ran out of memory. The smallest tested sufficient cap was 256 MiB; 512 MiB had no clear benefit. Successful analysis still took about 33–39 seconds. The launcher observer verifies the real registered preference; actual worker cap enforcement was measured separately in that experiment.

The preview retains the earlier measured autosave improvement. [Three matched Mac replacement-save pairs](https://github.com/alikatgh/openracket/actions/runs/38061486888) measured arm medians of 267 ms stock versus 172 ms enabled, about 35% lower; the median paired reduction was about 25%. Those measurements used stock appearance and the original limit. The newly combined preview has not been separately timed. The guard skips two redundant non-same-format scans; custom extensions observing those traversal callback counts can see fewer calls, and an explicit opt-out restores the original path.

## Remaining limits

Large-file coloring/analysis stalls, intermittent Stop behavior, complete Debug/Macro Stepper/teaching coverage, accessibility/IME, broad extension acceptance and Windows/Intel Mac/Linux installation remain open. The stock 20 ms colorer budget is retained. No scan, reply-cell or smaller-budget experiment is enabled. A passing bounded installer gate does not establish complete product parity.

## Delivered bytes and evidence

The ZIP contains the exact tested 155 source files plus their unchanged contents manifest. Its package structure and every source hash were verified after ZIP creation. Current instructions are a separate file so historical pending-state reports inside the tested source do not require changing those bytes.

- ZIP SHA-256: `689958d72cedb353ca69c4dbc207d6177a411a2296a2b480253b5a623f1b43c7`
- Helper SHA-256: `4a30290e88a8088c3223a810bbe96e276cc3398acee3e67dec7ef16a190fc742`
- Observer SHA-256: `ce3d961b5c6f2b5cb42edea8c984afcd9a87c309ff8e9409901eece4ed1fc9e5`
- Native log SHA-256: `db98f63b1fa172300a784d072553147e67d5b4b75b04fb136c964da7aeec9025`
- Unchanged runtime-tree SHA-256: `adaa2ac60b579a3219f189f1c8e56bc3f2ebb61913cfd62ea4cc692cbf427a60`

The runner was a standard free public GitHub macOS runner. No Actions cache, artifact or release upload was used. No installed runtime, generated cache, credential or user document is bundled in the source ZIP.
