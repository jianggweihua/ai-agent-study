from __future__ import annotations

import hashlib
import json
import math
import re
import threading
from functools import lru_cache
from pathlib import Path

import chromadb

from app.embedding import MODEL_NAME, get_embedding


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_PATH = PROJECT_ROOT / "data" / "company_docs.txt"
CHROMA_PATH = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "company_docs_embedding_v1"
MAX_CHUNK_CHARS = 180
CHUNK_OVERLAP = 30
INDEX_VERSION = 2
MIN_SIMILARITY = 0.30
MIN_SCORE_GAP = 0.06
NO_RESULT = "没有找到相关资料"

# all-MiniLM-L6-v2 is an English model. Add a short English concept hint to
# Chinese text before embedding so the requested model can compare Chinese
# policy queries and documents meaningfully; Chroma still stores the original
# Chinese chunks as the retrievable documents.
_CONCEPT_HINTS = (
    ("员工培训", "employee training"),
    ("培训", "professional skills training"),
    ("请假", "employee leave absence vacation"),
    ("休假", "employee leave absence vacation"),
    ("病假", "sick leave medical certificate"),
    ("事假", "personal leave manager approval"),
    ("报销", "expense reimbursement receipts"),
    ("票据", "receipts invoice"),
    ("主管", "supervisor manager approval"),
    ("部门负责人", "department head approval"),
)
_STOP_TERMS = {
    "公司", "员工", "制度", "政策", "规定", "查询", "问题", "请问",
    "关于", "怎么", "如何", "什么", "哪些", "是否", "可以", "需要",
}
_INDEX_LOCK = threading.RLock()


@lru_cache(maxsize=1)
def _get_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=str(CHROMA_PATH))


def _embedding_text(text: str) -> str:
    hints: list[str] = []
    for phrase, hint in _CONCEPT_HINTS:
        if phrase in text and hint not in hints:
            hints.append(hint)
    return f"{text}\n{'; '.join(hints)}" if hints else text


def _split_documents(text: str) -> list[str]:
    """Split blank-line-delimited sections, keeping headings with their lists."""
    normalized = re.sub(
        r"(?m)^([^\r\n]{2,50}[：:])\r?\n\s*\r?\n(?=\s*\d+[.、])",
        r"\1\n",
        text.strip(),
    )
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
    chunks: list[str] = []

    for paragraph in paragraphs:
        if len(paragraph) <= MAX_CHUNK_CHARS:
            chunks.append(paragraph)
            continue

        remaining = paragraph
        while len(remaining) > MAX_CHUNK_CHARS:
            split_at = remaining.rfind("\n", 0, MAX_CHUNK_CHARS + 1)
            if split_at < MAX_CHUNK_CHARS // 2:
                split_at = MAX_CHUNK_CHARS
            chunks.append(remaining[:split_at].strip())
            remaining = remaining[max(split_at - CHUNK_OVERLAP, 1):].strip()
        if remaining:
            chunks.append(remaining)

    return chunks


def _ensure_index():
    source_text = DOCUMENT_PATH.read_text(encoding="utf-8-sig")
    chunks = _split_documents(source_text)
    # Any change to the source, model or preprocessing must rebuild the vectors.
    index_inputs = json.dumps(
        [INDEX_VERSION, MODEL_NAME, MAX_CHUNK_CHARS, CHUNK_OVERLAP,
         _CONCEPT_HINTS, source_text],
        ensure_ascii=False,
    )
    digest = hashlib.sha256(index_inputs.encode("utf-8")).hexdigest()
    client = _get_client()

    with _INDEX_LOCK:
        names = {
            item if isinstance(item, str) else item.name
            for item in client.list_collections()
        }
        if COLLECTION_NAME in names:
            collection = client.get_collection(name=COLLECTION_NAME, embedding_function=None)
        else:
            collection = client.create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
                embedding_function=None,
            )

        metadata = collection.metadata or {}
        if metadata.get("index_fingerprint") != digest or collection.count() != len(chunks):
            # Compute embeddings before modifying a valid index. A model-load
            # failure must not erase the last successfully built collection.
            embeddings = [get_embedding(_embedding_text(chunk)) for chunk in chunks]
            ids = [f"company-doc-{digest[:16]}-{index:04d}" for index in range(len(chunks))]
            previous_ids = collection.get(include=["metadatas"])["ids"]
            if chunks:
                collection.upsert(
                    ids=ids,
                    documents=chunks,
                    metadatas=[
                        {"source": str(DOCUMENT_PATH.relative_to(PROJECT_ROOT)), "chunk": index}
                        for index in range(len(chunks))
                    ],
                    embeddings=embeddings,
                )
            stale_ids = sorted(set(previous_ids) - set(ids))
            if stale_ids:
                collection.delete(ids=stale_ids)
            collection.modify(
                metadata={"embedding_model": MODEL_NAME, "index_fingerprint": digest}
            )
        return collection


def _terms(text: str) -> set[str]:
    terms = {
        word.lower()
        for word in re.findall(r"[a-zA-Z0-9]+", text)
        if len(word) > 1 and word.lower() not in _STOP_TERMS
    }
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        terms.update(run[index:index + 2] for index in range(len(run) - 1))
    return terms - _STOP_TERMS


def _lexical_score(question: str, document: str, documents: list[str]) -> float:
    query_terms = _terms(question)
    if not query_terms:
        return 0.0

    document_terms = _terms(document)
    all_document_terms = [_terms(item) for item in documents]
    weights = {
        term: math.log((len(all_document_terms) + 1) / (1 + sum(term in terms for terms in all_document_terms))) + 1
        for term in query_terms
    }
    total_weight = sum(weights.values())
    if total_weight == 0:
        return 0.0
    return sum(weight for term, weight in weights.items() if term in document_terms) / total_weight


def rag_search(question: str) -> str:
    """Retrieve the closest relevant company policy section from ChromaDB."""
    if not isinstance(question, str) or not question.strip():
        return NO_RESULT
    if not DOCUMENT_PATH.is_file():
        return "知识库文件不存在"

    with _INDEX_LOCK:
        collection = _ensure_index()
        if collection.count() == 0:
            return NO_RESULT
        query_vector = get_embedding(_embedding_text(question))
        result = collection.query(
            query_embeddings=[query_vector],
            n_results=min(5, collection.count()),
            include=["documents", "distances"],
        )
    documents = result["documents"][0]
    distances = result["distances"][0]
    if not documents:
        return NO_RESULT

    # Keep Chroma's cosine-distance order. The model is weak on Chinese, so an
    # ambiguous nearest neighbour also needs lexical evidence; a clear semantic
    # match (e.g. 休假 -> 请假) can pass without any shared words.
    similarity = 1.0 - float(distances[0])
    if similarity < MIN_SIMILARITY:
        return NO_RESULT
    score_gap = float(distances[1]) - float(distances[0]) if len(distances) > 1 else 0.0
    if score_gap < MIN_SCORE_GAP:
        query_concepts = {hint for phrase, hint in _CONCEPT_HINTS if phrase in question}
        document_concepts = {hint for phrase, hint in _CONCEPT_HINTS if phrase in documents[0]}
        if not query_concepts.intersection(document_concepts) and _lexical_score(question, documents[0], documents) < 0.16:
            return NO_RESULT
    return documents[0]
