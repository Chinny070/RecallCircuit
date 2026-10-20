"""An intentionally labeled SIMULATED host for local state-machine testing.
No test in this file is real GenVM or validator consensus evidence.
"""
import dataclasses
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path
import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'contracts' / 'recall_circuit.py'

class UserError(Exception):
    pass

class Dyn(list):
    @classmethod
    def __class_getitem__(cls, _): return cls

class Map(dict):
    @classmethod
    def __class_getitem__(cls, _): return cls
    def __init__(self, storage_class):
        super().__init__()
        self.storage_class = storage_class
    def get_or_insert_default(self, key):
        if key not in self:
            obj = object.__new__(self.storage_class)
            for keyname, ty in self.storage_class.__annotations__.items():
                if ty is Dyn: val = Dyn()
                elif ty is bool: val = False
                elif ty is str: val = ''
                elif ty is int: val = 0
                else: val = ''
                setattr(obj, keyname, val)
            self[key] = obj
        return self[key]

class Event:
    def __init__(self, *args, **kwargs): pass
    def emit(self): pass

class Keccak:
    def __init__(self, b): self.data = b
    def hexdigest(self): return hashlib.sha3_256(self.data).hexdigest()

class Result:
    def __init__(self, calldata): self.calldata = calldata

class VM:
    Return = Result
    UserError = UserError
    @staticmethod
    def run_nondet_unsafe(leader, validator):
        answer = leader()
        if not validator(Result(answer)):
            raise ValueError('validator disagreement')
        return answer

@pytest.fixture
def state():
    pkg = types.ModuleType('genlayer')
    message = types.SimpleNamespace(sender_address='owner')
    pub = types.SimpleNamespace(write=lambda f: f, view=lambda f: f)
    gl = types.SimpleNamespace(vm=VM(), message=message, public=pub, Event=Event,
                                Contract=object, nondet=types.SimpleNamespace())
    pkg.__all__ = ['gl', 'u8', 'u32', 'u256', 'Address', 'DynArray', 'TreeMap',
                   'allow_storage', 'Keccak256']
    for name, val in {'gl': gl, 'u8': int, 'u32': int, 'u256': int, 'Address': str,
                      'DynArray': Dyn, 'TreeMap': Map, 'allow_storage': lambda f: f,
                      'Keccak256': Keccak}.items():
        setattr(pkg, name, val)
    sys.modules['genlayer'] = pkg
    try:
        spec = importlib.util.spec_from_file_location('recall_sim', SOURCE)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
    finally:
        del sys.modules['genlayer']
    core = mod.RecallCircuit()
    core.assets = Map(mod.Asset)
    core.notices = Map(mod.Notice)
    core.cases = Map(mod.Case)
    class LLM:
        def __init__(self):
            self.finding = 'AFFECTED'
            self.valid = True
            self.calls = 0
            self.override_validator = False
            self.remedy_ok = False
        def prompt(self, prompt, response_format='json'):
            self.calls += 1
            if 'OFFICIAL CPSC NOTICE VERIFICATION' in prompt:
                return {'official_id':'25-300', 'title':'Recalled batteries',
                        'recall_date':'2026-10-01', 'valid':self.valid}
            if 'REMEDY EVIDENCE CHECK' in prompt:
                finding = 'NOT_AFFECTED' if self.remedy_ok else 'UNCERTAIN'
            else:
                finding = self.finding
            if self.override_validator and self.calls % 2 == 0:
                finding = 'AFFECTED' if finding != 'AFFECTED' else 'NOT_AFFECTED'
            return {'finding': finding, 'reason_code':
                    {'AFFECTED':'MODEL_AND_SCOPE_MATCH', 'NOT_AFFECTED':'SCOPE_EXCLUDES',
                     'UNCERTAIN':'INSUFFICIENT_EVIDENCE'}[finding]}
    llm = LLM()
    gl.nondet.web = types.SimpleNamespace(render=lambda url, mode='text':
        'CPSC Recall Number 25-300. Example batteries have been recalled. '
        'Models manufactured in particular batches may require replacement. '
        'Do not use recalled batteries until repaired.')
    gl.nondet.exec_prompt = llm.prompt
    return core, mod, gl, llm
