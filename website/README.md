# OpenRacket website

A standalone, responsive project website. Plain HTML, CSS, and JavaScript; no build step, package installation, remote fonts, analytics, tracking, or backend.

## Preview

Open `index.html` directly in a browser, or serve this directory with any static server:

```sh
python3 -m http.server 8080 --directory website
```

The command above assumes the repository root as the working directory. Open `http://localhost:8080`. Serving this folder is sufficient; there are no root-relative asset paths, so it also works under a project subdirectory.

This source publication does **not** configure GitHub Pages or any other hosting.

## Design and content

- Paper, ink blue, and sage surfaces; editorial serif headings and system UI/monospace stacks.
- A clearly labeled interface design study with local light/dark preview controls. It is **not** a screenshot, Racket evaluator, or interactive implementation of the illustrated toolbar.
- Original inline vector artwork and an original parenthesis-inspired favicon; no third-party image assets.
- Direct links distinguish the earlier Rust preview on `main` from the `prototype/retained-drracket` experiment.
- Compatibility, native behavior, and performance are development goals and acceptance gates. No finished app, benchmark multiplier, or verified feature-parity claim is made.

The website does not follow later branch status automatically. Recheck project evidence before changing claims or adding downloads and benchmark results.

## Accessibility and progressive enhancement

Semantic landmarks, heading order, a skip link, visible keyboard focus, native disclosure controls, accessible theme-button state, and a live status announcement. The site is readable with JavaScript disabled; only the design-study theme controls require it. The theme selection is temporary and not saved. Reduced-motion and forced-colors modes have explicit treatments.

## Checks

From the repository root:

```sh
python3 website/tests/check_site.py
node --check website/script.js
node website/tests/check_interactions.cjs
```

The source checks cover required metadata and landmarks, unique IDs, link targets, local assets, heading structure, stylesheet guardrails, text-color contrast pairs, and the theme interaction with a small DOM fixture. They do not replace real-browser visual, keyboard, responsive, or screen-reader testing.

Suggested browser checks: 360, 390, 768, 1024, and 1440 pixel widths; no horizontal overflow; both illustration themes; repeated theme selections; full keyboard navigation; FAQ disclosure; JavaScript disabled; 200% zoom; reduced motion; high-contrast mode. The toolbar illustration has no real Run or evaluation behavior.

## Files

- `index.html`: content, navigation, original interface illustration
- `styles.css`: responsive presentation and accessibility modes
- `script.js`: local-only theme-preview behavior
- `assets/mark.svg`: original favicon
- `tests/`: dependency-free source/interaction checks

Website source is covered by the repository license. Racket and DrRacket names identify the upstream projects; this is an independent project and does not imply upstream endorsement.
