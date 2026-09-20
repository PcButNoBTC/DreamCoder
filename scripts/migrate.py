"""Database migration command-line helper.

Usage:
  python scripts/migrate.py status
  python scripts/migrate.py up
  python scripts/migrate.py rollback 1
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import db  # noqa: E402
import migrations  # noqa: E402


def main(argv: list[str]) -> int:
    conn = db.get_conn()
    try:
        action = argv[1] if len(argv) > 1 else "status"
        if action == "status":
            print(migrations.status(conn))
            return 0
        if action == "up":
            print({"current": migrations.apply(conn)})
            return 0
        if action == "rollback":
            if len(argv) != 3:
                print("rollback requires a target version", file=sys.stderr)
                return 2
            print({"current": migrations.rollback_to(conn, int(argv[2]))})
            return 0
        print("unknown action", file=sys.stderr)
        return 2
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
