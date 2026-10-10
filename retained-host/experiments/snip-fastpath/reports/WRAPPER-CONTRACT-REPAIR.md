# Conservative contract-wrapper repair

This staged revision is separate from the active plain-text timing run
38058079020 (source 028f01282977aed8aa11764ca3e881dbaab8a2ec).
The active run and its immutable source remain unchanged.

An official Racket 9.3 headless probe establishes that `object/c` can preserve
both the underlying object's interface identity and `object=?` identity while
wrapping public methods. A range predicate on `get-admin` is therefore observable
in the earlier shortcut, while stock `find-next-non-string-snip` reads the
internal admin field and never invokes that public method.

The repair uses documented `has-contract?` at both the inserted-snip eligibility
walk and argument guard. Contracted exact-class snips delegate without the new
getter call; observing one in an insertion permanently disables the shortcut.
This is deliberately broader than object/c: public class/c instances can also
carry the marker. A blanket `impersonator?` exclusion was rejected because normal
Racket objects with public fields can have internal chaperones without any
external method contract.

No public Framework module or generic mixin changes. The private helper remains
opt-in. No virtual query, ownership mutation, class reflection hack or new scan
is introduced. The original exact native string interface, stable-cache and
mutation-history guards remain.

Local checks: 17 independent lifecycle/contract model cases, 3 source-preservation
cases and 3 lexer-fixture cases pass. The 5 generator-integrity, 7 installed-source
refusal and 3 lexer-comparator Python cases pass. The new native suite has 15
cases and remains unrun for this revision. Its ordinary editor-created string
case must prove no contract marker and exact stock/private lower-delegate counts
of 2/0 for both false and owned-start arguments. Its object/c case must prove the
marker is present and zero extra getter-contract callbacks.

The extra native gate is planned alongside a later isolated experiment batch.
Current timing results, when available, apply only to their exact earlier helper
and plain fixture; they cannot establish the guarded revision's performance or
extension compatibility.
