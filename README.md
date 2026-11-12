# LSM-Tree Based Key-Value Storage Engine

A Python-based key-value storage engine built from scratch using the **Log-Structured Merge Tree (LSM-Tree)** architecture. The project explores how modern storage engines manage writes, organize data across memory and disk, recover from failures, and optimize read performance.

## Overview

This project implements an LSM-Tree based storage engine that combines an in-memory data structure with persistent disk-based storage.

Instead of directly modifying data on disk for every write, the engine first records operations in a Write-Ahead Log (WAL) and maintains data in an in-memory MemTable. Once the MemTable reaches its flush threshold, its contents are written to immutable Sorted String Tables (SSTables).

To improve lookup performance, the engine incorporates Bloom Filters and Sparse Indexing. It also implements compaction to merge SSTables and maintain an efficient on-disk storage structure.

## Architecture

The storage engine follows a write-optimized architecture consisting of the following components:

### 1. Write-Ahead Log (WAL)

The WAL provides durability by recording write operations before they are applied to the in-memory storage structure.

- Records write operations in an append-only log.
- Uses file synchronization to improve durability.
- Supports recovery by replaying logged operations after a restart.
- Helps restore the MemTable following an unexpected shutdown.

### 2. MemTable (Skip List)

The MemTable stores recently written key-value pairs in memory using a Skip List.

- Maintains keys in sorted order.
- Supports efficient insertion, deletion, and lookup operations.
- Provides expected O(log N) search and insertion complexity.
- Acts as the in-memory buffer before data is flushed to disk.

### 3. SSTable (Sorted String Table)

SSTables provide persistent, immutable storage for sorted key-value records.

- Flushes MemTable data into disk-based SSTable files.
- Stores records in sorted order.
- Uses file offsets to locate records efficiently.
- Supports reading records directly from disk.
- Maintains a sparse index to accelerate key lookups.

### 4. Bloom Filter

Bloom Filters help reduce unnecessary disk reads during key lookups.

- Uses a probabilistic data structure to test key membership.
- Quickly identifies keys that are definitely absent.
- Reduces unnecessary SSTable access.
- Allows false positives but does not produce false negatives under normal operation.

### 5. Sparse Indexing

Sparse indexing improves the efficiency of searching through SSTables.

- Stores selected keys and their corresponding file offsets.
- Narrows down the search region within an SSTable.
- Reduces the amount of disk data that needs to be scanned.

### 6. Compaction

Compaction merges existing SSTables into a consolidated sorted structure.

- Reads and merges records from multiple SSTables.
- Maintains sorted key-value data.
- Resolves multiple versions of the same key according to the engine's version-selection rules.
- Helps control the accumulation of SSTable files.

## Data Flow

### Write Path

1. A write operation is received by the storage engine.
2. The operation is appended to the Write-Ahead Log.
3. The data is inserted into the in-memory MemTable.
4. When the MemTable reaches its configured threshold, its contents are flushed to a new SSTable.
5. The SSTable and its associated indexing structures are published to disk.

### Read Path

1. A read request is received for a particular key.
2. The engine checks the in-memory MemTable first.
3. If the key is not found, the engine searches the available SSTables.
4. Bloom Filters help eliminate SSTables that definitely do not contain the key.
5. Sparse indexes help locate the relevant region within an SSTable.
6. The matching record is retrieved from disk.

### Recovery Path

1. The engine loads its persisted storage metadata.
2. The WAL is read to identify operations that need recovery.
3. Valid logged operations are replayed into the MemTable.
4. The engine restores its in-memory state and becomes ready to process requests.

## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| Storage Architecture | LSM-Tree |
| In-Memory Data Structure | Skip List |
| Persistent Storage | SSTables |
| Durability | Write-Ahead Logging |
| Read Optimization | Bloom Filters |
| Disk Lookup Optimization | Sparse Indexing |

## Project Structure

The implementation is organized into separate modules for storage management and individual LSM-Tree components.

| Module | Responsibility |
|---|---|
| `wal.py` | Write-Ahead Logging and recovery |
| `memtable.py` | Skip List-based in-memory storage |
| SSTable modules | Writing and reading immutable disk tables |
| Storage engine module | Coordinates writes, reads, flushing, recovery, and compaction |

*Refer to the source files for the exact module names and implementation details.*

## Key Engineering Concepts

This project explores several important database-engineering concepts:

- Write-optimized storage architectures.
- In-memory indexing using Skip Lists.
- Append-only logging and crash recovery.
- Immutable disk-based storage structures.
- Probabilistic data structures.
- File offsets and disk-level record access.
- Sparse indexing and lookup optimization.
- SSTable merging and compaction.

## Future Improvements

- Range queries and efficient sequential scans.
- Background compaction.
- Multi-level SSTable organization.
- Concurrent read and write support.
- Benchmarking against alternative storage structures.
- Improved crash consistency and fault-injection testing.

## Author

**Ayush Gusain**

- GitHub: [Ayush1W1312](https://github.com/Ayush1W1312)
- LinkedIn: [Ayush Gusain](https://linkedin.com/in/ayush-gusain-090bb632a)
