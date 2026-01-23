import os
from pathlib import Path

from src.config.settings import settings
from src.config.logging import logger
from src.ingestion.loaders import load_pdf, load_text, split_documents
from src.storage.vector_store import add_documents_to_store

def ingest_personal_docs():
    """
    Ingests CVs and Templates from the data directory.
    Target files:
    - data/cv_en.pdf
    - data/cv_fr.pdf
    - data/templates/*.md
    - data/templates/*.txt
    """
    data_dir = Path(settings.DATA_DIR)
    
    docs = []
    
    # 1. Load CVs
    cv_files = ["cv_en.pdf", "cv_fr.pdf", "my_cv_en.pdf", "my_cv_fr.pdf"] # Variants
    for cv in cv_files:
        f = data_dir / cv
        if f.exists():
            # Tag metadata
            loaded = load_pdf(f)
            for d in loaded:
                d.metadata["category"] = "cv"
                d.metadata["source"] = cv
            docs.extend(loaded)

    # 2. Load Templates
    templates_dir = data_dir / "templates"
    if templates_dir.exists():
        for t_file in templates_dir.glob("*"):
            if t_file.suffix in [".txt", ".md"]:
                loaded = load_text(t_file)
                for d in loaded:
                    d.metadata["category"] = "template"
                    d.metadata["template_name"] = t_file.stem
                docs.extend(loaded)
    
    if not docs:
        logger.warning("[ingest] No documents found to ingest.")
        return

    # 3. Split
    chunks = split_documents(docs)
    
    # 4. Store
    add_documents_to_store(chunks)
    logger.info("[ingest] Ingestion complete.")

if __name__ == "__main__":
    ingest_personal_docs()
