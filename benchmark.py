"""Small reproducible local benchmark; results are informational, not a formal claim."""
import tempfile
import time
import shutil
from storage_engine import LSMStorageEngine


def main(record_count=5000):
    directory = tempfile.mkdtemp(prefix="lsm_benchmark_")
    db = None
    try:
        db = LSMStorageEngine(data_dir=directory, max_memtable_size=1024 * 1024 * 1024)
        start = time.perf_counter()
        for i in range(record_count):
            db.put(f"key:{i:08d}", f"value:{i}")
        write_seconds = time.perf_counter() - start
        db.flush()

        start = time.perf_counter()
        for i in range(record_count):
            assert db.get(f"key:{i:08d}") == f"value:{i}"
        read_seconds = time.perf_counter() - start

        # Generate a few SSTables so compaction has work to do.
        for batch in range(3):
            for i in range(0, record_count, 10):
                db.put(f"key:{i:08d}", f"updated:{batch}:{i}")
            db.flush()
        start = time.perf_counter()
        compact_result = db.compact()
        compact_seconds = time.perf_counter() - start

        print(f"Records: {record_count}")
        print(f"PUT time: {write_seconds:.4f}s ({record_count / max(write_seconds, 1e-9):.0f} ops/s)")
        print(f"GET time: {read_seconds:.4f}s ({record_count / max(read_seconds, 1e-9):.0f} ops/s)")
        print(f"Compaction time: {compact_seconds:.4f}s; {compact_result}")
        print("Benchmark values vary by machine, Python version, and disk. Run several times for comparisons.")
    finally:
        if db is not None:
            db.close()
        shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    main()
