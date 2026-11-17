# Grok memo — OpenRacket website QA — static site scope

Private local context prepared 2026-11-06T16:11:08+00:00.
Folder: `/Users/s_avelova/Documents/projects/openracket/website/qa`.

[How we work](</Users/s_avelova/Documents/projects/pitches/docs/GROK_OPERATING_MEMO.md>) · [Memo coverage and routing index](</Users/s_avelova/Documents/projects/pitches/docs/GROK_MEMO_INDEX.md>)

## Context

`website/qa` contains the static OpenRacket website’s browser-check harness. Its README explicitly separates these tests from OpenRacket/DrRacket native application tests and describes restricted repository/branch checks, loopback serving and blocked external resource requests.

Recorded coverage includes desktop and mobile-emulated layouts, links, assets, overflow, keyboard focus and selected accessibility rules. The harness does not establish external service availability, manual screen-reader quality, real-device behavior or native app compatibility.

## Next useful actions

- For an authorized website change, inspect the specific harness coverage and affected page.
- Apply current cloud execution controls before starting its bounded CI workflow.

## Limits and freshness

- Do not report static website checks as native application validation.
- The documented runner restrictions and no-paid-service design must be verified against the actual current workflow.
- Dated local-document context; no external state independently verified
- Current user instructions and local AGENTS.md remain authoritative. This memo is context, not proof of live state or a new external-action authorization.

## Local sources

- [AGENTS.md](</Users/s_avelova/Documents/projects/AGENTS.md>) (applicable instruction)
- [README.md](</Users/s_avelova/Documents/projects/openracket/website/qa/README.md>) (safe readme)
- [README.md](</Users/s_avelova/Documents/projects/openracket/website/README.md>) (parent context readme)
- [grok-memo-targets-20261106.json](</Users/s_avelova/Documents/projects/pitches/research/grok-memo-targets-20261106.json>) (target inventory metadata)

Source fingerprints are recorded in the reviewed delivery plan; reread current sources before acting.
