# src/rag/constants.py
from __future__ import annotations

MIN_CLEAN_LEN = 500          # en dessous => trop pauvre, on ignore RAG
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150
TOP_K = 4                    # nb de chunks à injecter dans le prompt
MAX_CONTEXT_CHARS = 3500     # limite pour ne pas exploser tokens
