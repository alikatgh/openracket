"""Parser-only synthetic records. These tests do not run or emulate a GUI/lexer,
and are not native correctness evidence. No result artifact is promoted."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import compare as c

def style(index=0, name="Basic", join=False):
    delta = {k: "base" for k in c.DELTA_SYMBOLS}
    delta.update({k: False for k in c.DELTA_BOOLS})
    delta.update({k: [1, 1, 1, 1] for k in c.DELTA_COLORS})
    delta.update({"get-face": False, "get-size-mult": 1, "get-size-add": 0})
    appearance = {k: "normal" for k in c.APPEAR_SYMBOLS}
    appearance.update({k: False for k in c.APPEAR_BOOLS})
    appearance.update({"get-face": False, "get-size": 12, "foreground": [0,0,0,1], "background": [255,255,255,1]})
    return {"index": index, "name": name, "base": False if index == 0 else 0,
            "join": join, "shift": 1 if join else False, "delta": delta, "appearance": appearance}

def string_snip(value, start, ref):
    return {"kind": "string", "position": start, "count": len(value), "class": "wxtext",
            "version": 3, "flags": [], "style": ref, "text": value}

def document(value="ab", styles=None, refs=None):
    styles = copy.deepcopy(styles or [style(), style(1, "named")])
    refs = refs or [1] * len(value)
    return {"kind": "text", "text": value, "flattened": value, "length": len(value),
            "styles": styles, "position_styles": refs,
            "snips": [string_snip(char, i, refs[i]) for i, char in enumerate(value)]}

def lexed(edited=False):
    source = c.EDITED if edited else c.ORIGINAL
    styles = [style()] + [style(i, "framework:syntax-color:scheme:" + name)
                         for i, name in enumerate(("string", "parenthesis", "constant"), 1)]
    refs = [0] * len(source)
    target = c.ORIGINAL.index('"λ"')
    refs[target] = 2 if edited else 1
    if edited:
        refs[target+1] = 3
    doc = document(source, styles, refs)
    types = {0: "other", 1: "string", 2: "parenthesis", 3: "constant"}
    tokens = [{"position": i, "type": types[r], "start": i, "end": i+1, "style": r}
              for i, r in enumerate(refs)]
    navigation = [{"position": i, "forward": False, "backward": False} for i in range(len(source)+1)]
    if edited:
        navigation[target]["forward"] = target+5
        navigation[target+5]["backward"] = target
    return {"document": doc, "tokens": tokens, "navigation": navigation, "lexer_valid": True}

def rich():
    styles = [style(), style(1, "fixture:深蓝λ"), style(2, False, True)]
    d = document("head café|tail λ", styles)
    cursor = d["length"]
    common = {"count": 1, "version": 4, "flags": [], "style": 1}
    image = dict(common, position=cursor, kind="image", **{"class": "wximage"},
                 bitmap={"width": 3, "height": 2, "argb": [255,255,0,0,255,0,255,0,255,0,0,255,255,12,34,56,255,78,90,123,255,210,220,230]}, mask=False)
    embedded = dict(common, position=cursor+1, kind="editor", **{"class": "wxmedia"},
                    editor=document("nested λ café", styles), shared_style_list=True,
                    border=True, margin=[2,3,4,5], inset=[1,2,3,4],
                    min_width=40, max_width=240, min_height=20, max_height=100,
                    tight_text_fit=False, align_top_line=False)
    d["snips"] += [image, embedded]
    d["length"] += 2
    d["text"] += ".."
    d["flattened"] += ".."
    d["position_styles"] += [1,1]
    return d

def capture(mode):
    v = {"schema": c.SCHEMA, "mode": mode, "passed": True, "stages": c.STAGES[:],
         "gui_callback_errors": [],
         "runtime": {"racket_version": "9.3", "source": "/parser-only/fixture/style.rkt",
                     "source_sha256": c.STOCK_SHA if mode.startswith("stock") else c.CANDIDATE_SHA,
                     "flag": {"on": "1", "off": "0"}.get(mode), "source_first_load": True},
         "dependencies": [{"module":m,"source":"/parser-only/"+m+".rkt","sha256":sha}
                          for m,sha in c.DEPENDENCY_PINS.items()],
         "activation": {"enabled": None if mode.startswith("stock") else mode=="on",
                        "export_status": "missing" if mode.startswith("stock") else "present",
                        "module_already_loaded": True},
         "initial": lexed(), "edited": lexed(True), "edited_final": lexed(True),
         "lexer_transitions": [False,True,False,True],
         "identity": {k: True for k in ("private_style_compatible","public_style_compatible","canvas_editor_same","handler_thread")},
         "wxme": {"format":"standard", "bytes":1000, "save_snip_identities":True,
                  "save_style_identities":True, "save_bitmap_identity":True, "save_nested_editor_identity":True}}
    for k in ("rich_before", "rich_after_save", "rich_restored", "rich_final"):
        v[k] = rich()
    for i, k in enumerate(("diagnostics_before","diagnostics_initial","diagnostics_edited","diagnostics_final")):
        v[k] = None if mode.startswith("stock") else {
            "enabled": mode=="on", "cache-valid": mode=="on", "member-count":4,
            "lookups":10+i*10 if mode=="on" else 0, "hits":8+i*8 if mode=="on" else 0,
            "rebuilds":2 if mode=="on" else 0, "members-traversed":8 if mode=="on" else 0,
            "named-entries":4 if mode=="on" else 0}
    return v

class TypedComparison(unittest.TestCase):
    def test_synthetic_schema_sample(self):
        self.assertTrue(c.compare({m:capture(m) for m in c.MODES})["passed"])
    def test_huge_number_reports_typed_failure(self):
        with self.assertRaises(c.GateError): c.number(10**400,"huge")
    def test_stale_cache_is_observed_not_a_correctness_failure(self):
        v=capture("on"); v["diagnostics_final"]["cache-valid"]=False
        c.validate(v,"on")
    def test_missing_arm_rejected(self):
        with self.assertRaises(c.GateError):
            c.compare({"stock":capture("stock")})
    def test_bool_is_not_integer_identity(self):
        for value in (False, True, 1.0, -1):
            d=document(); d["position_styles"][0]=value
            with self.subTest(value=value), self.assertRaises(c.GateError):
                c.document(d,"document")
    def test_bool_not_numeric_color(self):
        d=document(); d["styles"][0]["appearance"]["foreground"][0]=False
        with self.assertRaises(c.GateError): c.document(d,"document")
    def test_false_and_zero_references_are_distinct(self):
        with self.assertRaises(c.GateError): c.equal_typed({"base":False},{"base":0},"style")
    def test_real_numeric_exactness_allowed(self):
        a=document(); b=copy.deepcopy(a)
        b["styles"][0]["delta"]["get-size-mult"]=1.0
        c.document(a,"a"); c.document(b,"b"); c.equal_typed(a,b,"roundtrip")
    def test_equal_attributes_do_not_erase_identity(self):
        a=document(); b=copy.deepcopy(a)
        b["styles"].append(style(2,"named"))
        b["position_styles"][1]=2
        b["snips"][1]["style"]=2
        c.document(a,"a"); c.document(b,"b")
        with self.assertRaises(c.GateError): c.equal_typed(a,b,"roundtrip")
    def test_style_order_never_sorted(self):
        a=document(); a["styles"].append(style(2,"second")); b=copy.deepcopy(a)
        b["styles"][1],b["styles"][2]=b["styles"][2],b["styles"][1]
        with self.assertRaises(c.GateError): c.document(b,"b")
    def test_snip_order_never_sorted(self):
        a=document(); a["snips"].reverse()
        with self.assertRaises(c.GateError): c.document(a,"a")
    def test_flag_order_retained(self):
        a=document(); a["snips"][0]["flags"]=["a","b"]; b=copy.deepcopy(a)
        b["snips"][0]["flags"].reverse()
        with self.assertRaises(c.GateError): c.equal_typed(a,b,"flags")
    def test_full_gate_rejects_mutations(self):
        mutations = {
            "runtime pin": lambda v:v["runtime"].update(source_sha256="0"*64),
            "wrong mode": lambda v:v.update(mode="on"),
            "failed": lambda v:v.update(passed=False),
            "failure": lambda v:v.update(failure={"message":"boom"}),
            "async callback": lambda v:v["gui_callback_errors"].append({"message":"callback failed"}),
            "stage omitted": lambda v:v["stages"].pop(),
            "activation": lambda v:v["activation"].update(enabled=True),
            "source first": lambda v:v["runtime"].update(source_first_load=False),
            "dependency pin": lambda v:v["dependencies"][0].update(sha256="0"*64),
            "dependency missing": lambda v:v["dependencies"].pop(),
            "top unknown field": lambda v:v.update(ignored="not allowed"),
            "lexer pending": lambda v:v["edited"].update(lexer_valid=False),
            "missing position": lambda v:v["initial"]["tokens"].pop(),
            "token geometry": lambda v:v["initial"]["tokens"][0].update(end=0),
            "paren mismatch": lambda v:v["edited"]["navigation"][c.ORIGINAL.index('"λ"')].update(forward=False),
            "final style change": lambda v:v["edited_final"]["document"]["styles"][0]["appearance"].update(**{"get-size":13}),
            "nested text": lambda v:v["rich_restored"]["snips"][-1]["editor"].update(text="wrong"),
            "style delta": lambda v:v["rich_restored"]["styles"][0]["delta"].update(**{"get-size-add":4}),
            "pixel": lambda v:v["rich_restored"]["snips"][-2]["bitmap"]["argb"].__setitem__(1,0),
            "geometry": lambda v:v["rich_restored"]["snips"][-1]["margin"].__setitem__(0,3),
            "shared alias": lambda v:v["rich_restored"]["snips"][-1].update(shared_style_list=False),
            "save identity": lambda v:v["wxme"].update(save_snip_identities=False),
            "new unknown snip": lambda v:v["rich_restored"]["snips"][-1].update(kind="other"),
            "unknown field": lambda v:v["rich_restored"].update(ignored="not allowed"),
            "disabled index work": lambda v:v["diagnostics_final"].update(lookups=1),
        }
        for name, mutate in mutations.items():
            v=capture("off"); mutate(v)
            with self.subTest(name=name), self.assertRaises(c.GateError): c.validate(v,"off")
    def test_workload_hits_cannot_be_synthetic_final_lookup(self):
        v=capture("on")
        v["diagnostics_edited"]=copy.deepcopy(v["diagnostics_initial"])
        with self.assertRaises(c.GateError): c.validate(v,"on")
    def test_stock_order_instability_blocks_all_acceptance(self):
        captures={m:capture(m) for m in c.MODES}
        captures["stock-again"]["wxme"]["bytes"]+=1
        with self.assertRaisesRegex(c.GateError,"stock_vs_stock-again"): c.compare(captures)
    def test_candidate_parity_failure_reports_path(self):
        captures={m:capture(m) for m in c.MODES}
        for key in ("initial","edited","edited_final"):
            captures["on"][key]["document"]["styles"][0]["appearance"]["get-size"]=13
        with self.assertRaisesRegex(c.GateError,r"stock_vs_on.initial.document.styles\[0\].appearance.get-size"):
            c.compare(captures)

if __name__=="__main__": unittest.main()
