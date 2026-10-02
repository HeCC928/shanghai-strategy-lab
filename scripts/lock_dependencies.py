"""Record the installed dependency closure for this verified Python/OS environment."""
from importlib.metadata import distribution
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

roots=["numpy","pandas","plotly","streamlit","pydantic","pyarrow","PyYAML","akshare","baostock","pytest","psutil","filelock"]
pending=roots.copy()
seen={}
while pending:
    name=canonicalize_name(pending.pop())
    if name in seen: continue
    d=distribution(name)
    seen[name]=d.version
    for text in d.requires or []:
        req=Requirement(text)
        if req.marker is None or req.marker.evaluate({"extra":""}):
            pending.append(req.name)
Path("requirements-lock.txt").write_text("# Verified Windows / Python 3.10 environment; use pyproject.toml on other platforms.\n"+"\n".join(f"{name}=={v}" for name,v in sorted(seen.items()))+"\n",encoding="utf-8")
print(f"Pinned {len(seen)} runtime and test packages")
