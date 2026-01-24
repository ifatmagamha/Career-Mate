from __future__ import annotations

import pandas as pd
import streamlit as st
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from src.config.settings import settings

def query_store(query: str, k: int = 3):
    """
    Public accessor for RAG Agent.
    """
    store = get_vector_store()
    if not store:
        return []
    
    return store.similarity_search(query, k=k)

def get_vector_store():
    # Setup embeddings
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=settings.GEMINI_API_KEY)
    
    # Use FAISS (In-Memory)
    try:
        # We try to load local index if exists
        vector_store = FAISS.load_local(
            folder_path=f"{settings.DATA_DIR}/faiss_index", 
            embeddings=embeddings,
            allow_dangerous_deserialization=True
        )
        return vector_store
    except Exception:
        # Return none if no index yet
        return None

from langchain_text_splitters import RecursiveCharacterTextSplitter

def create_vector_store(texts: list[str], metadatas: list[dict] = None):
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=settings.GEMINI_API_KEY)
    
    # RAG best practice: Chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
    )
    
    douments = text_splitter.create_documents(texts, metadatas=metadatas)
    
    vector_store = FAISS.from_documents(douments, embeddings)
    vector_store.save_local(f"{settings.DATA_DIR}/faiss_index")
    return vector_store
