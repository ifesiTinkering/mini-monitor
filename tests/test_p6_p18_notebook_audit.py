"""Offline regression checks: extract definitions, never execute notebook cells.

No environment file is loaded. All transport and model endpoints are fakes.
Run: uv run --no-sync python -m unittest discover -s tests -p test_p6_p18_notebook_audit.py -v
"""
import ast
import io
import json
import math
import os
import re
import shlex
import subprocess
import tempfile
import time
import unittest
import warnings
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import anyio
import pandas as pd

NOTEBOOK = Path(__file__).resolve().parents[1] / 'src/p6_p18_selfrec_pitch.ipynb'
CELLS = json.loads(NOTEBOOK.read_text())['cells']


def source(index: int) -> str:
    return ''.join(CELLS[index]['source'])


def definitions(index: int, names: list[str], namespace: dict[str, Any]) -> dict[str, Any]:
    """Compile only named definitions, with controlled dependency injection."""
    nodes = [node for node in ast.walk(ast.parse(source(index)))
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    if {node.name for node in nodes} != set(names):
        raise AssertionError(f'Missing definitions: {names}')
    exec(compile(ast.Module(body=nodes, type_ignores=[]), f'cell_{index}_definitions', 'exec'), namespace)
    return namespace


class AuditTests(unittest.TestCase):
    def test_syntax_and_disabled_defaults(self) -> None:
        found = set()
        for index, cell in enumerate(CELLS):
            if cell['cell_type'] != 'code':
                continue
            self.assertEqual(CELLS[index - 1]['cell_type'], 'markdown')
            self.assertIsNone(cell['execution_count'])
            self.assertEqual(cell['outputs'], [])
            tree = ast.parse(source(index))
            compile(source(index), f'cell_{index}', 'exec', flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    if target.id.startswith(('RUN_', 'SMOKE_')) or target.id == 'SMOKE':
                        if target.id not in ('RUN_NAME', 'SMOKE_SIZES'):
                            self.assertIs(ast.literal_eval(node.value), False, target.id)
                            found.add(target.id)
                    if target.id.endswith('_SCRIPT'):
                        compile(ast.literal_eval(node.value), target.id, 'exec')
        self.assertTrue({'RUN_GENERATION', 'RUN_SFT', 'RUN_EVAL', 'RUN_LONG', 'SMOKE_S2'} <= found)

    def test_remote_smoke_permission_does_not_need_model_token(self) -> None:
        ns = dict(re=re, os=SimpleNamespace(environ={}), REMOTE_BASE='/workspace',
                  check_remote_settings=lambda: None,
                  **{flag: False for flag in ('RUN_GENERATION','RUN_SFT','RUN_EVAL','RUN_LONG','SMOKE_S1','SMOKE_S2')})
        definitions(8, ['require_remote'], ns)
        with self.assertRaises(RuntimeError):
            ns['require_remote']()
        for flag in ('SMOKE_S1', 'SMOKE_S2'):
            ns[flag] = True
            ns['require_remote']()
            with self.assertRaises(ValueError):
                ns['require_remote'](token=True)
            ns[flag] = False

    def test_poll_forwards_token_keyword_to_remote_only(self) -> None:
        calls = []
        def remote(command: str, *, token: bool = True) -> str:
            calls.append((command, token))
            return 'JOB_EXIT=0' if 'tail -n' in command else 'gone'
        ns = dict(anyio=anyio, time=time, shlex=shlex, re=re, partial=partial,
                  run_remote=remote, REMOTE='/fake', SESSION='fake')
        definitions(8, ['poll_job'], ns)
        anyio.run(ns['poll_job'], 'prepare', 2)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(token is False for _, token in calls))

    def test_failed_job_is_reported(self) -> None:
        ns = dict(anyio=anyio, time=time, shlex=shlex, re=re, partial=partial,
                  run_remote=lambda *args, **kwargs: 'JOB_EXIT=1', REMOTE='/fake', SESSION='fake')
        definitions(8, ['poll_job'], ns)
        with self.assertRaisesRegex(RuntimeError, 'failed'):
            anyio.run(ns['poll_job'], 'prepare', 2)

    def test_cleanup_attempts_tunnel_after_stop_failure(self) -> None:
        calls = []
        def stop() -> None:
            calls.append('stop')
            raise RuntimeError('fake stop failure')
        ns = dict(check_remote_settings=lambda: None, stop_vllm=stop,
                  close_tunnel=lambda: calls.append('close'), warnings=warnings,
                  subprocess=subprocess, sanitise=str)
        definitions(8, ['cleanup_vllm'], ns)
        with warnings.catch_warnings(record=True) as caught:
            ns['cleanup_vllm']()
        self.assertEqual(calls, ['stop', 'close'])
        self.assertEqual(len(caught), 1)

    def test_cleanup_missing_settings_makes_no_connection(self) -> None:
        def missing() -> None:
            raise ValueError('no endpoint')
        ns = dict(check_remote_settings=missing, stop_vllm=lambda: self.fail('connected'),
                  close_tunnel=lambda: self.fail('connected'), warnings=warnings,
                  subprocess=subprocess, sanitise=str)
        definitions(8, ['cleanup_vllm'], ns)
        ns['cleanup_vllm']()

    def test_every_server_start_is_protected_by_cleanup(self) -> None:
        for index in (14,16,36,44):
            tree = ast.parse(source(index))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'start_vllm':
                    guards = [guard for guard in ast.walk(tree) if isinstance(guard, ast.Try)
                              and guard.finalbody and any(node is child for statement in guard.body for child in ast.walk(statement))]
                    self.assertTrue(guards, f'Unprotected start in cell {index}')
                    self.assertTrue(any('cleanup_vllm' in ast.unparse(ast.Module(body=g.finalbody, type_ignores=[])) for g in guards))

    def test_stale_server_restart_and_live_context_validation(self) -> None:
        for advertised in (131072, 32768, None):
            with self.subTest(advertised=advertised), tempfile.TemporaryDirectory() as tmp:
                art = Path(tmp)
                (art/'assets').mkdir()
                (art/'assets/provenance.json').write_text(json.dumps({'revision':'fake-sha'}))
                calls = []
                def remote(command: str, **kwargs: Any) -> str:
                    calls.append(command)
                    if command.startswith('cat '): return ''  # Unknown existing server configuration.
                    if 'has-session' in command: return 'alive'
                    return ''
                ns = dict(Any=Any, MAX_CONTEXT=32768, require_remote=lambda: None, ART=art, json=json,
                          U_HF='openai/gpt-oss-20b', REMOTE_PORT=8080, REMOTE='/fake', SESSION='fake',
                          run_remote=remote, shlex=shlex, stop_vllm=lambda: calls.append('STOP'),
                          close_tunnel=lambda: calls.append('CLOSE'), launch_job=lambda *args: calls.append('LAUNCH'),
                          open_tunnel=lambda: calls.append('OPEN'), BASE_URL='http://fake', anyio=anyio)
                definitions(12, ['start_vllm'], ns)
                data=json.dumps({'data':[{'id':ns['U_HF'],'max_model_len':advertised}]}).encode()
                with patch('urllib.request.urlopen', side_effect=lambda *a, **k: io.BytesIO(data)):
                    if advertised == 131072:
                        anyio.run(ns['start_vllm'], 131072)
                    else:
                        with self.assertRaisesRegex(RuntimeError,'Live server advertises'):
                            anyio.run(ns['start_vllm'],131072)
                self.assertLess(calls.index('STOP'), calls.index('LAUNCH'))
                self.assertLess(calls.index('CLOSE'), calls.index('OPEN'))

    def test_split_and_checkpoint_arithmetic(self) -> None:
        cut = next(node.value for node in ast.walk(ast.parse(source(20))) if isinstance(node,ast.Assign)
                   and any(isinstance(t,ast.Name) and t.id=='cut' for t in node.targets))
        for count in range(2,101):
            value=eval(compile(ast.Expression(cut),'split','eval'),{'math':math,'task_ids':list(range(count))})
            self.assertGreaterEqual(value,1);self.assertLess(value,count)
        script=next(ast.literal_eval(node.value) for node in ast.parse(source(24)).body
                    if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='TRAIN_SCRIPT')
        steps=next(kw.value for node in ast.walk(ast.parse(script)) if isinstance(node,ast.Call)
                   and isinstance(node.func,ast.Name) and node.func.id=='SFTConfig' for kw in node.keywords if kw.arg=='save_steps')
        for count in range(1,101):
            for target in (2,5):
                interval=eval(compile(ast.Expression(steps),'steps','eval'),{'examples':list(range(count)),'CONFIG':{'checkpoints_per_run':target}})
                distinct_final_and_periodic=math.ceil(count/interval)
                self.assertLessEqual(distinct_final_and_periodic,target)

    def test_long_pair_missing_conditions_and_all_failures(self) -> None:
        ns=definitions(46,['complete_long_pairs'],{'pd':pd})
        base=dict(view='none',pad_target=0,position='only',task_id='1',status='ok',suspicion=.8)
        for rows in ([dict(base,condition='attack')],
                     [dict(base,condition='attack',status='parse_failure',suspicion=None)],
                     [dict(base,condition='attack'),dict(base,condition='clean',status='parse_failure',suspicion=None)]):
            self.assertTrue(ns['complete_long_pairs'](pd.DataFrame(rows)).empty)
        pairs=ns['complete_long_pairs'](pd.DataFrame([dict(base,condition='attack'),dict(base,condition='clean',suspicion=.1)]))
        self.assertEqual(len(pairs),1)
        self.assertAlmostEqual(pairs.attack.iloc[0]-pairs.clean.iloc[0],.7)

    def test_token_budgets_include_framing_and_output(self) -> None:
        class FakeU:
            def encode(self,text: str,**kwargs: Any) -> Any:
                return SimpleNamespace(ids=list(range(len(text))))
        class FakeT:
            def encode(self,text: str,**kwargs: Any) -> list[int]:
                return list(range(len(text)))
        ns=dict(Any=Any,T_CHAT_OVERHEAD=10,SUMMARY_WORDS=800,
                SUMMARY_PROMPT='Summary:{body}',LONG_MONITOR_PROMPT='Monitor:{body}',
                T_MAX_INPUT_TOKENS=100,LONG_CONTEXT=100,U_MAX_TOKENS=20,CONTEXT_RESERVE=5)
        definitions(42,['u_prompt_tokens','t_prompt_tokens','validate_long_input'],ns)
        tokenizers=(FakeU(),FakeT(),dict(prefix='AAA',suffix='ZZZ'))
        self.assertEqual(ns['u_prompt_tokens']('abc',tokenizers),9)
        self.assertEqual(ns['t_prompt_tokens']('abc',tokenizers),13)
        ns['validate_long_input']({'task_id':'1','log':'x'*40},tokenizers)
        with self.assertRaisesRegex(RuntimeError,'U input plus output'):
            ns['validate_long_input']({'task_id':'1','log':'x'*70},tokenizers)
        ns['LONG_CONTEXT']=1000
        with self.assertRaisesRegex(RuntimeError,'T input budget'):
            ns['validate_long_input']({'task_id':'1','log':'x'*100},tokenizers)

    def test_long_input_guards_precede_gpu_start(self) -> None:
        text=source(44)
        self.assertLess(text.index('validate_long_input(row, tokenizers)'),text.index('await start_vllm'))
        self.assertIn("tokenizer_sha256=tokenizers[2]['tokenizer_sha256']",text)
        self.assertIn("write_once(LONG / 'build_spec.json'",text)


    def test_smoke_selection_rejects_wrong_count_and_duplicates(self) -> None:
        ns=definitions(51,['_selection'],{'Path':Path,'json':json,'N_TASKS':3})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'selection.json'
            for ids in (['1','2'],['1','1','3']):
                path.write_text(json.dumps([{'id':i} for i in ids]))
                with self.assertRaises(RuntimeError):ns['_selection'](path)
            path.write_text(json.dumps([{'id':i} for i in ['1','2','3']]))
            self.assertIn('3 distinct',ns['_selection'](path))

    def test_smoke_split_rejects_empty_overlap_and_unpaired_records(self) -> None:
        records={'train.jsonl':[dict(task_id='1',source='U'),dict(task_id='1',source='H')],
                 'test.jsonl':[dict(task_id='2',source='U'),dict(task_id='2',source='H')]}
        ns=definitions(51,['_split'],{'Path':Path,'json':json,'ART':Path('/fake'),
                                     'read_jsonl':lambda path:records[path.name]})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'split.json'
            for split in (dict(train_ids=[],test_ids=['2']),dict(train_ids=['1'],test_ids=['1'])):
                path.write_text(json.dumps(split))
                with self.assertRaises(RuntimeError):ns['_split'](path)
            path.write_text(json.dumps(dict(train_ids=['1'],test_ids=['2'])))
            self.assertIn('disjoint',ns['_split'](path))
            records['test.jsonl'].pop()
            with self.assertRaises(RuntimeError):ns['_split'](path)

    def test_smoke_auc_rejects_missing_runs_nan_and_zero_tasks(self) -> None:
        ns=definitions(51,['_auc'],{'Path':Path,'pd':pd})
        rows=[dict(run=run,auc=.5,common_test_tasks=1) for run in ['base','real','shuffled']]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'auc.csv'
            for values in (rows[:1],[dict(row,auc=None) for row in rows],
                           [dict(row,common_test_tasks=0) for row in rows]):
                pd.DataFrame(values).to_csv(path,index=False)
                with self.assertRaises(RuntimeError):ns['_auc'](path)
            pd.DataFrame(rows).to_csv(path,index=False)
            self.assertIn('3 valid',ns['_auc'](path))

if __name__ == '__main__':
    unittest.main()
