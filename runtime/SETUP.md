# OpenRacket: Racket setup and provenance

The editor expects a separately installed Racket executable. Set `RACKET_BIN`
to an absolute path, or have `racket` on PATH. Installing the complete Racket
package is the simplest option for users who need GUI or teaching libraries:
https://download.racket-lang.org/

For this local Linux x86_64 development build only, an official Minimal Racket
CS 9.3 tar archive was unpacked into a temporary development toolchain
without a system-wide install. Its local installation path is not required
to reproduce the build; set `RACKET_BIN` to your own Racket executable.

Verified upstream download:
https://download.racket-lang.org/releases/9.3/installers/racket-minimal-9.3-x86_64-linux-buster-cs.tgz

SHA-256:
`8f469b7e93645fc876594470d884775aafff7688f530fd38be873fb44c71ca6a`

The official release listing and checksum are at:
https://download.racket-lang.org/releases/9.3/

Minimal Racket includes the core modules used by this bridge (`racket/base`,
`racket`, `json`, `racket/async-channel`, and `syntax/modread`). No extra Racket
packages were installed for the runtime tests. The downloaded Racket runtime
is not part of this project's source and is not bundled in source deliverables.
There are no paid services or API keys involved.

## Licensing

Racket is available under MIT or Apache 2.0, with additional component notices;
Racket CS embeds Apache-licensed Chez Scheme. The authoritative license page is
https://docs.racket-lang.org/license/index.html . See the installation's
`share/LICENSE*.txt` notices if redistributing a Racket runtime. This project
invokes an external Racket process rather than embedding or modifying it.

## Implementation references

- Module declarations, source names, and dynamic loading:
  https://docs.racket-lang.org/reference/Module_Names_and_Loading.html
- Module namespaces for interactions:
  https://docs.racket-lang.org/reference/Namespaces.html
- Real Racket readers and EOF exceptions:
  https://docs.racket-lang.org/reference/Reading.html
- Captured input/output ports:
  https://docs.racket-lang.org/reference/customport.html
- Custodian-managed subprocess mode:
  https://docs.racket-lang.org/reference/subprocess.html

- Parameterizations and preserved thread-cell snapshots:
  https://docs.racket-lang.org/reference/parameters.html
  https://docs.racket-lang.org/reference/threadcells.html
