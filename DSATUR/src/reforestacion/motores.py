"""Explicit engine selection; no silent fallback on native errors."""
from types import SimpleNamespace
from . import algoritmos, geometria

def informacion_motor(nombre):
    if nombre=='python': return {'nombre':'python'}
    from pathlib import Path
    import json, hashlib
    from .motor_cpp import biblioteca
    lib=biblioteca()
    root=Path(__file__).resolve().parents[2]
    return dict(nombre=nombre,abi=lib.reforestacion_abi(),
        binario_sha256=hashlib.sha256(Path(lib._name).read_bytes()).hexdigest(),
        fuente_sha256=hashlib.sha256((root/'cpp/motor.cpp').read_bytes()).hexdigest(),
        compilacion=json.loads((root/'build/compilacion.json').read_text(encoding='utf-8')))

def obtener_motor(nombre='python'):
    if nombre=='python':
        return SimpleNamespace(candidatas=geometria.candidatas,dsatur=algoritmos.dsatur,busqueda_local=algoritmos.busqueda_local)
    if nombre=='cpp':
        from . import motor_cpp
        motor_cpp.biblioteca()
        return motor_cpp
    raise ValueError('Motor debe ser python o cpp.')
