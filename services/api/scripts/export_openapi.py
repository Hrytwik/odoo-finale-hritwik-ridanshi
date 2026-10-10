import json
from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    out = ROOT / "contracts" / "openapi.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
