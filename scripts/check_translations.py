"""List English texts used in the code that have no Khmer yet in locales/km.json.

    python scripts/check_translations.py          # show missing keys
    python scripts/check_translations.py --add    # append missing keys with empty value
"""
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALE = ROOT / "locales" / "km.json"
# functions whose first argument is shown on screen through t()
TRANSLATED_CALLS = {"t", "caveat", "missing_data_notice"}


def used_keys() -> set[str]:
    keys: set[str] = set()
    for f in [ROOT / "app.py", ROOT / "overview.py", *ROOT.glob("pages/*.py"), *ROOT.glob("src/*.py")]:
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in TRANSLATED_CALLS
                    and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)):
                keys.add(n.args[0].value)
    return keys


def main() -> int:
    table = json.loads(LOCALE.read_text(encoding="utf-8"))
    missing = sorted(k for k in used_keys() if not table.get(k))
    for k in missing:
        print(k)
    if "--add" in sys.argv and missing:
        table.update({k: "" for k in missing})
        LOCALE.write_text(json.dumps(table, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{len(missing)} missing", file=sys.stderr)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
