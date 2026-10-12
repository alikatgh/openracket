#!/usr/bin/env python3
"""Scope-selection regression for the real setup shell; never install a package."""
import json,os,re,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RACKET=os.environ.get('RACKET','/workspace/shared/racket-toolchain/racket/bin/racket')
class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='openracket-dependencies-')
        self.root=Path(self.tmp.name)/'proof';(self.root/'scripts').mkdir(parents=True)
        for name in ('setup-openracket.sh','proof-env.sh'):
            shutil.copy2(ROOT/'scripts'/name,self.root/'scripts'/name)
        self.log=Path(self.tmp.name)/'calls.jsonl'
        self.fake=Path(self.tmp.name)/'fake-racket'
        self.fake.write_text('''#!/usr/bin/env python3
import json,os,sys
a=sys.argv[1:]
with open(os.environ['FAKE_CALLS'],'a') as out: out.write(json.dumps(a)+'\\n')
if '-e' in a:
 code=a[a.index('-e')+1]
 if '(version)' in code: print('9.3',end='')
 elif '(display "available")' in code:
  package=a[-1]
  if package==os.environ.get('FAKE_BROKEN'): sys.exit(7)
  print('available' if package in json.loads(os.environ['FAKE_AVAILABLE']) else 'missing',end='')
 # The later GUI-directory probe deliberately returns absent, ending the fixture
 # before any real copy, applier or tool registration could be reached.
 sys.exit(0)
sys.exit(0)
''')
        self.fake.chmod(0o755)
    def tearDown(self): self.tmp.cleanup()
    def setup(self,available,broken=''):
        env=dict(os.environ,RACKET=str(self.fake),FAKE_CALLS=str(self.log),
                 FAKE_AVAILABLE=json.dumps(available),FAKE_BROKEN=broken)
        result=subprocess.run(['sh',str(self.root/'scripts/setup-openracket.sh'),'--install'],
             env=env,capture_output=True,text=True,timeout=10)
        calls=[json.loads(line) for line in self.log.read_text().splitlines()]
        installs=[a for a in calls if 'pkg' in a and 'install' in a]
        return result,installs
    def test_full_distribution_requests_no_duplicate_user_packages(self):
        result,installs=self.setup(['drracket','htdp-lib'])
        self.assertEqual(result.returncode,3,result.stderr)
        self.assertIn('gui-lib is missing',result.stderr)
        self.assertEqual(installs,[])
    def test_only_the_missing_package_is_requested(self):
        result,installs=self.setup(['htdp-lib'])
        self.assertEqual(result.returncode,3,result.stderr)
        self.assertEqual([a[-1] for a in installs],['drracket'])
    def test_minimal_runtime_requests_both_packages_from_official_catalog(self):
        result,installs=self.setup([])
        self.assertEqual(result.returncode,3,result.stderr)
        self.assertEqual([a[-1] for a in installs],['drracket','htdp-lib'])
        for args in installs:
            self.assertEqual(args[args.index('--scope')+1],'user')
            self.assertEqual(args[args.index('--catalog')+1],
                             'https://download.racket-lang.org/releases/9.3/catalog/')
    def test_broken_query_fails_closed_without_trying_install(self):
        result,installs=self.setup([],broken='drracket')
        self.assertEqual(result.returncode,7,result.stderr)
        self.assertEqual(installs,[])
    def test_actual_public_query_finds_wider_scope_base(self):
        source=(ROOT/'scripts/setup-openracket.sh').read_text()
        expression=re.search(r"availability=\$\(run_racket -e '([^']+)' --",source).group(1)
        profile=Path(self.tmp.name)/'actual-profile'
        env=dict(os.environ,PLTUSERHOME=str(profile),PLTADDONDIR=str(profile/'addon'))
        result=subprocess.run([RACKET,'-e',expression,'--','base'],env=env,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,'available')
if __name__=='__main__':unittest.main()
