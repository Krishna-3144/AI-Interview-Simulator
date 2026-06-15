# backend/services/memory_service.py
"""
Wraps ChromaDB.
- Each interview session gets its own collection.
- Answers are stored as embeddings so we can do semantic search.
- Used for: "earlier you mentioned X" callbacks + contradiction detection.
"""
from __future__ import annotations
import chromadb
from chromadb.config import Settings as ChromaSettings
from backend.core.config import settings

_client = chromadb.PersistentClient(
    path=settings.CHROMA_PERSIST_DIR,
    settings=ChromaSettings(anonymized_telemetry=False),
)


def get_collection(session_id: str):
    return _client.get_or_create_collection(
        name=f"session_{session_id}",
        metadata={"hnsw:space": "cosine"},
    )


def store_answer(session_id: str, question_id: str, question: str, answer: str, topic: str):
    col = get_collection(session_id)
    col.add(
        ids=[question_id],
        documents=[f"Q: {question}\nA: {answer}"],
        metadatas=[{"topic": topic, "question": question, "answer": answer}],
    )


def search_similar(session_id: str, query: str, n_results: int = 3) -> list[dict]:
    col = get_collection(session_id)
    count = col.count()
    if count == 0:
        return []
    results = col.query(
        query_texts=[query],
        n_results=min(n_results, count),
    )
    items = []
    for i, doc in enumerate(results["documents"][0]):
        items.append({
            "document": doc,
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })
    return items


def get_all_answers(session_id: str) -> list[dict]:
    col = get_collection(session_id)
    if col.count() == 0:
        return []
    results = col.get(include=["documents", "metadatas"])
    items = []
    for i, doc in enumerate(results["documents"]):
        items.append({
            "document": doc,
            "metadata": results["metadatas"][i],
        })
    return items


def delete_session_memory(session_id: str):
    try:
        _client.delete_collection(f"session_{session_id}")
    except Exception:
        pass
