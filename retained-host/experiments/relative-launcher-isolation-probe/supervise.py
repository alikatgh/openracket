#!/usr/bin/env python3
"""Test-only supervisor. Native commands exist for a separately authorized Mac.

Default audit/validate operations are read-only. No network, package manager,
archive, signing, registration, default-setting, or upload command is present.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import platform
import re
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
BUNDLE_ID = "org.openracket.relative-path-probe"
CLAIMS = ("CFBundleDocumentTypes", "UTExportedTypeDeclarations", "UTImportedTypeDeclarations")
EXCLUDED_LAUNCHER = "DrRacket.app"
SYSTEM_ROOTS = ("/System/Library/", "/usr/lib/")
MAX_OUTPUT = 1024 * 1024
TIMEOUT = 120
STOP_TIMEOUT = 5


class Refusal(ValueError):
    pass


class NativeCleanupUncertain(Refusal):
    pass


def require(test, message):
    if not test:
        raise Refusal(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def inside(path, root):
    try:
        Path(path).relative_to(root)
        return True
    except ValueError:
        return False


def is_system_path(path):
    p = Path(path)
    if not p.is_absolute():
        return False
    # Static OS dependency gate only; loaded images separately require a file
    # or affirmative native cache evidence. Resolve aliases and parent traversal.
    canonical = p.resolve(strict=False)
    return any(inside(canonical, Path(root).resolve(strict=False)) for root in SYSTEM_ROOTS)


def normalized_system_image_name(path):
    """Lexical cache-name gate only, never a filesystem trust decision."""
    return (isinstance(path, str) and path.startswith("/") and "\0" not in path
            and str(Path(path)) == path and ".." not in Path(path).parts
            and any(path.startswith(root) and path != root for root in SYSTEM_ROOTS))


def classify_loaded_images(images, snapshot, bundle):
    """Validate same-process public-dyld witnesses; no path-only cache waiver.

    Reports come from this bounded probe, not an attestation of hostile code.
    The sampled names/headers are rechecked by the native observer before/after.
    A missing or malformed witness fails closed, including historical reports.
    """
    require(isinstance(images, list) and 1 <= len(images) <= 8192,
            "invalid dyld image list")
    require(isinstance(snapshot, dict)
            and set(snapshot) == {"schema", "method", "count", "stable", "records"},
            "dyld snapshot missing or malformed")
    require(type(snapshot["schema"]) is int and snapshot["schema"] == 1
            and snapshot["method"] == "public-dyld-name-header-cache-v1"
            and type(snapshot["count"]) is int and snapshot["count"] == len(images)
            and snapshot["stable"] is True, "invalid or unstable dyld snapshot")
    records = snapshot["records"]
    require(isinstance(records, list) and len(records) == len(images), "dyld witness count mismatch")
    require(all(isinstance(p, str) and p.startswith("/") and "\0" not in p for p in images),
            "invalid loaded image")
    require(len(set(images)) == len(images), "duplicate dyld image name")
    result = []
    addresses = set()
    for index, (raw, record) in enumerate(zip(images, records)):
        require(isinstance(record, dict) and set(record) == {
            "index", "raw", "header_address", "magic", "cpu_type", "file_type", "flags",
            "shared_cache_contains_path"}, "malformed dyld image witness")
        require(type(record["index"]) is int and record["index"] == index
                and record["raw"] == raw, "dyld witness index/name mismatch")
        address = record["header_address"]
        require(isinstance(address, str) and re.fullmatch(r"[1-9a-f][0-9a-f]{0,15}", address),
                "invalid dyld header address")
        require(address not in addresses, "duplicate dyld header address")
        addresses.add(address)
        for field in ("magic", "cpu_type", "file_type", "flags"):
            require(type(record[field]) is int and 0 <= record[field] <= 0xffffffff,
                    "dyld header fields must be exact uint32 integers")
        require(record["magic"] == 0xFEEDFACF and record["cpu_type"] == 0x0100000C,
                "unexpected loaded Mach-O architecture")
        require(type(record["shared_cache_contains_path"]) is bool,
                "cache membership must be an exact boolean")
        in_cache = bool(record["flags"] & 0x80000000)
        if in_cache:
            require(record["file_type"] == 6 and record["shared_cache_contains_path"] is True
                    and normalized_system_image_name(raw), "unproved OS shared-cache image")
            # Deliberately do not resolve this virtual cache name as a disk file.
            # A Cryptex alias may have no standalone file at its resolved target.
            result.append({"raw": raw, "kind": "os-shared-cache", "witness_index": index})
        else:
            try:
                path = existing(raw)
            except OSError as error:
                raise Refusal(f"loaded image has no file or cache proof: {raw}") from error
            require(path.is_file(), f"loaded image is not a file: {raw}")
            require(is_system_path(path) or inside(path, bundle), f"external loaded image: {raw}")
            result.append({"raw": raw, "kind": "os-file" if is_system_path(path) else "bundle-file",
                           "resolved": str(path), "witness_index": index})
    return result


def existing(path):
    return Path(path).resolve(strict=True)


def fresh_leaf(path, suffix=None):
    p = Path(path)
    require(p.is_absolute(), "new path must be absolute")
    require(not p.is_symlink() and not p.exists(), "refusing occupied output")
    parent = existing(p.parent)
    require(parent.is_dir(), "output parent is not a directory")
    require(p.name not in ("", ".", ".."), "invalid output leaf")
    if suffix:
        require(p.name.endswith(suffix), f"output must end in {suffix}")
    return parent / p.name


def dump_new(path, data):
    with Path(path).open("x", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def inventory(root):
    """Read-only lstat inventory; never follow a tree symlink while walking."""
    root = existing(root)
    require(root.is_dir(), "inventory root must be a directory")
    entries = {}
    for p in [root, *sorted(root.rglob("*"))]:
        s = p.lstat()
        entry = {"mode": stat.S_IMODE(s.st_mode), "mtime_ns": s.st_mtime_ns}
        if stat.S_ISLNK(s.st_mode):
            target = os.readlink(p)
            require(not os.path.isabs(target), f"non-relocatable absolute symlink: {p}")
            require(inside(p.resolve(strict=True), root), f"escaping symlink: {p}")
            entry.update(kind="link", target=target)
        elif stat.S_ISREG(s.st_mode):
            entry.update(kind="file", bytes=s.st_size, sha256=file_digest(p))
        elif stat.S_ISDIR(s.st_mode):
            entry.update(kind="directory")
        else:
            raise Refusal(f"special file is unsupported: {p}")
        entries[p.relative_to(root).as_posix()] = entry
    return entries


def inventory_digest(entries):
    return digest(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode())


def copied_inventory_equal(original, copied):
    # Root mode/time and every copied file/directory mode/time/link target matter.
    require(original == copied, "complete copied runtime differs from original witness")


def runtime_copy_plan(original):
    """One exact reviewed exclusion, never a configurable app-removal policy."""
    require(original.get(EXCLUDED_LAUNCHER, {}).get("kind") == "directory",
            "exact top-level DrRacket.app must be a real directory")
    require(not any("/" not in name and name.casefold() == EXCLUDED_LAUNCHER.casefold()
                    and name != EXCLUDED_LAUNCHER for name in original),
            "conflicting top-level DrRacket.app spelling")
    excluded = {name: entry for name, entry in original.items()
                if name == EXCLUDED_LAUNCHER or name.startswith(EXCLUDED_LAUNCHER + "/")}
    retained = {name: entry for name, entry in original.items() if name not in excluded}
    plan = {"schema": 1, "excluded_path": EXCLUDED_LAUNCHER,
            "original_inventory_digest": inventory_digest(original),
            "original_entry_count": len(original), "excluded_entries": excluded,
            "excluded_inventory_digest": inventory_digest(excluded),
            "excluded_entry_count": len(excluded), "retained_entry_count": len(retained),
            "retained_inventory_digest": inventory_digest(retained)}
    return plan, retained


def copy_isolated_runtime(runtime, destination, original):
    """Copy every original entry except the unused top-level stock launcher."""
    runtime = existing(runtime)
    destination = fresh_leaf(destination)
    require(not inside(destination, runtime) and not inside(runtime, destination),
            "runtime copy destination overlaps original runtime")
    require(not inside(destination, HERE) and not inside(HERE, destination),
            "runtime copy destination overlaps probe source")
    require(inventory(runtime) == original, "original runtime changed before copy")
    plan, retained = runtime_copy_plan(original)
    excluded = runtime / EXCLUDED_LAUNCHER
    for name, entry in retained.items():
        if entry["kind"] == "link":
            require(not inside(existing(runtime / name), excluded),
                    f"retained symlink depends on excluded launcher: {name}")

    def omit_stock_launcher(directory, names):
        return [EXCLUDED_LAUNCHER] if Path(directory) == runtime else []

    shutil.copytree(runtime, destination, symlinks=True, copy_function=shutil.copy2,
                    ignore=omit_stock_launcher)
    copied_inventory_equal(retained, inventory(destination))
    require(inventory(runtime) == original, "original runtime changed during copy")
    return plan


def verify_isolated_runtime(runtime, original, plan):
    expected_plan, retained = runtime_copy_plan(original)
    require(plan == expected_plan, "runtime exclusion manifest differs from original witness")
    copied_inventory_equal(retained, inventory(runtime))


def nested_claims(root):
    rows = []
    # Audit every Info.plist, including backing directories of bundle aliases,
    # mixed-case .APP names and framework metadata. No symlink traversal needed.
    for p in sorted(Path(root).rglob("*")):
        if p.name.casefold() != "info.plist":
            continue
        require(not p.is_symlink(), f"linked bundle plist refused: {p}")
        require(p.is_file() and p.stat().st_size <= MAX_OUTPUT, f"invalid/oversized plist: {p}")
        with p.open("rb") as f:
            data = plistlib.load(f)
        require(isinstance(data, dict), f"non-dictionary plist: {p}")
        rows.append({"plist": p.relative_to(root).as_posix(),
                     "sha256": file_digest(p),
                     "bundle_identifier": data.get("CFBundleIdentifier"),
                     "declarations": {key: data[key] for key in CLAIMS if key in data}})
    return rows


def refuse_claims(rows):
    # Even an empty declaration key is surfaced and held for review.
    require(not any(row["declarations"] for row in rows),
            "nested app document/UTI declarations require a reviewed disposable-copy plan; no launch")


def macho_slices(data):
    if data[:4] in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf"):
        return [data]
    if data[:4] == b"\xca\xfe\xba\xbe":
        require(len(data) >= 8, "truncated fat Mach-O")
        n = struct.unpack_from(">I", data, 4)[0]
        require(n <= 32 and len(data) >= 8 + n * 20, "invalid fat Mach-O")
        slices = []
        for i in range(n):
            _, _, offset, size, _ = struct.unpack_from(">IIIII", data, 8 + i * 20)
            require(size and offset + size <= len(data), "invalid Mach-O slice range")
            slices.append(data[offset:offset + size])
        return slices
    if data[:4] in (b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbf"):
        raise Refusal("unsupported 32-bit/fat64 Mach-O; do not silently skip")
    return []


def macho_commands(data):
    result = []
    for part in macho_slices(data):
        require(part[:4] in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf"), "unsupported Mach-O slice")
        endian = "<" if part[:4] == b"\xcf\xfa\xed\xfe" else ">"
        require(len(part) >= 32, "truncated Mach-O header")
        _, cpu, _, _, ncmds, sizeofcmds, _, _ = struct.unpack_from(endian + "8I", part)
        require(ncmds <= 8192 and 32 + sizeofcmds <= len(part), "invalid Mach-O commands")
        offset = 32
        libs, rpaths = [], []
        for _ in range(ncmds):
            require(offset + 8 <= 32 + sizeofcmds, "truncated Mach-O command")
            cmd, size = struct.unpack_from(endian + "II", part, offset)
            require(size >= 8 and offset + size <= 32 + sizeofcmds, "invalid Mach-O command size")
            # LC_LOAD_DYLIB, WEAK, REEXPORT, UPWARD; LC_ID_DYLIB is not a dependency.
            if cmd in (0xC, 0x80000018, 0x8000001F, 0x80000023, 0x8000001C):
                require(size >= 12, "truncated dependency command")
                start = struct.unpack_from(endian + "I", part, offset + 8)[0]
                require(12 <= start < size, "invalid dependency string offset")
                raw = part[offset + start:offset + size]
                require(b"\0" in raw, "unterminated dependency string")
                value = raw.split(b"\0", 1)[0].decode("utf-8", errors="strict")
                (rpaths if cmd == 0x8000001C else libs).append(value)
            offset += size
        require(offset == 32 + sizeofcmds, "Mach-O command region mismatch")
        result.append({"cpu_type": cpu, "dependencies": libs, "rpaths": rpaths})
    return result


def macho_inventory(root):
    root = existing(root)
    rows = []
    for p in sorted(root.rglob("*")):
        if p.is_symlink() or not p.is_file():
            continue
        with p.open("rb") as f:
            magic = f.read(4)
        if magic in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe",
                     b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbf"):
            rows.append({"path": p.relative_to(root).as_posix(), "sha256": file_digest(p),
                         "slices": macho_commands(p.read_bytes())})
    return rows


def check_dependency_paths(root, rows):
    """Conservative static gate. @rpath needs native loader-context evidence."""
    root = existing(root)
    unresolved = []
    for row in rows:
        image = root / row["path"]
        for part in row["slices"]:
            for rpath in part["rpaths"]:
                if rpath.startswith("/"):
                    require(is_system_path(rpath), f"absolute non-system rpath: {row['path']}: {rpath}")
                elif rpath.startswith("@loader_path/"):
                    target = (image.parent / rpath[len("@loader_path/"):]).resolve(strict=False)
                    require(inside(target, root), f"escaping loader rpath: {rpath}")
                elif not rpath.startswith("@executable_path/"):
                    raise Refusal(f"unsupported rpath token: {rpath}")
            for dep in part["dependencies"]:
                if is_system_path(dep):
                    continue
                if dep.startswith("/"):
                    raise Refusal(f"absolute non-system dependency: {row['path']}: {dep}")
                if dep.startswith("@loader_path/"):
                    target = (image.parent / dep[len("@loader_path/"):]).resolve(strict=True)
                    require(inside(target, root), f"escaping loader dependency: {dep}")
                    require(target.is_file(), f"loader dependency is not a file: {dep}")
                elif dep.startswith(("@rpath/", "@executable_path/")):
                    # executable_path is tied to each actual process, not each dylib.
                    unresolved.append({"image": row["path"], "dependency": dep})
                else:
                    raise Refusal(f"unqualified dependency: {dep}")
    return unresolved


def new_profile(parent, name):
    p = fresh_leaf(Path(parent) / name)
    p.mkdir(mode=0o700)
    for leaf in ("home", "tmp", "addons", "compiled"):
        (p / leaf).mkdir(mode=0o700)
    (p / "TEST-PROFILE").write_text("disposable path-probe profile; no user state\n")
    (p / "TEST-PROFILE").chmod(0o600)
    return p


def clean_env(profile):
    return {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(profile / "home"),
            "TMPDIR": str(profile / "tmp"), "LANG": "en_US.UTF-8"}


def racket_command(runtime, profile, script, *args):
    return [str(runtime / "bin/racket"), "-X", str(runtime / "collects"),
            "-G", str(runtime / "etc"), "-A", str(profile / "addons"), "-U",
            "-R", str(profile / "compiled"), "-t", str(script), "--", *map(str, args)]


def native_only():
    require(sys.platform == "darwin", "native operation requires macOS and separate execution authorization")
    require(platform.machine() == "arm64", "probe targets native Apple Silicon, not Rosetta or Intel")


def stop_and_confirm_death(proc):
    """Bounded stop of an owned group; every unproved outcome has one type."""
    try:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + STOP_TIMEOUT
        proc.wait(timeout=max(0, deadline - time.monotonic()))
        while True:
            try:
                os.killpg(proc.pid, 0)
            except ProcessLookupError:
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise NativeCleanupUncertain("owned process group still exists after bounded stop")
            time.sleep(min(0.05, remaining))
    except NativeCleanupUncertain:
        raise
    except BaseException as exc:
        raise NativeCleanupUncertain("cannot prove owned process-group death after stop; no additional native work") from exc


def confirm_terminal_group(proc):
    try:
        os.killpg(proc.pid, 0)
    except ProcessLookupError:
        return
    except BaseException as exc:
        raise NativeCleanupUncertain("cannot verify terminal owned process group; no additional native work") from exc
    stop_and_confirm_death(proc)
    # Death is now proved, but this native observation still failed its normal
    # lifecycle contract. A read-only after-handler witness is safe; no relocation.
    raise Refusal("owned process group outlived leader; stopped and proved empty")


def bounded_run(command, profile, label):
    """No shell. Kill only this owned process group on time/log bound."""
    outpath, errpath = profile / (label + ".stdout"), profile / (label + ".stderr")
    def log_bytes():
        return sum(p.stat().st_size for p in profile.iterdir()
                   if p.is_file() and p.suffix in (".stdout", ".stderr"))
    with outpath.open("xb") as out, errpath.open("xb") as err:
        try:
            proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                    env=clean_env(profile), cwd=profile, start_new_session=True)
        except BaseException as exc:
            raise NativeCleanupUncertain("native process creation did not establish a verifiable owned group") from exc
        try:
            started = time.monotonic()
            while proc.poll() is None:
                if time.monotonic() - started > TIMEOUT or log_bytes() > MAX_OUTPUT:
                    raise Refusal("native command exceeded 120 seconds or 1 MiB output")
                time.sleep(0.1)
        except BaseException:
            stop_and_confirm_death(proc)
            raise
        # Establish death before output-port closing/reading can raise unrelated
        # errors. Such errors must never mask an unverified living process group.
        confirm_terminal_group(proc)
    require(log_bytes() <= MAX_OUTPUT, "native output exceeded bound")
    require(proc.returncode == 0, f"native command failed ({proc.returncode}); see {errpath}")
    return {"pid": proc.pid, "stdout": outpath.read_text(), "stderr": errpath.read_text()}


def handler(runtime, profile, label):
    result = bounded_run(racket_command(runtime, profile, HERE / "probe/default-handler.rkt"), profile, label)
    value = json.loads(result["stdout"])
    require(value.get("status") == "observed" and value.get("defaults_changed") is False,
            "read-only handler baseline unavailable")
    return value


def runtime_shape(runtime):
    for rel in ("bin/racket", "collects/racket/base.rkt", "etc", "lib", "share/pkgs", "doc"):
        require((runtime / rel).exists(), f"full in-place runtime member missing: {rel}")
    require(os.access(runtime / "bin/racket", os.X_OK), "console runtime is not executable")
    require(not inside(HERE, runtime) and not inside(runtime, HERE), "runtime and probe source must be independent")


def _build(runtime, work, expected_digest):
    native_only()
    runtime = existing(runtime)
    runtime_shape(runtime)
    work = fresh_leaf(work)
    require(not inside(work, runtime), "work directory must be outside original runtime")
    require(not inside(work, HERE), "work directory must be outside probe source")
    before = inventory(runtime)
    require(inventory_digest(before) == expected_digest, "runtime witness digest mismatch")
    runtime_copy_plan(before)  # Refuse missing/aliased/conflicting exclusion before native work.
    source_before = inventory(HERE)
    work.mkdir(mode=0o700)
    profile = new_profile(work, "build-profile")
    # A global read-only .rkt handler witness is taken before generation too.
    baseline = handler(runtime, profile, "handler-before-generation")
    dump_new(work / "handler-before-generation.json", baseline)
    dump_new(work / "original-runtime.json", before)
    dump_new(work / "source-before.json", source_before)
    compile_sources = [HERE / "make-launcher.rkt", HERE / "native-read-compile.rkt", *sorted((HERE / "probe").glob("*.rkt"))]
    bounded_run(racket_command(runtime, profile, HERE / "native-read-compile.rkt", *compile_sources), profile, "native-compile")
    app = work / "Path Probe.app"
    bounded_run(racket_command(runtime, profile, HERE / "make-launcher.rkt", app), profile, "generate")
    # This order is essential: the official generator deletes its destination.
    native = app / "Contents/MacOS/Path Probe"
    require(native.is_file() and not native.is_symlink(), "generated native executable missing")
    native.rename(native.with_name("ProbeNative"))
    resources = app / "Contents/Resources"
    copy_plan = copy_isolated_runtime(runtime, resources / "runtime", before)
    dump_new(work / "runtime-copy-plan.json", copy_plan)
    shutil.copytree(HERE / "probe", resources / "probe", symlinks=False)
    shutil.copy2(HERE / "bootstrap.sh", app / "Contents/MacOS/ProbeBootstrap")
    (app / "Contents/MacOS/ProbeBootstrap").chmod(0o755)
    plist = app / "Contents/Info.plist"
    with plist.open("rb") as f:
        info = plistlib.load(f)
    # Preserve existing outer identity/bootstrap contract; never strip claims.
    require(not any(key in info for key in CLAIMS), "generated outer skeleton declares document/UTI claims")
    info.update(CFBundleExecutable="ProbeBootstrap", CFBundleIdentifier=BUNDLE_ID,
                CFBundleName="OpenRacket Path Probe", CFBundleDisplayName="OpenRacket Path Probe")
    with plist.open("wb") as f:
        plistlib.dump(info, f, sort_keys=False)
    claims = nested_claims(app)
    machos = macho_inventory(app)
    pending = check_dependency_paths(app, machos)
    after_handler = handler(runtime, profile, "handler-after-generation")
    dump_new(work / "handler-after-generation.json", after_handler)
    require(after_handler == baseline, "global .rkt handler changed during generation")
    require(inventory(runtime) == before, "original runtime changed during build")
    require(inventory(HERE) == source_before, "probe source changed during native compile/build")
    record = {"schema": 1, "status": "assembled-not-launched", "original_runtime": str(runtime),
              "original_runtime_digest": expected_digest, "bundle": str(app),
              "native_sha256": file_digest(app / "Contents/MacOS/ProbeNative"),
              "nested_apps": claims, "macho": machos, "static_loader_context_pending": pending,
              "handler_baseline": baseline,
              "native_launch_blocked_by_declarations": any(r["declarations"] for r in claims),
              "native_launch_blocked_by_loader_context": bool(pending),
              "runtime_copy_plan": "runtime-copy-plan.json",
              "retained_runtime_digest": copy_plan["retained_inventory_digest"],
              "intrinsic_generator_ad_hoc_signing": True,
              "manual_signing_or_security_changes": False}
    dump_new(work / "build.json", record)
    return record


def build(runtime, work, expected_digest):
    # Preserve read-only failure evidence too; no failure cleanup deletes inputs
    # or partial output. An existing work path is never considered owned.
    native_only()
    root = existing(runtime)
    out = fresh_leaf(work)
    before_runtime, before_source = inventory(root), inventory(HERE)
    try:
        return _build(root, out, expected_digest)
    finally:
        after_runtime, after_source = inventory(root), inventory(HERE)
        witness = {"schema": 1, "original_runtime_before": inventory_digest(before_runtime),
                   "original_runtime_after": inventory_digest(after_runtime),
                   "source_before": inventory_digest(before_source),
                   "source_after": inventory_digest(after_source),
                   "original_runtime_unchanged": before_runtime == after_runtime,
                   "source_unchanged": before_source == after_source}
        if out.is_dir():
            dump_new(out / "protected-input-witness.json", witness)
        require(witness["original_runtime_unchanged"] and witness["source_unchanged"],
                "protected source/runtime changed; inspect protected-input-witness.json")


def walk_path_records(value):
    if isinstance(value, dict):
        if {"raw", "absolute", "exists", "resolved"} <= value.keys():
            yield value
        else:
            for child in value.values():
                yield from walk_path_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_path_records(child)


def validate_report(report, bundle, profile, expected_pid=None):
    bundle, profile = existing(bundle), existing(profile)
    require(type(report.get("schema")) is int and report["schema"] == 1
            and report.get("status") == "observed", "native report is not an observation")
    require((report.get("version"), report.get("os"), report.get("gc")) == ("9.3", "macosx", "cs"), "wrong native runtime")
    require(report.get("child", {}).get("status") == "observed", "child observation missing")
    require(type(report["child"].get("schema")) is int and report["child"]["schema"] == 1,
            "invalid console child schema")
    require((report["child"].get("version"), report["child"].get("gc")) == ("9.3", "cs"), "wrong console child runtime")
    runtime = bundle / "Contents/Resources/runtime"
    native = bundle / "Contents/MacOS/ProbeNative"
    for path in walk_path_records(report):
        require(type(path["exists"]) is bool, "path existence must be an exact boolean")
    for paths in [report["startup"], report["paths"], report["child"]["paths"]]:
        require(paths["use_collection_link_paths"] is True, "collection links disabled")
        require(paths["use_user_specific_search_paths"] is False, "user search paths enabled")
        for path in walk_path_records(paths):
            absolute = Path(path["absolute"])
            require(absolute.is_absolute(), "relative actual path")
            require(absolute.exists() == path["exists"], "path existence disagrees with filesystem")
            resolved = absolute.resolve(strict=path["exists"])
            if path["exists"]:
                require(path["resolved"] and existing(path["resolved"]) == resolved,
                        "declared canonical path disagrees with filesystem")
            else:
                require(path["resolved"] is False, "missing path claims a canonical existing target")
            require(inside(resolved, bundle) or inside(resolved, profile), f"escaped active path: {path}")
        for key, expected in {"exec-file": runtime / "bin/racket", "collects-dir": runtime / "collects",
                              "config-dir": runtime / "etc", "addon-dir": profile / "addons"}.items():
            require(existing(paths["system"][key]["resolved"]) == existing(expected), f"unexpected {key}")
        require(paths["setup"]["pkgs"]["exists"], "package root missing")
    require(existing(report["paths"]["system"]["run-file"]["resolved"]) == existing(native), "run-file is not native launcher")
    identity = report["identity"]
    for pid in (identity["pid"], identity["running_pid"], report["child"]["pid"]):
        require(type(pid) is int and pid > 0, "native PIDs must be positive exact integers")
    if expected_pid is not None:
        require(identity["pid"] == expected_pid, "bootstrap failed to preserve supervisor-owned process")
    require(identity["pid"] == identity["running_pid"], "Cocoa process mismatch")
    require(report["child"]["pid"] != identity["pid"], "no distinct console child observed")
    for field in ("main_bundle_path", "running_bundle_path"):
        require(identity.get(field) and existing(identity[field]) == bundle, f"wrong {field}")
    require(identity.get("main_bundle_identifier") == BUNDLE_ID and identity.get("running_bundle_identifier") == BUNDLE_ID,
            "wrong Cocoa bundle identity")
    require(identity.get("same_running_application") is True, "Cocoa identity changed")
    require(existing(identity["process_image_path"]) == existing(native), "actual process image is not outer native binary")
    # CFBundleExecutable metadata may be bootstrap; report it without pretending
    # it is the actual process image or forcing NSRunningApplication to match it.
    for field in ("main_bundle_executable_path", "running_executable_path"):
        require(identity.get(field) and inside(existing(identity[field]), bundle / "Contents/MacOS"), f"escaped {field}")
    classifications = {}
    for label, observed in (("gui", report), ("child", report["child"])):
        classifications[label] = classify_loaded_images(
            observed["loaded_images"], observed.get("loaded_image_snapshot"), bundle)
    require(set(report["modules"]) == {"racket_base", "setup_dirs", "pkg_lib", "gui_base", "drracket_main"}, "incomplete module witnesses")
    for module in report["modules"].values():
        p = existing(module["path"]["resolved"])
        require(inside(p, runtime), "package module escaped runtime")
        require(file_digest(p) == module["sha256"], "module witness hash mismatch")
    for paths in [report["startup"], report["paths"], report["child"]["paths"]]:
        for name in ("config_file", "links_file", "package_database"):
            record = paths[name]
            require(name == "config_file" or record["path"]["exists"], f"full-runtime {name} missing")
            # Configuration files may be absent in an official default layout;
            # report that absence explicitly. If present, verify actual bytes.
            if record["path"]["exists"]:
                p = existing(record["path"]["resolved"])
                require(file_digest(p) == record["sha256"], f"{name} hash mismatch")
            else:
                require(record["sha256"] is False, f"invented hash for missing {name}")
    return {"status": "path-and-identity-observation-validated", "bundle": str(bundle), "profile": str(profile),
            "loaded_image_classifications": classifications}


def loaded_closure(bundle, images, executable, rows, snapshot):
    """Resolve active arm64 Mach-O dependencies against measured dyld images.

    This proves the sampled image set's closure only. Unloaded optional runtime
    libraries and stock nested apps remain separate full-distribution coverage.
    """
    bundle = existing(bundle)
    executable = existing(executable)
    indexed = {str(existing(bundle / row["path"])): row for row in rows}
    classified = classify_loaded_images(images, snapshot, bundle)
    measured = {p["resolved"] for p in classified if p["kind"] == "bundle-file"}
    cache_names = {p["raw"] for p in classified if p["kind"] == "os-shared-cache"}
    require(str(executable) in measured, "actual executable missing from dyld snapshot")

    def expand(path, image):
        if path.startswith("@loader_path/"):
            return image.parent / path[len("@loader_path/"):]
        if path.startswith("@executable_path/"):
            return executable.parent / path[len("@executable_path/"):]
        if path.startswith("/"):
            return Path(path)
        raise Refusal(f"unsupported loader token: {path}")

    def arm_slice(row):
        values = [p for p in row["slices"] if p["cpu_type"] == 0x0100000C]
        require(len(values) == 1, "missing or duplicate arm64 Mach-O slice")
        return values[0]

    main = arm_slice(indexed[str(executable)])
    witness = []
    for path in sorted(measured):
        require(path in indexed, f"loaded non-system image absent from Mach-O inventory: {path}")
        image = Path(path)
        part = arm_slice(indexed[path])
        for dep in part["dependencies"]:
            if dep in cache_names or is_system_path(dep):
                witness.append({"image": path, "dependency": dep, "system": True})
                continue
            if dep.startswith("@rpath/"):
                # Handle this image's and the main executable's declared rpaths.
                # An inherited intermediate-loader rpath is intentionally refused
                # until a richer loader-chain witness is supplied, never guessed.
                bases = [(v, image) for v in part["rpaths"]] + [(v, executable) for v in main["rpaths"]]
                candidates = [expand(v, owner) / dep[len("@rpath/"):] for v, owner in bases]
            else:
                candidates = [expand(dep, image)]
            resolved = []
            for candidate in candidates:
                if str(candidate) in cache_names or is_system_path(candidate):
                    resolved.append(str(candidate))
                elif candidate.exists():
                    real = str(existing(candidate))
                    require(inside(Path(real), bundle), f"dependency escaped bundle: {dep}")
                    if real in measured:
                        resolved.append(real)
            require(resolved, f"active dependency has no measured resolution: {path}: {dep}")
            witness.append({"image": path, "dependency": dep, "resolved_candidates": sorted(set(resolved))})
    return witness


def _run_probe(build_record, renamed):
    native_only()
    record_path = existing(build_record)
    record = json.loads(record_path.read_text())
    require(record["status"] == "assembled-not-launched", "invalid build record")
    app = existing(record["bundle"])
    require(file_digest(app / "Contents/MacOS/ProbeNative") == record["native_sha256"], "native executable changed")
    original_witness = json.loads((record_path.parent / "original-runtime.json").read_text())
    copy_plan = json.loads((record_path.parent / "runtime-copy-plan.json").read_text())
    require(record["original_runtime_digest"] == inventory_digest(original_witness), "original witness digest mismatch")
    require(record["runtime_copy_plan"] == "runtime-copy-plan.json"
            and record["retained_runtime_digest"] == copy_plan["retained_inventory_digest"],
            "build record runtime-copy witness mismatch")
    require(record["static_loader_context_pending"] == [], "assembly has unresolved loader references; no launch")
    verify_isolated_runtime(app / "Contents/Resources/runtime", original_witness, copy_plan)
    # Nothing native is launched, including a handler query, before both audits.
    refuse_claims(nested_claims(app))
    require(not check_dependency_paths(app, macho_inventory(app)), "unresolved loader references; no launch")
    destination = fresh_leaf(renamed, ".app")
    require(not inside(destination, app) and not inside(app, destination), "invalid relocation overlap")
    require(not inside(destination, Path(record["original_runtime"])), "relocation is inside original runtime")
    require(not inside(destination, HERE), "relocation is inside probe source")
    original = Path(record["original_runtime"])
    original_before = inventory(original) if original.exists() else None
    require(original_before is None or original_before == original_witness, "original runtime changed since assembly")
    observations = []
    current = app
    for index in range(2):
        if index:
            current.rename(destination)
            current = destination
        verify_isolated_runtime(current / "Contents/Resources/runtime", original_witness, copy_plan)
        refuse_claims(nested_claims(current))
        require(not check_dependency_paths(current, macho_inventory(current)), "unresolved loader references; no launch")
        profile = new_profile(record_path.parent, f"run-profile-{index}")
        runtime = current / "Contents/Resources/runtime"
        before_handler = handler(runtime, profile, "handler-before-launch")
        require(before_handler == record["handler_baseline"], "handler differs from pre-generation baseline")
        before = inventory(current)
        cleanup_certain = True
        try:
            process = bounded_run([str(current / "Contents/MacOS/ProbeBootstrap"), str(profile)], profile, "probe")
            result_file = profile / "result.json"
            require(result_file.stat().st_size <= MAX_OUTPUT, "native report exceeded bound")
            report = json.loads(result_file.read_text())
            verdict = validate_report(report, current, profile, process["pid"])
            machos = macho_inventory(current)
            closure = {
                "gui": loaded_closure(current, report["loaded_images"], current / "Contents/MacOS/ProbeNative", machos, report["loaded_image_snapshot"]),
                "child": loaded_closure(current, report["child"]["loaded_images"], runtime / "bin/racket", machos, report["child"]["loaded_image_snapshot"])}
        except NativeCleanupUncertain:
            cleanup_certain = False
            raise
        finally:
            after = inventory(current)
            after_handler = (handler(runtime, profile, "handler-after-launch") if cleanup_certain
                             else {"status": "unobserved-owned-process-group-cleanup-uncertain"})
            witness = {"schema": 1, "bundle_unchanged": after == before,
                       "bundle_before_digest": inventory_digest(before),
                       "bundle_after_digest": inventory_digest(after),
                       "handler_before": before_handler, "handler_after": after_handler,
                       "owned_process_group_cleanup_certain": cleanup_certain}
            dump_new(profile / "post-launch-witness.json", witness)
            require(after == before, "bundle mutated during probe")
            if cleanup_certain:
                require(after_handler == before_handler, "global .rkt handler changed during launch")
        observations.append({"profile": str(profile), "verdict": verdict, "report": report,
                             "active_non_system_dylib_closure": closure,
                             "bundle_inventory_digest": inventory_digest(before)})
    if original_before is not None:
        require(inventory(original) == original_before, "original runtime changed during launch")
    # Compare package/config content hashes, rather than serializing path equality
    # across relocation. A full JSON path witness is retained for both locations.
    a, b = [o["report"] for o in observations]
    for name in a["modules"]:
        require(a["modules"][name]["sha256"] == b["modules"][name]["sha256"], "module content changed after rename")
    for name in ("config_file", "links_file", "package_database"):
        require(a["paths"][name]["sha256"] == b["paths"][name]["sha256"], "metadata content changed after rename")
    result = {"schema": 1, "status": "bounded-path-probe-passed", "observations": observations,
              "original_runtime_present": original_before is not None,
              "recorded_original_runtime_absent": original_before is None,
              "clean_destination_tested": False,
              "initially_unset_handler_tested": record["handler_baseline"].get("default_handler") is None,
              "full_distribution_acceptance": False,
              "unresolved_static_loader_context": record["static_loader_context_pending"]}
    dump_new(record_path.parent / "native-summary.json", result)
    return result


def run_probe(build_record, renamed):
    native_only()
    record_path = existing(build_record)
    require(not (record_path.parent / "launch-protected-input-witness.json").exists(),
            "this build already has a launch attempt; inspect it, then use a fresh build")
    record = json.loads(record_path.read_text())
    original = Path(record["original_runtime"])
    original_before = inventory(original) if original.exists() else None
    source_before = inventory(HERE)
    try:
        return _run_probe(record_path, renamed)
    finally:
        original_after = inventory(original) if original.exists() else None
        source_after = inventory(HERE)
        witness = {"schema": 1,
                   "original_runtime_unchanged": original_before == original_after,
                   "original_runtime_before": inventory_digest(original_before) if original_before is not None else None,
                   "original_runtime_after": inventory_digest(original_after) if original_after is not None else None,
                   "source_unchanged": source_before == source_after,
                   "source_before": inventory_digest(source_before),
                   "source_after": inventory_digest(source_after)}
        dump_new(record_path.parent / "launch-protected-input-witness.json", witness)
        require(witness["original_runtime_unchanged"] and witness["source_unchanged"], "protected input changed during native probe")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit-runtime", help="read-only inventory, nested claims, Mach-O paths")
    audit.add_argument("runtime", type=Path)
    audit.add_argument("--output", type=Path, required=True, help="fresh local JSON outside runtime/source; never uploaded")
    build_cmd = commands.add_parser("build", help="native compile/generation; separately authorized macOS only")
    build_cmd.add_argument("--runtime", type=Path, required=True)
    build_cmd.add_argument("--work", type=Path, required=True)
    build_cmd.add_argument("--expected-runtime-digest", required=True)
    run = commands.add_parser("run", help="two bounded native observations, including rename/relocation")
    run.add_argument("--build-record", type=Path, required=True)
    run.add_argument("--renamed", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "audit-runtime":
        output = fresh_leaf(args.output)
        require(not inside(output, existing(args.runtime)) and not inside(output, HERE),
                "audit output must be outside runtime and probe source")
        inv = inventory(args.runtime)
        rows = macho_inventory(args.runtime)
        data = {"schema": 1, "inventory_digest": inventory_digest(inv), "inventory": inv,
                "nested_apps": nested_claims(args.runtime), "macho": rows,
                "static_loader_context_pending": check_dependency_paths(args.runtime, rows)}
        dump_new(output, data)
        summary = {"status": "audited-not-executed", "output": str(output),
                   "inventory_digest": data["inventory_digest"], "entry_count": len(inv),
                   "macho_count": len(rows), "plist_count": len(data["nested_apps"]),
                   "declarations_block_launch": any(r["declarations"] for r in data["nested_apps"])}
    elif args.command == "build":
        data = build(args.runtime, args.work, args.expected_runtime_digest)
        summary = {"status": data["status"], "build_record": str(args.work / "build.json"),
                   "native_launch_blocked_by_declarations": data["native_launch_blocked_by_declarations"],
                   "native_launch_blocked_by_loader_context": data["native_launch_blocked_by_loader_context"]}
    else:
        data = run_probe(args.build_record, args.renamed)
        summary = {key: data[key] for key in ("status", "recorded_original_runtime_absent",
                                             "clean_destination_tested", "initially_unset_handler_tested",
                                             "full_distribution_acceptance")}
        summary["native_summary"] = str(args.build_record.parent / "native-summary.json")
    # CLI prints compact facts only. Detailed manifests/reports stay local;
    # no runtime inventory or binary is streamed into CI logs or uploaded.
    text = json.dumps(summary, ensure_ascii=False, sort_keys=True)
    require(len(text.encode()) <= 16384, "compact summary exceeded 16 KiB")
    print(text)


if __name__ == "__main__":
    try:
        main()
    except (Refusal, OSError, KeyError, ValueError) as exc:
        print(json.dumps({"schema": 1, "status": "refused", "error": str(exc)}), file=sys.stderr)
        sys.exit(1)
