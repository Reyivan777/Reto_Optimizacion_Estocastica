"""Compile C++17 with GCC/Clang (Windows MinGW or Linux); no Python headers."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def compilar(compiler='g++'):
    build = ROOT/'build'; build.mkdir(exist_ok=True)
    target = build/('reforestacion.dll' if sys.platform == 'win32' else 'libreforestacion.so')
    cmd = [compiler, '-std=c++17', '-O3', '-ffp-contract=off', '-shared',
           str(ROOT/'cpp/motor.cpp'), '-o', str(target)]
    cmd += ['-static-libgcc', '-static-libstdc++'] if sys.platform == 'win32' else ['-fPIC']
    subprocess.run(cmd, check=True)
    metadata = dict(command=cmd, compiler=subprocess.check_output([compiler,'--version'],text=True),
                    platform=platform.platform(), source_sha256=hashlib.sha256((ROOT/'cpp/motor.cpp').read_bytes()).hexdigest(),
                    binary_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    (build/'compilacion.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    print(target)

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',default='g++')
    compilar(parser.parse_args().compiler)
