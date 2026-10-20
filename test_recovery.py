"""Regression tests for WAL replay, sparse index, Bloom filter, and compaction."""
import os
import shutil
import tempfile
from unittest.mock import patch
from storage_engine import LSMStorageEngine


def run_test():
    data_dir = tempfile.mkdtemp(prefix="lsm_recovery_test_")
    db = None
    try:
        db = LSMStorageEngine(data_dir=data_dir, max_memtable_size=10**9)
        # WAL-only recovery, including separators and Unicode.
        db.put("user:1", "Ayush")
        db.put("key:with:colons", "value:with:colons")
        db.put("हिंदी🔑", "नमस्ते 🌍")
        db.close()

        db = LSMStorageEngine(data_dir=data_dir, max_memtable_size=10**9)
        assert db.get("user:1") == "Ayush"
        assert db.get("key:with:colons") == "value:with:colons"
        assert db.get("हिंदी🔑") == "नमस्ते 🌍"

        # Fault-injection: failed flush must not clear WAL or MemTable.
        with patch("storage_engine.SSTableWriter.flush_to_disk", side_effect=OSError("simulated disk failure")):
            try:
                db.flush()
                raise AssertionError("flush should have propagated the simulated failure")
            except OSError as exc:
                assert "simulated disk failure" in str(exc)
        assert db.get("user:1") == "Ayush"
        assert db.wal.recover(), "WAL should remain available after failed flush"

        # Force a flush, then restart and verify SSTable + sparse index discovery.
        db.flush()
        db.close()
        db = LSMStorageEngine(data_dir=data_dir, max_memtable_size=10**9)
        assert db.get("user:1") == "Ayush"
        assert db.get("missing-key") is None

        # More than one table with overlapping versions and a deletion tombstone.
        db.put("user:1", "Updated")
        db.put("new:key", "new-value")
        db.flush()
        db.delete("new:key")
        db.put("other", "present")
        db.flush()
        assert db.sstable_count >= 3
        before = {k: db.get(k) for k in ("user:1", "key:with:colons", "हिंदी🔑", "new:key", "other")}
        assert before == {"user:1": "Updated", "key:with:colons": "value:with:colons",
                          "हिंदी🔑": "नमस्ते 🌍", "new:key": None, "other": "present"}

        # Fault-injection: a failed compaction write must leave existing tables readable.
        with patch("storage_engine.SSTableWriter.flush_to_disk", side_effect=OSError("simulated compaction failure")):
            try:
                db.compact()
                raise AssertionError("compaction should have propagated the simulated failure")
            except OSError as exc:
                assert "simulated compaction failure" in str(exc)
        assert {k: db.get(k) for k in before} == before

        result = db.compact()
        assert result["tables_before"] >= 3
        assert result["tables_after"] == 1
        after = {k: db.get(k) for k in before}
        assert after == before
        assert db.get("new:key") is None, "tombstone must not allow deleted value to reappear"
        committed = [f for f in os.listdir(data_dir) if f.startswith("sstable_") and f.endswith(".db")]
        assert len(committed) == 1

        # Restart after compaction; ensure the compacted table remains discoverable.
        db.close()
        db = LSMStorageEngine(data_dir=data_dir, max_memtable_size=10**9)
        for key, value in before.items():
            assert db.get(key) == value
        db.close()
        db = None
        print("PASS: WAL replay, colon/Unicode keys, sparse index, Bloom filter lookup, updates, tombstones, compaction, restart, and injected write failures.")
    finally:
        if db is not None:
            db.close()
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    run_test()
