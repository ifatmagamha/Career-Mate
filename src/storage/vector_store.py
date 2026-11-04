from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

from src.config.logging import logger
from src.config.settings import settings
from src.llm.port import llm

INDEX_DIR = Path(settings.DATA_DIR) / "faiss_index"
META_FILE = "meta.json"  # which embedding model built the index (spec v0.1, D3)


class PortEmbeddings(Embeddings):
    """LangChain-facing embeddings that go through LLMPort (role 'embed')."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), 100):  # provider batch limit
            vectors += llm.embed(texts[i : i + 100])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return llm.embed([text])[0]


def query_store(query: str, k: int = 3):
    """
    Public accessor for RAG Agent.
    """
    store = get_vector_store()
    if not store:
        return []

    return store.similarity_search(query, k=k)

def get_vector_store():
    if not (INDEX_DIR / "index.faiss").exists():
        return None

    current = llm.config("embed").model
    try:
        built_with = json.loads((INDEX_DIR / META_FILE).read_text(encoding="utf-8"))["embedding_model"]
    except (OSError, ValueError, KeyError):
        built_with = "unknown"
    if built_with != current:
        # Vectors from different models are not comparable: searching would return noise
        logger.warning(f"[vector_store] index built with '{built_with}', embed role is '{current}': re-upload the CV to rebuild it")
        return None

    return FAISS.load_local(
        folder_path=str(INDEX_DIR),
        embeddings=PortEmbeddings(),
        allow_dangerous_deserialization=True
    )

from langchain_text_splitters import RecursiveCharacterTextSplitter

def create_vector_store(texts: list[str], metadatas: list[dict] = None):
    # RAG best practice: Chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
    )

    douments = text_splitter.create_documents(texts, metadatas=metadatas)
    return save_documents(douments)

def save_documents(documents):
    vector_store = FAISS.from_documents(documents, PortEmbeddings())
    vector_store.save_local(str(INDEX_DIR))
    (INDEX_DIR / META_FILE).write_text(json.dumps({"embedding_model": llm.config("embed").model}), encoding="utf-8")
    return vector_store
