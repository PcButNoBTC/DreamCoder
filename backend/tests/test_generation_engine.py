from generation.engine import parse_json, parse_files

def test_parse_json_recovers_embedded_object():
    assert parse_json("prefix {"approved": true} suffix")["approved"] is True

def test_parse_files_rejects_unsafe_paths():
    files=parse_files("===FILE: ../escape.py===\nprint(1)\n===END===")
    assert files == []
