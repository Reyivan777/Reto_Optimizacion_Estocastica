#!/usr/bin/env python3
"""Aplica el paquete DSATUR validado y publica un commit solo en DSATUR/."""
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

BASE = 'fa888eefea118c154f6ada52145c7fc5ee6298ec'
COMMIT_MESSAGE = 'Valida presupuesto y consolida resultados completos de DSATUR'


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def main():
    zip_file = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).with_name('DSATUR_mejoras_validadas.zip')
    if not zip_file.is_file():
        sys.exit(f'ZIP no encontrado: {zip_file}')
    root = Path(git('rev-parse', '--show-toplevel')).resolve()
    if git('branch', '--show-current') != 'main':
        sys.exit('No se aplicó: debes estar en la rama main.')
    # Permitir commits nuevos únicamente si respetan el DSATUR validado.
    if subprocess.run(['git', 'merge-base', '--is-ancestor', BASE, 'HEAD'],
                      cwd=root).returncode:
        sys.exit('No se aplicó: la versión local no desciende de la base validada.')
    if subprocess.run(['git', 'diff', '--quiet', BASE, 'HEAD', '--', 'DSATUR'],
                      cwd=root).returncode:
        sys.exit('No se aplicó: DSATUR cambió desde la base validada; hay que revisar conflictos.')
    # Ignorar archivos sin seguimiento fuera de DSATUR, pero no cambios de código.
    if git('status', '--porcelain', '--untracked-files=no') or git('ls-files', '--others', '--exclude-standard', '--', 'DSATUR'):
        sys.exit('No se aplicó: hay cambios locales o archivos nuevos en DSATUR sin commit.')
    # No sobrescribir cambios remotos de main durante la publicación.
    subprocess.run(['git', 'fetch', 'origin', 'main'], cwd=root, check=True)
    if git('rev-parse', 'HEAD') != git('rev-parse', 'FETCH_HEAD'):
        sys.exit('No se aplicó: main local no coincide con origin/main. Ejecuta git pull --ff-only.')
    with zipfile.ZipFile(zip_file) as z:
        if z.testzip():
            sys.exit('El ZIP contiene un archivo corrupto.')
        manifest = json.loads(z.read('manifiesto_cambios.json'))
        if manifest['base_commit'] != BASE:
            sys.exit('Base del manifiesto incompatible.')
        changed = manifest['changes']
        removed = manifest['deletes']
        paths = [entry['path'] for entry in changed] + removed
        if len(set(paths)) != len(paths):
            sys.exit('Hay rutas duplicadas en el manifiesto.')
        for path in paths:
            p = Path(path)
            if p.is_absolute() or '..' in p.parts or p.parts[0] != 'DSATUR':
                sys.exit(f'Ruta rechazada: {path}')
        for entry in changed:
            data = z.read(entry['path'])
            digest = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            if digest != entry['sha'] or len(data) != entry['size']:
                sys.exit(f'SHA o tamaño incorrecto: {entry["path"]}')
        print(f'Integridad verificada: {len(changed)} archivos y {len(removed)} eliminaciones.')
        for entry in changed:
            dest = root / entry['path']
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(entry['path']))
        for path in removed:
            (root / path).unlink(missing_ok=True)
    subprocess.run(['git', 'add', '--', 'DSATUR'], cwd=root, check=True)
    staged = git('diff', '--cached', '--name-only').splitlines()
    if any(not name.startswith('DSATUR/') for name in staged):
        sys.exit('Se detuvo: hay archivos fuera de DSATUR preparados para commit.')
    if not staged:
        sys.exit('No se detectaron cambios respecto a main.')
    subprocess.run(['git', 'diff', '--cached', '--check'], cwd=root, check=True)
    print(f'Archivos preparados para commit: {len(staged)}')
    subprocess.run(['git', 'commit', '-m', COMMIT_MESSAGE], cwd=root, check=True)
    subprocess.run(['git', 'push', 'origin', 'main'], cwd=root, check=True)
    print('PUBLICADO:', git('rev-parse', 'HEAD'))

if __name__ == '__main__':
    main()
