OpenRacket macOS status - 2026-11-06

The newest public engineering branch is prototype/retained-drracket at 0aa912f
(2026-10-22). main is the older 64c0f45 tip (2026-10-11), a documentation/website
update. No October 27-30 engineering work is present in the recovered repository
history. See ../RECOVERY-AND-GAP-2026-11-06.md for provenance and later reports.

The retained-DrRacket prototype has historical macOS core/native passes, but
stock Stop completion timeouts and large-file readiness/analysis stalls remain
open. Later Mac Stop passes and a 256 MiB capacity improvement do not close those
blockers. The separate Cocoa source package has not passed its native workflow.
There is no notarized macOS app.

HISTORICAL RUST/ICED PACKAGE README TEMPLATE
The text below describes the proposed OpenRacket 0.1.0 Apple Silicon package.
It is not evidence that a ZIP, app binary or MACOS-TEST-REPORT.md was delivered.
Its runtime, signing and coverage statements apply only to that proposed package,
not the retained-DrRacket or Cocoa prototypes.

OpenRacket 0.1.0 - proposed Apple Silicon development preview

This is an early plain-text Racket editor. It is not a full DrRacket replacement.
Requires Apple Silicon and macOS 15 or later for this preview build.
Intel Macs and earlier macOS versions have not been validated.

RACKET IS A SEPARATE REQUIREMENT
Install the official Racket 9.3 CS distribution for Apple Silicon from:
https://download.racket-lang.org/racket-9-3-aarch64-macosx-cs-dmg.html
Keep its full folder together. OpenRacket checks /Applications/Racket v9.3/bin/racket,
RACKET_BIN, PATH and conventional Racket locations. Its Runtime settings accept
an alternative absolute executable path. No Racket runtime is inside this ZIP.
Do not move only Racket's executable out of its installation.

The native OpenRacket executable is in:
OpenRacket.app/Contents/MacOS/openracket
Its Racket bridge and fonts are embedded; it does not need the source checkout.
The welcome example and licensing notices are inside Contents/Resources.

SIGNING AND TRUST
The bundle has an ad-hoc integrity signature only. There is no verified developer
identity and no Apple notarization. macOS may refuse to launch this downloaded
preview under Gatekeeper. This package does not alter security settings, remove
quarantine, grant permissions or bypass a security warning. Treat a blocked
launch as a release blocker. A successful CI build is not a claim that macOS
will accept the downloaded application.

TEST COVERAGE
See MACOS-TEST-REPORT.md beside the release download for the actual checks run.
Native GUI focus, dialogs, keyboard, clipboard, accessibility, IME and Finder
behavior require separate macOS desktop checks. See MANUAL-QA.md.
No end-to-end speed advantage over DrRacket has been measured.

Only run trusted Racket code: the interpreter has the user's normal file and
process privileges. Process separation is not a security sandbox.
