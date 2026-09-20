#!/usr/bin/env python3
"""Apply and inspect DreamCoder SQLite migrations."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))

import db
import migrations

parser=argparse.ArgumentParser()
parser.add_argument("command",choices=("up","status"),nargs="?",default="up")
args=parser.parse_args()
db.init_db()
if args.command=="status":
    print(migrations.status())
else:
    print({"applied": migrations.apply(), "status": migrations.status()})
