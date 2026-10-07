"""Create a source-only checkpoint without environment secrets or dependencies."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime
import sys
out=Path('.tmp/m2-checkpoints');out.mkdir(parents=True,exist_ok=True)
with ZipFile(out / (sys.argv[1]+'-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.zip'),'w',ZIP_DEFLATED) as z:
 for root in ['backend','frontend','deploy','scripts']:
  for p in Path(root).rglob('*'):
   if p.is_file() and not any(x in p.parts for x in ['.venv','node_modules','__pycache__','dist','staticfiles']) and p.name!='.env' and p.suffix in ['.py','.ts','.tsx','.json','.in','.lock','.yaml','.yml','.ps1','.conf','.html','.cjs']:
    z.write(p,p.as_posix())
