# Object hashing: bounded read-only source review

Date: 2026-10-11 UTC. Scope: exact supplied class implementation and official Racket v9.3 sources. No production changes, candidate implementation, native execution, eligibility measurement, or speed claim.

## Conclusion

Prefer a small physical-structure guard inside the existing default `object-hash-code` body:

1. If `impersonator? obj` is true, immediately execute the original body.
2. Otherwise call `struct-info` on the original `obj`.
3. If its `skipped?` result is true, return exactly `eq-hash-code obj`.
4. Otherwise execute the original body unchanged.

The exact v9.3 implementations support this equivalence. For a plain structure, `struct-info` returns `skipped?` true only when the most-specific physical type is inaccessible to the current inspector. `struct->vector` inserts the existing hidden-value sentinel for that inaccessible layer. The original `inspectable-struct->vector` therefore rejects the vector, and `object-hash-code` returns precisely the same identity hash. A visible ancestor with `skipped?` true is sufficient evidence. `skipped?` false does not rule out hidden ancestors, so it must retain the old path.

Excluding all impersonators before `struct-info` prevents inspection interception and preserves visible-field read hooks, exceptions, and contract behavior. An opaque layer does not make those hooks irrelevant: the original conversion can read other visible fields before its sentinel scan rejects the completed vector. Do not unwrap or whitelist built-in chaperones. Keep the guard exclusively inside the default hash procedure so `equal<%>` and other custom equality/hash properties retain their dispatch.

`struct?` is less useful: standard objects inherit the transparent, zero-field `object%` structure, so `struct?` can be true despite inaccessible fields.

## Private-metadata alternative and caveats

A more complicated proof is possible under ordinary class representation invariants: reject impersonated objects/classes and replacement/primitive classes, require a canonical class with positive own-field count (cumulative width minus immediate-superclass width), and require its actual `class-obj-inspector` to be nonfalse and not subordinate to the current inspector. The inspector relation is strict: the same inspector does not suffice for access. This attributes a positive number of physical fields to the inaccessible layer.

That alternative depends on trustworthy class records, superclass vectors, and class/object correspondence. It does not establish correctness for fabricated or deliberately corrupted private records. A class-generated object predicate could additionally check membership. The physical `struct-info` guard avoids these extra assumptions and is preferred.

Do not use class introspection opacity as physical opacity. `class-insp-mk` can be `void` while the actual object inspector is transparent, notably for `object%`, class/c replacement classes, and interface-contract concretization. Total inherited field width plus apparent class opacity is insufficient.

The exact CS and BC sources insert a sentinel even for an inaccessible zero-field physical layer. The earlier zero-field concern applies to conflating class introspection with physical visibility, not a verified exception in these v9.3 converters. The proposed `struct-info` guard follows physical visibility directly.

## Eligibility prerequisite

This is a source recommendation, not a measured performance candidate. Before implementing or benchmarking it, obtain a witness at the real editor `object-hash-code` call entry, under that call's actual inspector:

- Whether the received argument is an impersonator/chaperone.
- For a plain argument, the actual `struct-info` result and `skipped?` value.
- Whether the proposed fast branch would therefore be reached.

The editor inspected elsewhere may differ from the argument supplied by the hashing machinery. Built-in unsafe-undefined chaperones intentionally miss the guard. A transparent leaf above inaccessible ancestors also misses it. If actual calls are ineligible, this review supplies no basis for widening the guard or claiming usefulness.

## Required differential checks before any promotion

Compare original and guarded primary/secondary hashes, recursive callback counts, equality/hash-table behavior, exceptions, and wrapper-hook traces. Cover inspector ancestry/siblings/sameness and `inspect #f`; public/private fields and zero-field layers; both mixed visible/hidden inheritance directions; class/c and repeated contracts, contracted superclasses, interface-contract concretization and sealed classes; object/c, field/property impersonators and built-in undefined guards; custom equality/hash properties; mutation, cycles and partially initialized objects. No such tests were executed in this review.

## Exact provenance

The supplied local file was only read:

- `openracket-binding-eager-experiment-freeze-20261011-1230/vendor/class-internal.rkt`
- SHA256: `1dbb533328bb46add290422c1e2fc6c1040d1f8e6d75b06f546734a294bb342f`
- Computed Git blob SHA1: `b3134180ee93023bfc2132d67c676b8246574c66`
- Official v9.3 `class-internal.rkt` tool response reported blob `b3134180ee93023bfc2132d67c676b8246574c66`.
- Byte-identity to that reported blob: verified.

Official sources below were read through GitHub tools, with the `v9.3` tag explicitly selected. Returned blob IDs were verified from tool metadata; no tag-resolved commit SHA was retrieved or inferred.

- [class-internal.rkt](https://github.com/racket/racket/blob/v9.3/racket/collects/racket/private/class-internal.rkt), blob `b3134180ee93023bfc2132d67c676b8246574c66`: supplied-file lines 2294, 2386–2456 (metadata/physical fields); 3273–3304 (original hashing); 3313–3354 (object%); 3496–3557 (concretization); 4771–4780 (custom hashing).
- [CS struct.ss](https://github.com/racket/racket/blob/v9.3/racket/src/cs/rumble/struct.ss), blob `d70bac22bcf0155670d22a9f472da454263778a2`: 941–964 (`struct?` and `struct-info`); 1321–1326 (visibility); 1386–1439 (vector conversion and wrapped field reads).
- [BC struct.c](https://github.com/racket/racket/blob/v9.3/racket/src/bc/src/struct.c), blob `e052c647d6a6aca644dab87674264318e9c8a6f7`: 2952–2988 (`struct-info`); 3200–3281 (vector conversion and wrapped field reads).
- [class-struct.rkt](https://github.com/racket/racket/blob/v9.3/racket/collects/racket/private/class-struct.rkt), blob `deb8e77f654e925d41d2f11e079da6524740adc7`: class representation and impersonatable object property.
- [class-c.rkt](https://github.com/racket/racket/blob/v9.3/racket/collects/racket/private/class-c.rkt), blob `25b15a0cc3dee2b0ac9b6dd233c611b0d6007191`: 295–367 (replacement metadata and zero-new-field structure).
- [object-c.rkt](https://github.com/racket/racket/blob/v9.3/racket/collects/racket/private/object-c.rkt), blob `64249995eb8aaa91c56e04289117fc3ce1d87aba`: 612–621 (object property impersonation).
- [class-undef.rkt](https://github.com/racket/racket/blob/v9.3/racket/collects/racket/private/class-undef.rkt), blob `f6ba93e21b9bfc1a5a583cd3bbf04d12ae25e541`: undefined-access analysis, inspected for context only.

Supplementary official documentation read: [structure inspectors](https://docs.racket-lang.org/reference/inspectors.html) and [structure utilities](https://docs.racket-lang.org/reference/structutils.html). A web preview of master `struct.ss` was seen before obtaining exact v9.3 sources; the conclusion above rests on the exact v9.3 responses.

No remote source files were downloaded or saved to the filesystem. They were read through tools and temporarily retained in tool-call memory. The only new file created by this review is this report.
