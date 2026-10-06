"""
Local development server:  python run_dev.py   (API on http://127.0.0.1:5000)
Reads variables from ../.env if present (see .env.example).
"""
import os
from pathlib import Path

env_file = Path(__file__).resolve().parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip())

from app import create_app  # noqa: E402  (after env is loaded)

if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
