import asyncio
import db, execution_queue

def test_persistent_queue_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "queue.db")
    monkeypatch.setattr(db, "_CANDIDATES", [tmp_path / "queue.db"])
    db.init_db()
    job=execution_queue.enqueue("model_chat", {"message":"hello"}, priority=10, max_attempts=2)
    assert job["status"]=="queued"
    async def handler(item):
        assert item["attempt"]==1
        return {"ok":True}
    result=asyncio.run(execution_queue.run_once(handler))
    assert result["status"]=="completed"
    assert result["result"]["ok"] is True

def test_queue_cancel(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "cancel.db")
    monkeypatch.setattr(db, "_CANDIDATES", [tmp_path / "cancel.db"])
    db.init_db()
    job=execution_queue.enqueue("model_chat", {"message":"hello"})
    cancelled=execution_queue.cancel(job["id"])
    assert cancelled["status"]=="cancelled"
