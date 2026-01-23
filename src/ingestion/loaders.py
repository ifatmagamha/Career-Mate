from pathlib import Path
from typing import List

from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredMarkdownLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config.logging import logger

def load_pdf(file_path: str | Path) -> List[Document]:
    """Loads a PDF file."""
    path = Path(file_path)
    if not path.exists():
        logger.warning(f"PDF file not found: {path}")
        return []
    
    loader = PyPDFLoader(str(path))
    docs = loader.load()
    logger.info(f"Loaded {len(docs)} pages from {path.name}")
    return docs

def load_text(file_path: str | Path) -> List[Document]:
    """Loads a Text/Markdown file."""
    path = Path(file_path)
    if not path.exists():
        logger.warning(f"File not found: {path}")
        return []
    
    try:
        if path.suffix.lower() == ".md":
            loader = UnstructuredMarkdownLoader(str(path))
        else:
            loader = TextLoader(str(path), encoding="utf-8")
        
        docs = loader.load()
        logger.info(f"Loaded {len(docs)} documents from {path.name}")
        return docs
    except Exception as e:
        logger.error(f"Failed to load text {path}: {e}")
        return []

def split_documents(documents: List[Document], chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Document]:
    """Splits documents into smaller chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = splitter.split_documents(documents)
    logger.info(f"Split {len(documents)} docs into {len(chunks)} chunks.")
    return chunks
