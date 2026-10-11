import copy
import importlib.util
from pathlib import Path
import unittest
p = Path(__file__).with_name('compare-bindings.py')
s = importlib.util.spec_from_file_location('compare', p)
m = importlib.util.module_from_spec(s);s.loader.exec_module(m)

def row(mode):
    enabled = mode == 'candidate-on'; candidate = mode != 'stock'
    graph = []
    for a,b,c,d in m.EDGES:
        if not graph or graph[-1][0] != [a,b]: graph.append([[a,b]])
        graph[-1].append([c,d])
    sources = {k:{'relative':'share/pkgs/drracket-core-lib/drracket/private/syncheck/'+k+'.rkt','sha256':v}
               for k,v in dict(m.FIXED_PINS,gui=m.PINS['candidate_gui' if candidate else 'stock_gui']).items()}
    state = dict(enabled=enabled,active=False,in_flight=False,exposed=enabled,generation=1,
                 accepted=8 if enabled else 0,duplicates=0,eager_writes=8 if enabled else 0,
                 stock_calls=0 if enabled else 8,pending=0,materializations=0,public_keys=3,
                 indexed_edges=0,cached_starts=0,unsupported_fallbacks=0,failure_fallbacks=0,
                 fallback_reason='public-exposure' if enabled else None) if candidate else None
    return dict(schema='openracket-native-binding-eager-graph/v1',completed=True,mode=mode,
                activation=enabled if candidate else 'unexported',flag=('1' if enabled else '0') if candidate else None,
                runtime_root='/runtime-'+mode,version='9.3',sources=sources,host_sha256=m.PINS['host'],
                workflow_sha256=m.PINS['workflow'],source=m.SOURCE,selection=[1,6],graph=graph,
                edges=copy.deepcopy(m.EDGES),navigation=copy.deepcopy(m.NAVIGATION),eager_witness=state,
                checks=dict.fromkeys(m.CHECKS,True))
def rows(): return {mode:row(mode) for mode in ['stock','candidate-off','candidate-on']}
class Tests(unittest.TestCase):
    def reject(self,change):
        data=rows();change(data['candidate-on'])
        with self.assertRaises(m.Refused):m.compare(data)
    def test_accept_exact_and_do_not_mutate(self):
        data=rows();before=copy.deepcopy(data);self.assertTrue(m.compare(data)['accepted']);self.assertEqual(data,before)
    def test_edge_change(self):self.reject(lambda r:r['edges'][0].__setitem__(2,20))
    def test_full_graph_change(self):self.reject(lambda r:r['graph'][0][1].__setitem__(0,20))
    def test_duplicate(self):self.reject(lambda r:r['graph'][0].append(r['graph'][0][1]))
    def test_missing_zero_span(self):self.reject(lambda r:r['graph'][0].pop(2))
    def test_navigation_change(self):self.reject(lambda r:r['navigation'][0][2].__setitem__(0,26))
    def test_bool_coordinate(self):self.reject(lambda r:r['selection'].__setitem__(0,True))
    def test_bool_counter(self):self.reject(lambda r:r['eager_witness'].__setitem__('materializations',True))
    def test_fallback_vacuity(self):self.reject(lambda r:r['eager_witness'].__setitem__('accepted',0))
    def test_pending_work(self):self.reject(lambda r:r['eager_witness'].__setitem__('pending',1))
    def test_deferred_materialization(self):self.reject(lambda r:r['eager_witness'].__setitem__('materializations',1))
    def test_eager_write_missing(self):self.reject(lambda r:r['eager_witness'].__setitem__('eager_writes',7))
    def test_public_table_incomplete(self):self.reject(lambda r:r['eager_witness'].__setitem__('public_keys',2))
    def test_cached_work_remains(self):self.reject(lambda r:r['eager_witness'].__setitem__('indexed_edges',8))
    def test_in_flight_escape(self):self.reject(lambda r:r['eager_witness'].__setitem__('in_flight',True))
    def test_failed_fast_path(self):self.reject(lambda r:r['eager_witness'].__setitem__('failure_fallbacks',1))
    def test_misclassified_fallback(self):self.reject(lambda r:r['eager_witness'].__setitem__('stock_calls',8))
    def test_wrong_source(self):self.reject(lambda r:r['sources']['xref'].__setitem__('sha256','0'*64))
    def test_path_escape(self):self.reject(lambda r:r['sources']['gui'].__setitem__('relative','../drracket/private/syncheck/gui.rkt'))
    def test_claimed_preservation(self):self.reject(lambda r:r['checks'].__setitem__('table_identity',1))
    def test_wrong_flag(self):self.reject(lambda r:r.__setitem__('flag','0'))
    def test_wrong_fixture(self):self.reject(lambda r:r.__setitem__('source',r['source']+' '))
    def test_ordered_navigation(self):self.reject(lambda r:r['navigation'].reverse())
    def test_missing_arm(self):
        data=rows();data.pop('candidate-off')
        with self.assertRaises(m.Refused):m.compare(data)
    def test_more_metadata(self):self.reject(lambda r:r.__setitem__('unexpected',1))
if __name__=='__main__':unittest.main()
