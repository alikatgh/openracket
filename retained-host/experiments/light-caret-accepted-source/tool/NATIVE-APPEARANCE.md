# Opt-in native appearance candidate

This belongs only to the isolated polish candidate. The validated baseline is
unchanged. The new modules compile and their lifecycle/policy tests pass without
a GUI. Native Cocoa/GTK execution and screenshots still require the separate
approved graphical acceptance run; compilation is not native acceptance.

## Activation and retained-host contract

Native appearance requires all of:

- `OPENRACKET_HOST_THEME=1` and `OPENRACKET_UI` other than `stock`;
- `OPENRACKET_NATIVE_APPEARANCE=1`;
- a successfully committed OpenRacket appearance, including a saved `applied`
  profile at startup;
- a supported adapter on the existing GUI handler thread.

One controller owns the app-wide checkpoint across all existing/new frames. It
does not start a GUI, create another application, edit OS settings, or alter
titlebar implementations, control placement, callbacks, editor hosts or children.
Titlebars can adopt an appearance only through their original platform behavior.

Standard Preferences light/dark changes are followed only while native activation
is committed. Same-mode requests verify current native state before skipping the
setter, preventing appearance-notification feedback without trusting a stale mode
cache. External changes invalidate that verification.

The standard `platform` preference restores the original native appearance while
retaining the first checkpoint. This preserves nil/system inheritance rather than
pinning the app to the currently resolved light/dark mode. Platform following keeps
the existing contrast-safe toolbar capsules pending separate blend acceptance.

Explicit **Restore previous appearance** clears native activation and blending
before preference restoration or any queued synchronization. A native restore
failure is surfaced and prevents a false `restored` bookkeeping state; the owned
checkpoint remains available for retry. A failed *reapply* instead recovers the
previous committed native mode and activation without discarding the first
checkpoint. Opening another frame cannot undo an explicit restore.

Stock Preferences **Undo Changes** and Escape still restore Framework's full
preference snapshot. A separate queued state reconciler follows that final
committed applied/restored state. Internal transaction state writes are marked,
and a generation fence prevents older external callbacks from undoing a later
explicit Apply/Restore. Ordinary mode callbacks cannot reactivate a restored
session. Rapid external state updates coalesce to the latest committed snapshot.

Native titlebar appearance is process-local. Existing font/scheme preference
rollback requirements still apply: opting out or uninstalling alone does not undo
saved editor preferences.

## Cocoa: primary candidate

The adapter uses the public, strong, nullable `NSApplication.appearance` property.
It retains the exact original object (including nil), verifies the assigned
explicit pointer and the actual effective mode, and restores that exact object.
Racket 9.3 already observes `effectiveAppearance` and schedules stock dark-mode and
canvas-refresh events, so the adapter installs no replacement window machinery.

Only standard Aqua/DarkAqua explicit/effective appearances are eligible. Custom,
vibrant, unknown and high-contrast appearances are refused before new mutation.
The system Increase Contrast setting is checked too; inability to read it also
refuses capability. Exact checkpoint restoration remains possible in those states.
Apple documents automatic high-contrast variants, but this candidate deliberately
does not claim that unverified path as supported. It never changes accessibility
settings or explicitly assigns a high-contrast appearance.

For successful explicit Cocoa light/dark application, the optional retained
toolbar painter may leave idle/disabled canvases transparent to their actual
native parent. Unsupported/failed/restored states retain the safer capsules.

## GTK: experimental, not enabled by tool integration

The platform factory defaults `#:allow-gtk-candidate?` to false, and `tool.rkt`
always passes false. An isolated native adapter test can enable it separately.

The experimental adapter only considers an already selected Adwaita/Adwaita-dark
family. It compares resolved light, dark-variant and named-dark CSS to detect a
missing counterpart or GTK's silent fallback. Unknown themes, `GTK_THEME`
overrides, and ambiguous Adwaita-plus-prefer-dark states are refused. It never
forces Adwaita over another selected theme.

Racket 9.3 caches some native label/selection colors and listens to theme-name
changes, not prefer-dark alone. The candidate changes process-local prefer-dark
first and the positively verified paired name last, preserving the stock listener.
It sends no synthetic notification and calls no private cache-refresh function.

Both prior property values are restored exactly. However, public GtkSettings APIs
do not reveal their original application-versus-desktop source priority. Restoring
values with `g_object_set` cannot reconstruct that inheritance. Blindly calling
`gtk_settings_reset_property` could erase an earlier app override, so it is not
used. This limitation prevents strict-parity/default GTK rollout even if candidate
native palette tests pass.

## Verification

Headless:

    raco make tool/native-appearance*.rkt
    raco test tool/native-appearance-tests.rkt

The focused tests cover opt-in/thread guards, nil and exact object ownership,
reapply/rollback/retry/disposal failures, idempotence and external state changes,
platform inheritance, conservative Cocoa capability checks and effective-mode
acceptance, and strict GTK pair detection. Independent transaction/bridge tests
exercise the actual integrated tool definitions with before-commit callbacks.

In an approved graphical environment only, with an external timeout:

    racket tool/native-appearance-native-tests.rkt

That runner uses native stock controls, verifies actual platform mode and label
contrast, logs native label/selection colors, repeats mode/idempotence/platform
transitions, checks retained child identities/order and callback counts, and
restores the initial native values. For the separately authorized GTK experiment,
set `OPENRACKET_NATIVE_GTK_CANDIDATE=1`; unsupported capability fails the test
instead of silently substituting a theme. Independent full-DrRacket multiwindow,
Preferences and Restore acceptance is a separate test.

## Primary sources

- [Apple: NSApplication appearance](https://developer.apple.com/documentation/appkit/nsapplication/appearance)
- [Apple: choosing an app appearance](https://developer.apple.com/documentation/AppKit/choosing-a-specific-appearance-for-your-macos-app)
- [Apple: high-contrast variants](https://developer.apple.com/documentation/appkit/nsappearance/name-swift.struct/accessibilityhighcontrastdarkaqua)
- [Apple: Increase Contrast](https://developer.apple.com/documentation/appkit/nsworkspace/accessibilitydisplayshouldincreasecontrast)
- [GTK: application settings](https://docs.gtk.org/gtk3/class.Settings.html)
- [GTK: dark preference](https://docs.gtk.org/gtk3/property.Settings.gtk-application-prefer-dark-theme.html)
- [GTK: resolved named providers](https://docs.gtk.org/gtk3/type_func.CssProvider.get_named.html)
- [GTK: provider serialization and ownership](https://docs.gtk.org/gtk3/method.CssProvider.to_string.html)

Official cached Racket 9.3 `gui-lib` source: Cocoa `queue.rkt:129–141` and
`procs.rkt:184–257`; GTK `style.rkt:76–129` under `mred/private/wx/`.
