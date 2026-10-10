# Native detached-snip contract finding

Native run 38057531854, commit bb01478940f2d9018f15f4c2b0b49d10f3135a81, compiled
the full candidate and passed 13 of 14 native cases on both Linux and macOS.
The real shortcut and custom-merge regression passed. Timing was blocked.

The remaining case revealed an incorrect test/model assumption and a genuine
shortcut compatibility gap. Exact stock text.rkt calls object=? on the supplied
snip's admin before checking whether the editor is empty. A detached snip has
false admin and therefore raises a contract exception; returning false hides it.

The repaired shortcut accepts only false or an exact native string-snip% whose
stock get-admin is nonfalse. The exact class/interface check precedes the getter,
so custom virtual methods are never called. All detached, subclass, custom, rich
and invalid arguments use the original method. Foreign owned stock strings are
safe to return false because the original owner check does the same.

Restricting the shortcut to false alone would not optimize the measured input-port
path: mred/private/snipfile.rkt passes the actual starting snip. The new native
positive assertion therefore requires a shortcut hit for an owned starting snip.
Native tests compare actual contract outcomes rather than assuming detached
snips return false. This is a contract repair, not a weaker acceptance gate.
