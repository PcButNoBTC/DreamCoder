"""Project symbol index – backed by SQLite for persistence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import db


@dataclass
class Symbol:
    name: str
    kind: str
    file: str
    line: int
    signature: str = ""


class ProjectIndex:
    def __init__(self):
        db.init_db()

    def clear(self) -> None:
        db.clear_files()

    def index_file(self, path: str, content: str, language: str = "python") -> dict[str, Any]:
        # upsert_file clears the previous symbol snapshot before parsing the new content.
        db.upsert_file(path, content, language)
        symbols = self._extract_python_symbols(path, content) if language == "python" else []
        db.insert_symbols(
            [
                {
                    "name": s.name,
                    "kind": s.kind,
                    "file": s.file,
                    "line": s.line,
                    "signature": s.signature,
                }
                for s in symbols
            ]
        )
        return self.stats()

    def remove_file(self, path: str) -> dict[str, Any]:
        db.delete_file(path)
        return self.stats()

    def get_file(self, path: str):
        return db.get_file(path)

    def list_files(self):
        return db.list_files()

    def _extract_python_symbols(self, path: str, content: str) -> list:
        symbols = []
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            m = re.match(r"^class\s+(\w+)", stripped)
            if m:
                symbols.append(Symbol(name=m.group(1), kind="class", file=path, line=i, signature=stripped))
                continue
            m = re.match(r"^(?:async\s+)?def\s+(\w+)\s*\((.*?)\)", stripped)
            if m:
                symbols.append(
                    Symbol(
                        name=m.group(1),
                        kind="function",
                        file=path,
                        line=i,
                        signature=f"{m.group(1)}({m.group(2)})",
                    )
                )
                continue
            m = re.match(r"^(\w+)\s*=", stripped)
            if m and not stripped.startswith("#"):
                symbols.append(Symbol(name=m.group(1), kind="variable", file=path, line=i))
        return symbols

    def search(self, query: str, limit: int = 20) -> list:
        rows = db.search_symbols(query, limit=limit)
        return [
            Symbol(
                name=r["name"],
                kind=r["kind"],
                file=r["file"],
                line=r["line"],
                signature=r.get("signature") or "",
            )
            for r in rows
        ]

    def stats(self) -> dict:
        return db.symbol_stats()

    def to_context_symbols(self, limit: int = 40) -> list:
        return db.all_symbol_names(limit=limit)
