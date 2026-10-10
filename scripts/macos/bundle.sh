#!/usr/bin/env bash
# Package an already-built native binary; never downloads, installs or publishes.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || {
  echo 'Packaging requires Apple Silicon macOS; Linux output is not a Mac build.' >&2; exit 1;
}
binary=${1:-"$root/target/release/openracket"}
out=${2:-"$root/dist/macos"}
[[ -f "$binary" && -x "$binary" ]] || { echo 'Build the release binary first.' >&2; exit 1; }
[[ "$(lipo -archs "$binary")" == arm64 ]] || { echo 'Expected one native arm64 slice.' >&2; exit 1; }
file "$binary" | grep -q 'Mach-O 64-bit executable arm64'
[[ ! -e "$out" ]] || { echo "Refusing to overwrite existing output: $out" >&2; exit 1; }
mkdir -p "$out"
out=$(cd "$out" && pwd)
work=$(mktemp -d "$out/.staging.XXXXXX")
trap 'rm -rf "$work"' EXIT
package="$work/OpenRacket"
app="$package/OpenRacket.app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources/licenses"
cp "$binary" "$app/Contents/MacOS/openracket"
chmod 755 "$app/Contents/MacOS/openracket"
python3 "$root/scripts/macos/write-info-plist.py" "$root/Cargo.toml" "$app/Contents/Info.plist"
printf 'APPL????' > "$app/Contents/PkgInfo"
cp "$root/LICENSE" "$root/THIRD_PARTY_NOTICES.md" "$root/DEPENDENCY-LICENSES.md" "$app/Contents/Resources/"
cp "$root/assets/FONTS-LICENSE.txt" "$app/Contents/Resources/"
cp -R "$root/licenses/." "$app/Contents/Resources/licenses/"
cp "$root/examples/welcome.rkt" "$app/Contents/Resources/"
cp "$root/docs/macos/README-MACOS.txt" "$package/README-MACOS.txt"
cp "$root/docs/macos/MANUAL-QA.md" "$package/MANUAL-QA.md"
plutil -lint "$app/Contents/Info.plist"
# Ad-hoc seal: no certificate, Apple account, network timestamp or notarization.
codesign --force --sign - --timestamp=none "$app"
codesign --verify --strict --verbose=2 "$app"
codesign --display --verbose=2 "$app" 2> "$out/CODESIGN.txt"
otool -L "$app/Contents/MacOS/openracket" > "$out/DYNAMIC-LIBRARIES.txt"
# Refuse runner-local/Homebrew libraries that would break on another Mac.
python3 "$root/scripts/macos/check-dylibs.py" "$out/DYNAMIC-LIBRARIES.txt"
cp "$out/CODESIGN.txt" "$out/DYNAMIC-LIBRARIES.txt" "$package/"
archive="$out/OpenRacket-macos-arm64-preview.zip"
ditto -c -k --sequesterRsrc --keepParent "$package" "$archive"
# Round-trip verification checks the actual distributable, not only staging.
mkdir "$work/unpacked"
ditto -x -k "$archive" "$work/unpacked"
codesign --verify --strict --verbose=2 "$work/unpacked/OpenRacket/OpenRacket.app"
cmp "$binary" "$work/unpacked/OpenRacket/OpenRacket.app/Contents/MacOS/openracket" >/dev/null || {
  # Signing may legitimately change the copied Mach-O; compare to signed source.
  cmp "$app/Contents/MacOS/openracket" "$work/unpacked/OpenRacket/OpenRacket.app/Contents/MacOS/openracket"
}
(cd "$out" && shasum -a 256 OpenRacket-macos-arm64-preview.zip > SHA256SUMS.txt)
cat "$out/SHA256SUMS.txt"
printf 'Created %s\n' "$archive"
