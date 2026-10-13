import pytest
from app.memory.database import MemoryDatabase
import tempfile
from pathlib import Path

def test_sqlite_memory():
    temp_db = str(Path(tempfile.gettempdir()) / f"test_mem_{tempfile.mktemp().split('tmp')[-1]}.db")
    db = MemoryDatabase(db_path=temp_db)
    
    # Test messages
    msg_id = db.add_message("user", "Hello FOXSI test")
    assert msg_id > 0
    msgs = db.get_recent_messages(5)
    assert len(msgs) == 1
    assert msgs[0]["content"] == "Hello FOXSI test"

    # Test preferences
    db.set_preference("theme", "dark")
    assert db.get_preference("theme") == "dark"

    # Test export
    exported = db.export_memory()
    assert "messages" in exported
    assert len(exported["messages"]) == 1

    # Test clear
    cleared = db.clear_conversation()
    assert cleared == 1
    assert len(db.get_recent_messages()) == 0
