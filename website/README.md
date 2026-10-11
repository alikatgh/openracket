# OpenRacket website

A plain project-information page with source branches, implementation notes,
build-documentation links, validation scope, and known limitations.

The production site is `index.html`, `changelog.html`, `blog.html` and `styles.css`. It has no JavaScript,
images, external fonts, tracking, backend, package dependencies, or build step.
It does not configure hosting or GitHub Pages.

## Preview

Open `index.html` directly, or run a static server from the repository root:

```sh
python3 -m http.server 8080 --directory website
```

Then open `http://localhost:8080`. Relative asset paths also support serving the
directory under `/website/`.

## Content

The page distinguishes the earlier Rust preview on `main` from the retained
DrRacket 9.3 experiment on `prototype/retained-drracket`. It links to each branch’s
own setup instructions rather than maintaining a second copy of those commands.
The pages make no full-compatibility or overall-editor speedup claim and provide no
application download. The dated changelog and technical blog describe the measured
localized autosave result, its evidence and limitations.

The website does not automatically follow repository changes. Recheck branch
names, prerequisites, and validation evidence when editing the project information.

## Verification

Run the dependency-free source checks from the repository root:

```sh
python3 website/tests/check_site.py
```

Real-browser checks are documented in `qa/README.md`. They run only on the
guarded public GitHub runner configured by `.github/workflows/website-browser.yml`.
The test packages are not website runtime dependencies.

The page uses semantic headings and navigation, a keyboard skip link, visible
focus, system light/dark preferences, and a single responsive text column.
Automated checks do not establish physical-device or screen-reader compatibility.

Website source is covered by the repository license. This independent project is
not an official Racket or DrRacket release.
