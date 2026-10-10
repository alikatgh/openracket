# Retained-host polish candidate

This separate workspace starts from the verified 1206 source snapshot. It is not
published and has not passed native CI. The baseline retained-host workspace is
unchanged. Its historical reports describe the baseline, not these new changes.

## Typography seam

- The original platform `normal-control-font` object now supplies both stock
  width/height measurements and custom toolbar painting.
- Point versus pixel units, face, weight, smoothing and accessibility sizing are
  preserved. The 13 px sample font is only the offscreen preview default.
- No button event, callback, label, menu, tooltip, enablement, registration or
  ordering method changes. Original stock painter fallback remains byte-identical.
- Twenty-two added tests check platform-font identity across sizes and units,
  drawing bounds with the same measured font, and all three source font sites.
  Seventy-five combined font/source/paint checks and twelve integrity tests pass
  headlessly. Native font scaling and compact layout still need verification.

## Native appearance candidate

`OPENRACKET_NATIVE_APPEARANCE=1` enables a separate app-local candidate only when
this tool has successfully committed modern appearance. The Cocoa adapter uses
the existing NSApplication appearance, because stock Racket custom status/filename
painters read that same application palette. It retains the original appearance
object, including nil inheritance, across repeated light/dark changes. It never
sets desktop defaults or replaces native widgets. One controller serves all frames.

Explicit Restore clears the activation and toolbar blending gates before native
restoration, rejects a failed restore, and permits a retry. Failed reapply instead
recovers the prior committed mode while preserving the original native baseline.
Framework's `platform` mode restores original native inheritance, rather than pinning
its currently resolved light/dark value. Already queued callbacks and later-created
frames cannot reactivate an explicitly restored override.

Known high-contrast/unsupported appearances remain untouched. Before trusting a
same-mode notification, the adapter inspects current native state. Idle toolbar
buttons blend into original native surfaces only after native synchronization;
unsupported and platform-following paths retain safe capsules.

The GTK experiment remains disabled in real tool integration. Its value setters
cannot yet restore the original inherited setting source, so passing value-level
checks would not justify enabling it. Linux outer chrome therefore remains stock.

Pure lifecycle tests and independent actual-source transaction/bridge extraction
checks cover rollback, retries, queued notifications and shared baseline ownership.
They do not execute Cocoa. Actual native adapter and two-frame integration checks
are the next acceptance gate.

No claim is made yet that native toolbar/status backgrounds, custom label colors,
warning highlights, restore flows or multiple windows work with the new adapter.
The existing component image belongs to the earlier baseline and is not new
native evidence for this candidate.
