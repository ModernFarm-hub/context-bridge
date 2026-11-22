# SPDX-License-Identifier: Apache-2.0
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout

class WheelBudgetTests(unittest.TestCase):
    def checker(self):
        path=Path(__file__).resolve().parents[2]/'tools/check_artifacts.py'
        spec=importlib.util.spec_from_file_location('artifact_budget_check',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module.check
    def wheel(self,path,extra=None):
        with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_STORED) as z:
            for name in ('imports.py','privacy.py','mcp_server.py','__main__.py'):z.writestr('context_bridge/'+name,'# fixture')
            if extra:z.writestr(*extra)
    def test_small_runtime_wheel_passes_but_size_and_corpus_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);check=self.checker()
            small=root/'small.whl';self.wheel(small)
            with redirect_stdout(io.StringIO()):check(small)
            large=root/'large.whl';self.wheel(large,('payload.txt','x'*500000))
            with self.assertRaisesRegex(ValueError,'size budget'):check(large)
            corpus=root/'corpus.whl';self.wheel(corpus,('context_bridge/evals/savings-real/corpus/v1/doc.rst','fixture'))
            with self.assertRaisesRegex(ValueError,'must not'):check(corpus)
