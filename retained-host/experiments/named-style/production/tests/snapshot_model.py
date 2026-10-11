from dataclasses import dataclass
from itertools import permutations
@dataclass(eq=False)
class Style:
    name: object

def build(members):
    table = {}
    for style in members:
        if isinstance(style.name, str):
            table.setdefault(style.name, style)
    return (members, table)

def stock(members, name):
    return next((s for s in members if s.name == name), False)

basic, inner, outer, anon = (Style(x) for x in ('Basic', 'same', 'same', None))
snapshots = [(basic,), (inner, basic), (outer, inner, basic), (inner, outer, basic), (anon, inner, outer, basic)]
checks = 0
for publication_order in permutations(range(len(snapshots))):
    cache = None
    for i in publication_order:
        cache = build(snapshots[i])
        for members in snapshots:
            use = cache if cache[0] is members else build(members)
            for name in ('Basic', 'same', '', 'missing', '\u03bb'):
                assert use[1].get(name, False) is stock(members, name)
                checks += 1
# A stale completed build can replace a newer publication, but cannot masquerade
# as the new members snapshot. A lookup that already captured old members retains
# its old snapshot result, exactly as stock for/or.
old = snapshots[1]; new = snapshots[2]
old_build = build(old); new_build = build(new)
cache = new_build; cache = old_build
assert cache[0] is not new
assert old_build[1]['same'] is inner
assert build(new)[1]['same'] is outer
print(f'{checks} identity comparisons passed across every five-snapshot publication order; no native execution')
