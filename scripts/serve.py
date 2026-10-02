"""Run the bundled local app without changing the FinRL environment."""
import argparse
import json
from pathlib import Path
import sys
import threading
import time
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".runtime" / "python"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--allow-network", action="store_true", help="Disable the process-local offline guard")
    args = parser.parse_args()
    if not args.allow_network:
        from lab.offline import enable_offline
        enable_offline()
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        raise SystemExit("The frontend is not built. Run setup-web.ps1 once while connected.")
    import uvicorn
    url = f"http://127.0.0.1:{args.port}"
    try:
        with urlopen(url + "/api/health", timeout=1) as response:
            existing = json.load(response)
        if existing.get("app") == "shanghai-strategy-lab":
            print("The local lab is already running: " + url)
            if not args.no_browser:
                webbrowser.open(url)
            return
        raise SystemExit("This port is occupied by another app. Choose --port with a different number.")
    except OSError:
        pass

    def open_when_ready():
        for _ in range(40):
            try:
                with urlopen(url + "/api/health", timeout=1) as response:
                    if response.status == 200:
                        webbrowser.open(url)
                        return
            except OSError:
                time.sleep(.25)

    if not args.no_browser:
        threading.Thread(target=open_when_ready, daemon=True).start()
    uvicorn.run("api.main:app", host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
