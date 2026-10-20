import os
import re
from wal import WAL
from memtable import MemTable
from sstable import SSTableWriter, SSTableReader


_DELETED = "[DELETED]"
_TABLE_PATTERN = re.compile(r"^sstable_(\d+)\.db$")


class LSMStorageEngine:
    def __init__(self, data_dir="data", max_memtable_size=1024):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        self.wal_path = os.path.join(data_dir, "wal.log")
        self.wal = WAL(self.wal_path)

        self.memtable = MemTable()
        self.max_memtable_size = max_memtable_size
        self.sstable_count = 0

        # Discover tables before replaying the WAL. The WAL may contain operations
        # from a flush that was published but whose WAL clear did not finish.
        self._discover_sstables()
        self._recover()

    def _discover_sstables(self):
        """Rebuild the filename counter from disk after every process restart."""
        highest = 0
        for filename in os.listdir(self.data_dir):
            match = _TABLE_PATTERN.match(filename)
            if match:
                number = int(match.group(1))
                table_path = os.path.join(self.data_dir, filename)
                index_path = table_path + ".index"
                # Count only committed table/index pairs as readable tables.
                if os.path.isfile(table_path) and os.path.isfile(index_path):
                    highest = max(highest, number)
        self.sstable_count = highest

    def _recover(self):
        """Replay durable WAL operations into a fresh MemTable after restart."""
        records = self.wal.recover()
        for op, key, value in records:
            if op == "PUT":
                self.memtable.put(key, value)
            elif op in ("DELETE", "DEL"):
                self.memtable.put(key, _DELETED)

    def put(self, key: str, value: str):
        if value == _DELETED:
            raise ValueError(f"Value {_DELETED!r} is reserved internally for delete tombstones")
        # 1. WAL first: append() flushes and fsyncs before returning.
        self.wal.append("PUT", key, value)

        # 2. Then update the in-memory sorted MemTable.
        self.memtable.put(key, value)

        # 3. Flush if the approximate MemTable size reached its limit.
        if self.memtable.size_bytes >= self.max_memtable_size:
            self._flush_memtable()

    def delete(self, key: str):
        # The tombstone is written to WAL before changing the MemTable.
        self.wal.append("DELETE", key, "")
        self.memtable.put(key, _DELETED)
        if self.memtable.size_bytes >= self.max_memtable_size:
            self._flush_memtable()

    def _flush_memtable(self):
        items = list(self.memtable.items())
        if not items:
            return

        # Use the next table number, but do not commit the counter until the writer
        # has published both the SSTable and its index.
        next_count = self.sstable_count + 1
        sstable_path = os.path.join(self.data_dir, f"sstable_{next_count}.db")

        # If this fails, the WAL and MemTable are deliberately left intact.
        SSTableWriter.flush_to_disk(sstable_path, items)
        self.sstable_count = next_count

        # The SSTable and index are now published and fsynced. Only now can the WAL
        # be cleared. If a crash happens before/during this clear, replaying WAL
        # records is safe: MemTable values overlay older SSTable values.
        self.wal.clear()
        self.memtable.clear()

    def get(self, key: str):
        # 1. MemTable contains the newest unflushed value or tombstone.
        val = self.memtable.get(key)
        if val is not None:
            return None if val == _DELETED else val

        # 2. Search SSTables from newest to oldest. Missing/corrupt index pairs
        # return None from the reader and are skipped.
        for i in range(self.sstable_count, 0, -1):
            sstable_path = os.path.join(self.data_dir, f"sstable_{i}.db")
            if not os.path.exists(sstable_path + ".index"):
                continue
            val = SSTableReader.get(sstable_path, key)
            if val is not None:
                return None if val == _DELETED else val

        return None


    def compact(self):
        """Merge every committed SSTable into one sorted table.

        Newer tables win for duplicate keys. Tombstones are deliberately retained:
        if the process stops after publishing the compacted table but before all old
        tables are removed, the tombstones prevent deleted values from resurfacing.
        """
        table_numbers = []
        for filename in os.listdir(self.data_dir):
            match = _TABLE_PATTERN.match(filename)
            if not match:
                continue
            number = int(match.group(1))
            path = os.path.join(self.data_dir, filename)
            if os.path.isfile(path) and os.path.isfile(path + ".index"):
                table_numbers.append(number)

        table_numbers.sort(reverse=True)
        if len(table_numbers) < 2:
            return {"tables_before": len(table_numbers), "tables_after": len(table_numbers),
                    "keys_written": 0, "message": "At least two SSTables are required for compaction."}

        newest_records = {}
        # Scan newest to oldest, keeping the first version of each key.
        # Any corrupt input aborts compaction rather than silently losing data.
        for number in table_numbers:
            path = os.path.join(self.data_dir, f"sstable_{number}.db")
            for key, value in SSTableReader.iter_items(path):
                if key not in newest_records:
                    newest_records[key] = value

        new_number = max(table_numbers) + 1
        new_path = os.path.join(self.data_dir, f"sstable_{new_number}.db")
        SSTableWriter.flush_to_disk(new_path, sorted(newest_records.items()))

        # The new table is fully published before old files are removed. Keeping
        # tombstones in the output makes interrupted cleanup safe against resurrection.
        self.sstable_count = new_number
        for number in table_numbers:
            old_path = os.path.join(self.data_dir, f"sstable_{number}.db")
            for suffix in ("", ".index", ".bloom", ".tmp", ".index.tmp", ".bloom.tmp"):
                candidate = old_path + suffix
                if os.path.exists(candidate):
                    os.remove(candidate)

        # Best-effort sync of directory entry removals.
        if os.name != "nt":
            try:
                fd = os.open(self.data_dir, getattr(os, "O_DIRECTORY", 0) | os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            except OSError:
                pass

        return {"tables_before": len(table_numbers), "tables_after": 1,
                "keys_written": len(newest_records), "message": "Compaction completed."}

    def close(self):
        """Close the WAL file handle cleanly."""
        self.wal.close()

    def flush(self):
        """Force the current MemTable to disk (useful for testing/shutdown)."""
        self._flush_memtable()
