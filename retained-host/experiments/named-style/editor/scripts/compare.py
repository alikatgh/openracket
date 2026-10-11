#!/usr/bin/env python3
"""Fail-closed typed, ORDERED editor/WXME comparison. Never runs native code."""
from __future__ import annotations
import argparse
import json
import math
import traceback
from pathlib import Path

SCHEMA = "openracket-named-style-editor-v1"
STOCK_SHA = "2e06742f956c3de50847bbb429c400af78303c68e0deba1ebc865a619534bde0"
CANDIDATE_SHA = "74eb24f0d6485187c9700cca421f4299dee67ea092a811d56b737972b2204c6d"
MODES = ("stock", "stock-again", "off", "on")
DEPENDENCY_PINS = {
    "framework/private/color": "da45ea64a5a0b413296a60ebe61d3e5ee69a27b53a6f1e13ae258701bdce1578",
    "framework/private/racket": "fd3ada7890a54f715fc0c7369993d59902fb079a43b00c83a1d5fbd2f0fe4520",
    "mred/private/wxme/editor": "63987762c560c5b3b3d4f087e66bb68b3fba3a8aabb7d897bfcb09994391a144",
    "mred/private/wxme/editor-snip": "055f9bd6bdcbbf6712c25dd0ee66b195d0c1a2dbb61ed05da041526c61047049",
    "mred/private/wxme/editor-snip-class": "c0a82e707983738c5b5d76256caecc283993097b7903101f2500e5bf08513f62",
}
ORIGINAL = '#lang racket/base\n(define café "λ")\n(define (bump x) (+ x 41))\n; comment ☃\n(bump 1)\n'
EDITED = ORIGINAL.replace('"λ"', '[1 2]')
STAGES = ["source-pin-verified", "gui-imported-same-runtime-module", "actual-editor-created",
          "initial-lexer-readback", "edited-lexer-readback", "rich-saved-with-identities",
          "final-gui-readback"]
DIAG_KEYS = {"enabled", "lookups", "hits", "rebuilds", "members-traversed", "cache-valid", "named-entries", "member-count"}
DELTA_SYMBOLS = {"get-family", "get-weight-on", "get-weight-off", "get-style-on", "get-style-off", "get-smoothing-on", "get-smoothing-off", "get-alignment-on", "get-alignment-off"}
DELTA_BOOLS = {"get-underlined-on", "get-underlined-off", "get-size-in-pixels-on", "get-size-in-pixels-off", "get-transparent-text-backing-on", "get-transparent-text-backing-off"}
DELTA_COLORS = {"foreground-mult", "foreground-add", "background-mult", "background-add"}
APPEAR_SYMBOLS = {"get-family", "get-weight", "get-style", "get-smoothing", "get-alignment"}
APPEAR_BOOLS = {"get-underlined", "get-size-in-pixels", "get-transparent-text-backing"}
SEMANTIC_KEYS = ("fixture_search", "initial", "edited", "edited_final", "lexer_transitions", "identity", "rich_before",
                 "rich_after_save", "rich_restored", "rich_final", "wxme")

class GateError(ValueError):
    pass

def require(condition, path, message):
    if not condition:
        raise GateError(f"{path}: {message}")

def keys(obj, expected, path):
    require(type(obj) is dict, path, "expected object")
    require(set(obj) == set(expected), path, f"fields {sorted(obj)} != {sorted(expected)}")

def integer(v, path, low=0, high=1024):
    require(type(v) is int and low <= v <= high, path, f"expected integer in [{low}, {high}], got {v!r}")

def number(v, path):
    try:
        finite = type(v) in (int, float) and math.isfinite(v)
    except (OverflowError, ValueError):
        finite = False
    require(finite, path, "expected finite real, never boolean")

def boolean(v, path):
    require(type(v) is bool, path, "expected boolean")

def text(v, path, false=False):
    require(type(v) is str or (false and v is False), path, "expected string" + (" or false" if false else ""))

def ref(v, count, path, false=False):
    if false and v is False:
        return
    integer(v, path, 0, count - 1)

def array(v, path, bound=1024):
    require(type(v) is list and len(v) <= bound, path, "expected bounded ordered array")

def channels(v, path):
    array(v, path, 4)
    require(len(v) == 4, path, "four ordered color channels required")
    for i, x in enumerate(v):
        number(x, f"{path}[{i}]")

def style(v, i, count, path):
    keys(v, {"index", "name", "base", "join", "shift", "delta", "appearance"}, path)
    integer(v["index"], path + ".index")
    require(v["index"] == i, path, "style array must preserve exact public index order")
    text(v["name"], path + ".name", True)
    ref(v["base"], count, path + ".base", True)
    boolean(v["join"], path + ".join")
    ref(v["shift"], count, path + ".shift", True)
    require((v["shift"] is not False) == v["join"], path, "join/shift identity disagrees")
    require((v["base"] is False) == (i == 0), path, "only Basic has no base")
    if i == 0:
        require(v["name"] == "Basic", path, "index zero must be Basic")
    d = v["delta"]
    keys(d, DELTA_SYMBOLS | DELTA_BOOLS | DELTA_COLORS | {"get-face", "get-size-mult", "get-size-add"}, path + ".delta")
    for k in DELTA_SYMBOLS:
        text(d[k], path + ".delta." + k)
    for k in DELTA_BOOLS:
        boolean(d[k], path + ".delta." + k)
    for k in DELTA_COLORS:
        channels(d[k], path + ".delta." + k)
    text(d["get-face"], path + ".delta.get-face", True)
    number(d["get-size-mult"], path + ".delta.get-size-mult")
    integer(d["get-size-add"], path + ".delta.get-size-add", -10000, 10000)
    a = v["appearance"]
    keys(a, APPEAR_SYMBOLS | APPEAR_BOOLS | {"get-face", "get-size", "foreground", "background"}, path + ".appearance")
    for k in APPEAR_SYMBOLS:
        text(a[k], path + ".appearance." + k)
    for k in APPEAR_BOOLS:
        boolean(a[k], path + ".appearance." + k)
    text(a["get-face"], path + ".appearance.get-face", True)
    number(a["get-size"], path + ".appearance.get-size")
    channels(a["foreground"], path + ".appearance.foreground")
    channels(a["background"], path + ".appearance.background")

def bitmap(v, path):
    keys(v, {"width", "height", "argb"}, path)
    integer(v["width"], path + ".width", 1, 12)
    integer(v["height"], path + ".height", 1, 9)
    array(v["argb"], path + ".argb", 4 * 12 * 9)
    require(len(v["argb"]) == 4 * v["width"] * v["height"], path, "pixel byte count disagrees with geometry")
    for i, x in enumerate(v["argb"]):
        integer(x, f"{path}.argb[{i}]", 0, 255)

def document(v, path, depth=0):
    require(depth <= 1, path, "editor nesting exceeds fixture bound")
    keys(v, {"kind", "text", "flattened", "length", "styles", "position_styles", "snips"}, path)
    require(v["kind"] == "text", path, "genuine text editor expected")
    integer(v["length"], path + ".length")
    text(v["text"], path + ".text")
    text(v["flattened"], path + ".flattened")
    array(v["styles"], path + ".styles")
    require(len(v["styles"]) >= 1, path, "missing actual style graph")
    count = len(v["styles"])
    for i, s in enumerate(v["styles"]):
        style(s, i, count, f"{path}.styles[{i}]")
    array(v["position_styles"], path + ".position_styles")
    require(len(v["position_styles"]) == v["length"], path, "missing per-position style identities")
    for i, x in enumerate(v["position_styles"]):
        ref(x, count, f"{path}.position_styles[{i}]")
    array(v["snips"], path + ".snips")
    cursor = 0
    for i, s in enumerate(v["snips"]):
        p = f"{path}.snips[{i}]"
        common = {"position", "count", "class", "version", "flags", "style", "kind"}
        extra = {"string": {"text"}, "image": {"bitmap", "mask"}, "editor": {
            "editor", "shared_style_list", "border", "margin", "inset", "min_width", "max_width",
            "min_height", "max_height", "tight_text_fit", "align_top_line"}}
        require(type(s) is dict and s.get("kind") in extra, p, "unknown typed snip")
        keys(s, common | extra[s["kind"]], p)
        integer(s["position"], p + ".position")
        integer(s["count"], p + ".count", 0)
        require(s["position"] == cursor, p, "ordered snips must be contiguous")
        cursor += s["count"]
        text(s["class"], p + ".class")
        integer(s["version"], p + ".version", 0, 100000)
        array(s["flags"], p + ".flags", 64)
        for flag in s["flags"]:
            text(flag, p + ".flag")
        ref(s["style"], count, p + ".style")
        require(v["position_styles"][s["position"]:cursor] == [s["style"]] * s["count"], p, "snip style identity disagrees with positions")
        if s["kind"] == "string":
            text(s["text"], p + ".text")
            require(len(s["text"]) == s["count"], p, "string snip content/count mismatch")
        elif s["kind"] == "image":
            require(s["count"] == 1, p, "image is one editor item")
            bitmap(s["bitmap"], p + ".bitmap")
            if s["mask"] is not False:
                bitmap(s["mask"], p + ".mask")
        else:
            require(s["count"] == 1, p, "embedded editor is one editor item")
            document(s["editor"], p + ".editor", depth + 1)
            for k in ("shared_style_list", "border", "tight_text_fit", "align_top_line"):
                boolean(s[k], p + "." + k)
            if s["shared_style_list"]:
                equal_typed(v["styles"], s["editor"]["styles"], p + ".shared_styles")
            for k in ("margin", "inset"):
                array(s[k], p + "." + k, 4)
                require(len(s[k]) == 4, p, "four margin/inset sides required")
                for x in s[k]:
                    integer(x, p + "." + k)
            for k in ("min_width", "max_width", "min_height", "max_height"):
                if s[k] != "none":
                    number(s[k], p + "." + k)
    require(cursor == v["length"], path, "snips must cover complete editor content")

def lexed(v, expected, path):
    keys(v, {"document", "tokens", "navigation", "lexer_valid"}, path)
    require(v["lexer_valid"] is True, path, "lexer must be complete")
    document(v["document"], path + ".document")
    n = len(expected)
    require(v["document"]["text"] == expected and v["document"]["length"] == n, path, "actual fixture source mismatch")
    array(v["tokens"], path + ".tokens")
    require(len(v["tokens"]) == n, path, "missing exact per-position tokens")
    for i, token in enumerate(v["tokens"]):
        p = f"{path}.tokens[{i}]"
        keys(token, {"position", "type", "start", "end", "style"}, p)
        for k in ("position", "start", "end", "style"):
            integer(token[k], p + "." + k)
        require(token["position"] == i and 0 <= token["start"] <= i < token["end"] <= n, p, "token geometry invalid")
        text(token["type"], p + ".type")
        require(token["style"] == v["document"]["position_styles"][i], p, "token style does not refer to actual snip")
    array(v["navigation"], path + ".navigation", 1025)
    require(len(v["navigation"]) == n + 1, path, "missing paren/navigation graph")
    for i, nav in enumerate(v["navigation"]):
        p = f"{path}.navigation[{i}]"
        keys(nav, {"position", "forward", "backward"}, p)
        integer(nav["position"], p + ".position")
        require(nav["position"] == i, p, "navigation reordered")
        for k in ("forward", "backward"):
            if nav[k] is not False:
                integer(nav[k], p + "." + k, 0, n)

def equal_typed(a, b, path):
    """After schema validation, real numeric fields may change exactness only.
    Bool != integer. Arrays retain order, references, geometry and all strings.
    """
    if type(a) in (int, float) and type(b) in (int, float):
        require(a == b, path, f"numeric value differs: {a!r} != {b!r}")
    elif type(a) is dict and type(b) is dict:
        require(set(a) == set(b), path, "field set differs")
        for k in a:
            equal_typed(a[k], b[k], path + "." + k)
    elif type(a) is list and type(b) is list:
        require(len(a) == len(b), path, "ordered array length differs")
        for i, (x, y) in enumerate(zip(a, b)):
            equal_typed(x, y, f"{path}[{i}]")
    else:
        require(type(a) is type(b) and a == b, path, f"typed value differs: {a!r} != {b!r}")

def fixture_search(v, path):
    keys(v, {"query", "absent_query", "text_length", "selection_start", "selection_end",
             "target", "default_target", "eof_target", "absent_target", "found_text"}, path)
    query = '"λ"'
    absent_query = '"OPENRACKET_ABSENT_λ"'
    for key in ("text_length", "selection_start", "selection_end", "target"):
        integer(v[key], path + "." + key)
    for key, expected in (("query", query), ("absent_query", absent_query), ("found_text", query)):
        text(v[key], path + "." + key)
        require(v[key] == expected, path + "." + key, "exact search query/range required")
    for key in ("text_length", "selection_start", "selection_end"):
        require(v[key] == len(ORIGINAL), path + "." + key, "post-insertion caret must be at actual source EOF")
    require(v["target"] == ORIGINAL.index(query), path + ".target", "exact source-derived Unicode character offset required")
    require(ORIGINAL[v["target"]:v["target"] + len(query)] == v["found_text"], path, "found source range differs")
    for key in ("default_target", "eof_target", "absent_target"):
        require(v[key] is False, path + "." + key, "native negative search must return false, never integer zero")

def diagnostics(v, mode, path):
    if mode.startswith("stock"):
        require(v is None, path, "stock must not fabricate diagnostic exports")
        return
    keys(v, DIAG_KEYS, path)
    for k in ("enabled", "cache-valid"):
        boolean(v[k], path + "." + k)
    for k in DIAG_KEYS - {"enabled", "cache-valid"}:
        integer(v[k], path + "." + k, 0, 10**12)
    require(v["member-count"] >= 1, path, "actual editor style list missing")
    require(v["enabled"] is (mode == "on"), path, "diagnostic activation mismatch")
    if mode == "off":
        require(all(v[k] == 0 for k in ("lookups", "hits", "rebuilds", "members-traversed", "named-entries")), path, "disabled branch performed index work")
        require(v["cache-valid"] is False, path, "disabled branch has cache")

def validate(v, mode):
    p = mode
    require(type(v) is dict and v.get("schema") == SCHEMA and v.get("mode") == mode, p, "wrong capture schema/mode")
    require(v.get("passed") is True and "failure" not in v, p, f"native fixture did not succeed: {v.get('failure')!r}")
    required = set(SEMANTIC_KEYS) | {"schema", "mode", "passed", "stages", "runtime", "activation",
                                     "dependencies", "gui_callback_errors", "diagnostics_before", "diagnostics_initial",
                                     "diagnostics_edited", "diagnostics_final"}
    keys(v, required, p)
    require(v["gui_callback_errors"] == [], p, "asynchronous GUI callback failures were reported")
    require(v.get("stages") == STAGES, p, "missing ordered native completion stages")
    array(v["dependencies"], p + ".dependencies", len(DEPENDENCY_PINS))
    require(len(v["dependencies"]) == len(DEPENDENCY_PINS), p, "complete official dependency evidence required")
    for dep, (module, sha) in zip(v["dependencies"], DEPENDENCY_PINS.items()):
        keys(dep, {"module", "source", "sha256"}, p + ".dependency")
        require(dep["module"] == module and dep["sha256"] == sha, p, "official GUI dependency pin mismatch")
        text(dep["source"], p + ".dependency.source")
    runtime = v["runtime"]
    keys(runtime, {"racket_version", "source", "source_sha256", "flag", "source_first_load"}, p + ".runtime")
    require(runtime["racket_version"] == "9.3" and runtime["source_first_load"] is True, p, "actual source-first 9.3 runtime required")
    text(runtime["source"], p + ".runtime.source")
    require(runtime["source_sha256"] == (STOCK_SHA if mode.startswith("stock") else CANDIDATE_SHA), p, "source pin mismatch")
    require(runtime["flag"] == ({"off": "0", "on": "1"}.get(mode)), p, "exact flag mismatch")
    act = v["activation"]
    keys(act, {"enabled", "export_status", "module_already_loaded"}, p + ".activation")
    require(act["module_already_loaded"] is True, p, "module was not already loaded")
    require(act["export_status"] == ("missing" if mode.startswith("stock") else "present"), p, "export availability mismatch")
    require(act["enabled"] is (None if mode.startswith("stock") else mode == "on"), p, "export activation mismatch")
    fixture_search(v["fixture_search"], p + ".fixture_search")
    for name, expected in (("initial", ORIGINAL), ("edited", EDITED), ("edited_final", EDITED)):
        lexed(v[name], expected, p + "." + name)
    equal_typed(v["edited"], v["edited_final"], p + ".final_lexer_stability")
    target = ORIGINAL.index('"λ"')
    def at(name, pos, token_type):
        snap = v[name]
        tok = snap["tokens"][pos]
        require(tok["type"] == token_type, p, "expected genuine fixture token classification")
        require(snap["document"]["styles"][tok["style"]]["name"] == "framework:syntax-color:scheme:" + token_type, p, "actual framework named color missing")
    at("initial", target, "string")
    at("edited", target, "parenthesis")
    at("edited", target + 1, "constant")
    require(v["edited"]["navigation"][target]["forward"] == target + 5 and v["edited"]["navigation"][target + 5]["backward"] == target, p, "real edited bracket geometry missing")
    transitions = v["lexer_transitions"]
    array(transitions, p + ".lexer_transitions", 16)
    for x in transitions:
        boolean(x, p + ".lexer_transitions")
    require(len(transitions) >= 4 and transitions[-2:] == [False, True], p, "missing actual invalidation/revalidation")
    keys(v["identity"], {"private_style_compatible", "public_style_compatible", "canvas_editor_same", "handler_thread"}, p + ".identity")
    require(all(x is True for x in v["identity"].values()), p, "actual GUI/module identity proof missing")
    for name in ("rich_before", "rich_after_save", "rich_restored", "rich_final"):
        document(v[name], p + "." + name)
    # This requires exact serialized style index order, alias graph, snip
    # order/types, nesting and all attributes. Nothing gets sorted or dropped.
    for name in ("rich_after_save", "rich_restored", "rich_final"):
        equal_typed(v["rich_before"], v[name], p + ".roundtrip." + name)
    rich = v["rich_before"]
    images = [s for s in rich["snips"] if s["kind"] == "image"]
    embedded = [s for s in rich["snips"] if s["kind"] == "editor"]
    require(len(images) == len(embedded) == 1, p, "rich fixture must retain one image and one embedded editor")
    require(images[0]["bitmap"] == {"width": 3, "height": 2, "argb": [255,255,0,0,255,0,255,0,255,0,0,255,255,12,34,56,255,78,90,123,255,210,220,230]}, p, "exact image geometry/pixels differ")
    require(embedded[0]["editor"]["text"] == "nested λ café", p, "nested Unicode content differs")
    require(embedded[0]["margin"] == [2,3,4,5] and embedded[0]["inset"] == [1,2,3,4], p, "embedded geometry differs")
    require(embedded[0]["shared_style_list"] is True, p, "nested style alias graph changed")
    require(any(s["join"] for s in rich["styles"]), p, "join style graph not exercised")
    ref_a, ref_b = rich["position_styles"][0], rich["position_styles"][10]
    require(ref_a == ref_b and rich["styles"][ref_a]["name"] == "fixture:深蓝λ", p, "repeated exact named style identity missing")
    wx = v["wxme"]
    keys(wx, {"format", "bytes", "save_snip_identities", "save_style_identities", "save_bitmap_identity", "save_nested_editor_identity"}, p + ".wxme")
    require(wx["format"] == "standard", p, "WXME standard format required")
    integer(wx["bytes"], p + ".wxme.bytes", 1, 256*1024)
    require(all(wx[k] is True for k in wx if k.startswith("save_")), p, "save altered actual object identities")
    diag_names = ("diagnostics_before", "diagnostics_initial", "diagnostics_edited", "diagnostics_final")
    for name in diag_names:
        diagnostics(v[name], mode, p + "." + name)
    if mode == "on":
        for previous, current in zip(diag_names, diag_names[1:]):
            a, b = v[previous], v[current]
            for k in ("lookups", "hits", "rebuilds", "members-traversed"):
                require(b[k] >= a[k], p, "serial diagnostic counter regressed")
        for name, previous in (("diagnostics_initial", "diagnostics_before"), ("diagnostics_edited", "diagnostics_initial")):
            require(v[name]["lookups"] > v[previous]["lookups"] and v[name]["hits"] > v[previous]["hits"], p, "genuine initial/edit workload performed no named-style lookups/hits")
        d = v["diagnostics_final"]
        require(d["rebuilds"] > 0 and d["members-traversed"] > 0 and d["named-entries"] > 0, p, "actual editor cold/cache evidence missing")
        # cache-valid is observed, never a correctness precondition: a final
        # anonymous style insertion can legitimately invalidate the cache.
    return {k: v[k] for k in SEMANTIC_KEYS}

def compare(captures):
    require(set(captures) == set(MODES), "captures", "all four independent captures are mandatory")
    meanings = {mode: validate(captures[mode], mode) for mode in MODES}
    # Stock-again is first. Natural ordering variance blocks acceptance; this
    # comparator never responds by sorting/dropping mismatching observations.
    for mode in MODES[1:]:
        equal_typed(meanings["stock"], meanings[mode], "stock_vs_" + mode)
    return {"schema": "openracket-named-style-editor-comparison-v1", "passed": True,
            "modes": list(MODES), "comparison": "typed-ordered-full-editor-and-rich-style-graph",
            "native_executed": True, "performance_claim": False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for mode in MODES:
        p.add_argument("--" + mode, required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = vars(p.parse_args())
    result = {"schema": "openracket-named-style-editor-comparison-v1", "passed": False}
    try:
        result = compare({mode: json.loads(a[mode.replace('-', '_')].read_text()) for mode in MODES})
    except BaseException:
        result["failure"] = traceback.format_exc()
    finally:
        a["output"].write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    return 0 if result["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
