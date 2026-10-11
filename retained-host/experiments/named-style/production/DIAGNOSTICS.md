# Activation and actual-instance evidence contract

Flag: `OPENRACKET_NAMED_STYLE_INDEX`, enabled only by the exact string `1` at the
loading module's initialization. It is captured once; changing the environment
later does not toggle an already-loaded class.

Exports added to `racket/snip/private/style`:

- `openracket-named-style-index-enabled?`: immutable module binding, boolean
- `openracket-named-style-index-state`: accepts an instance of that module's
  `style-list%` and returns an immutable `hasheq` snapshot

The accessor calls a `define-local-member-name` diagnostic method. An unrelated
subclass may use the same printed spelling for an ordinary public method without
intercepting or colliding with it. The accessor rejects a non-instance with an
argument contract error. No new ordinary public API name is required on editors.

The immutable result contains only scalars:

| Key | Meaning |
| --- | --- |
| `enabled` | This module's captured activation boolean |
| `lookups` | Enabled public lookup entries after normal argument checking |
| `hits` | Calls reusing a matching members-snapshot cache, including absent names |
| `rebuilds` | Counter incremented immediately **after** complete pair publication |
| `members-traversed` | Visits performed during rebuilds, including visits in later aborted builds |
| `cache-valid` | The sampled cached list is `eq?` to the sampled members list |
| `named-entries` | Hash count in sampled cache, or 0 if absent; may describe an old cache when invalid |
| `member-count` | Existing stock member-count scalar |

Reading this state performs no lookup, iteration, rebuild or prewarming, and
retains no query/name payloads. All counters remain zero on the disabled branch.
A first lookup on a fresh Basic-only list records one call, one publication and
one member visit; later unchanged-list lookups record hits, even for misses.

Counters are deliberately unsynchronized diagnostic scalars. They are exact in
ordinary completed serial/eventspace operations, but are **not** a coherent
transaction or precise cross-thread accounting: an interruption after publication
can precede its counter increment; increments can be lost under unsynchronized
cross-thread interleavings. Visits are incremented before each private name read.
An interrupted lookup can count as a call without a hit or completed publication.
Do not invent a general `lookups = hits + rebuilds` invariant. No correctness
condition depends on these counters, and no lock or break suppression is added
to make the instrumentation look exact.

For eventual GUI evidence, obtain the **actual definitions editor's existing
style list** and the accessor from its **already-loaded runtime module**. Verify
the resolved source/candidate hash and flag. A newly instantiated style list or a
second copied module is not evidence about that editor. At a quiescent endpoint,
require genuine nonzero enabled lookup/hit evidence and report cold rebuild and
members-traversed counts separately, plus cache validity, named-entry count and
member count. Never perform a test lookup to force evidence before measurement.

Warm lookups do scalar counter work; cold rebuilds count every named and unnamed
member. Instrumentation cost and cold work are part of this candidate's measured
cost. The accessor has no clock calls, logging, style/name lists or payload export.
