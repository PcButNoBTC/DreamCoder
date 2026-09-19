import backup_manager
from pathlib import Path

def test_write_backup_creates_zip(tmp_path,monkeypatch):
    monkeypatch.setenv("DREAMCODER_BACKUP_DIR",str(tmp_path))
    result=backup_manager.write_backup("/root","src/app.py","print('hi')\n","test reason")
    assert result["ok"] is True
    assert Path(result["path"]).exists()

def test_list_backups(tmp_path,monkeypatch):
    monkeypatch.setenv("DREAMCODER_BACKUP_DIR",str(tmp_path))
    backup_manager.write_backup("/root","a.py","x = 1\n","r1")
    backup_manager.write_backup("/root","b.py","y = 2\n","r2")
    assert len(backup_manager.list_backups())==2

def test_log_command(tmp_path,monkeypatch):
    monkeypatch.setenv("DREAMCODER_BACKUP_DIR",str(tmp_path))
    backup_manager.log_command("pytest -q","/proj",0,run_id="abc")
    assert any(e.get("command")=="pytest -q" for e in backup_manager.read_audit_log())
