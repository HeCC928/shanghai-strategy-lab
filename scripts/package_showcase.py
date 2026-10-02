"""Build a local offline bundle without network access or a Python redistribution."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    showcase=json.loads((ROOT/'configs/showcase.json').read_text())
    runs={showcase['featured_run_id'],showcase['rolling_run_id']}
    runs.update(x['run_id'] for x in showcase['comparisons'].values())
    search=ROOT/'storage/searches'/showcase['search_id']
    runs.update(t['run_id'] for t in json.loads((search/'trials.json').read_text()) if t.get('run_id'))
    roots=[ROOT/x for x in ('api','lab','configs','scripts','docs','tests','examples','frontend/src','frontend/dist','.runtime/python','storage/showcase')]
    roots += [ROOT/'storage/runs'/identifier for identifier in sorted(runs)]
    roots += [ROOT/'storage/snapshots'/showcase['snapshot_id'],search]
    chosen={}
    for directory in roots:
        for file in directory.rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts and file.suffix not in ('.pyc','.zip'):
                chosen[file.relative_to(ROOT).as_posix()]=file
    for file in (ROOT/'frontend').iterdir():
        if file.is_file():chosen[file.relative_to(ROOT).as_posix()]=file
    for name in ('README.md','app.py','Start Lab.cmd','start.ps1','setup-web.ps1','pyproject.toml','requirements-lock.txt','requirements-web.txt','requirements-web-lock.txt','LICENSE','IMPLEMENTATION_PLAN_V3_WALK_FORWARD_SHOWCASE.md'):
        chosen[name]=ROOT/name
    chosen['storage/verification-tests.xml']=ROOT/'storage/verification-tests.xml'
    manifest={name:hashlib.sha256(file.read_bytes()).hexdigest() for name,file in chosen.items()}
    archive_path=ROOT/'storage/Shanghai_Strategy_Lab_Offline.zip'
    with zipfile.ZipFile(archive_path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name,file in sorted(chosen.items()):archive.write(file,'Shanghai_Strategy_Lab/'+name)
        archive.writestr('Shanghai_Strategy_Lab/bundle-manifest.json',json.dumps(manifest,indent=2))
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        for name,expected in manifest.items():
            assert hashlib.sha256(archive.read('Shanghai_Strategy_Lab/'+name)).hexdigest()==expected
    print(json.dumps({'archive':str(archive_path),'files':len(manifest),'bytes':archive_path.stat().st_size,
                      'sha256':hashlib.sha256(archive_path.read_bytes()).hexdigest()},indent=2))

if __name__=='__main__':main()
