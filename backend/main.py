from __future__ import annotations

"""CLI entry: python main.py is not used; run `python app.py` instead."""

from app import app, _load_dotenv

if __name__ == "__main__":
    _load_dotenv()
    app.run(host="127.0.0.1", port=5000, debug=True)
