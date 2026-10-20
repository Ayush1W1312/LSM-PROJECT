from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from storage_engine import LSMStorageEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.storage = LSMStorageEngine(data_dir="data")
    try:
        yield
    finally:
        app.state.storage.close()


app = FastAPI(title="LSM-Tree DB Engine", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class KeyValue(BaseModel):
    key: str
    value: str


class KeyOnly(BaseModel):
    key: str


@app.get("/")
def root():
    return {"message": "LSM-Tree DB Engine is running", "docs": "/docs"}


@app.post("/put")
def put_item(item: KeyValue):
    if not item.key:
        raise HTTPException(status_code=400, detail="Key cannot be empty")
    try:
        app.state.storage.put(item.key, item.value)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Write failed: {exc}") from exc
    return {"status": "success", "message": f"Stored key '{item.key}'"}


@app.get("/get/{key:path}")
def get_item(key: str):
    value = app.state.storage.get(key)
    if value is None:
        return {"status": "not_found", "key": key, "value": None}
    return {"status": "found", "key": key, "value": value}


@app.delete("/delete/{key:path}")
def delete_item(key: str):
    try:
        app.state.storage.delete(key)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Delete failed: {exc}") from exc
    return {"status": "success", "message": f"Deleted key '{key}' if it existed"}


@app.post("/flush")
def flush_items():
    try:
        app.state.storage.flush()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Flush failed: {exc}") from exc
    return {"status": "success", "message": "MemTable flush completed"}


@app.post("/compact")
def compact_tables():
    try:
        result = app.state.storage.compact()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Compaction failed: {exc}") from exc
    return {"status": "success", **result}


@app.get("/health")
def health():
    return {"status": "ok", "sstable_count": app.state.storage.sstable_count,
            "memtable_size_bytes": app.state.storage.memtable.size_bytes}
