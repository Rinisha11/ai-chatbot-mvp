# backend/cli/ingest.py
# (Create this new file and paste this entire code)

# Upgrade for modular cli utility and multi-tenant segmentation
import asyncio
import os
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv

# Import libraries - we still use langchain offline builder in MVP CLI
# but using paths from the new config structure in Phase 2.
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import CharacterTextSplitter

# Load .env variables locally for this CLI tool
load_dotenv()

# Setup basic logging - CLI output format
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ingest-utility")

# Load essential settings directly from env for this tool
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("FATAL: OPENAI_API_KEY environment variable must be set to run ingestion.")

# We always initialize embeddings once for the script
embeddings = OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL, openai_api_key=OPENAI_API_KEY)


async def run_ingestion_async(site_id: str, data_source_dir: Path, chroma_out_dir: Path):
    """Processes documents for a single tenant into their local vector DB."""
    
    logger.info(f"--- Starting Data Ingestion for Tenant: '{site_id}' ---")
    logger.info(f"Source Data: {data_source_dir}")
    logger.info(f"Output Vector Store: {chroma_out_dir}")

    # Validate Source Data directory exists
    if not data_source_dir.exists():
        logger.error(f"Error: Raw data folder '{data_source_dir}' not found. Ingestion aborted.")
        return

    all_documents = []

    # Source Validation - Segmented path check
    logger.info(f"Scanning '{data_source_dir}' for .pdf and .txt files...")
    for filename in os.listdir(data_source_dir):
        filepath = os.path.join(data_source_dir, filename)

        if filename.lower().endswith(".pdf"):
            try:
                # Optimized for modern async PDF loading
                loader = PyPDFLoader(filepath)
                documents = await loader.aload()
                all_documents.extend(documents)
                logger.info(f"Loaded PDF: {filepath} ({len(documents)} pages)")
            except Exception as exc:
                logger.error(f"Error loading PDF '{filepath}': {exc}")

        elif filename.lower().endswith(".txt"):
            try:
                # TextLoader is typically efficient synchronously
                loader = TextLoader(filepath)
                documents = loader.load()
                all_documents.extend(documents)
                logger.info(f"Loaded TXT: {filepath}")
            except Exception as exc:
                logger.error(f"Error loading TXT '{filepath}': {exc}")

    # Text Splitter - Standardize MVP configuration
    if not all_documents:
        logger.warning(f"No documents found to ingest for tenant '{site_id}' in {data_source_dir}.")
        return

    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    docs = text_splitter.split_documents(all_documents)
    logger.info(f"Split documents into {len(docs)} chunks.")

    # Output Persistence - Segments directory structure enforced
    try:
        os.makedirs(chroma_out_dir, exist_ok=True)
        # MVP Limitation: This script creates LOCAL SQLite files.
        # This will work for Phase 1 local/testing and requires manual
        # migration for a scalable production deployment.
        await Chroma.afrom_documents(docs, embeddings, persist_directory=str(chroma_out_dir))
        logger.info(f"--- Successfully ingested data into '{chroma_out_dir}' (SQLite SQLite fallback) ---")
    except Exception as exc:
        logger.error(f"Error during ingestion for tenant '{site_id}': {exc}")


if __name__ == "__main__":
    # --- Modern CLI Interface ---
    parser = argparse.ArgumentParser(
        description="Multi-Tenant MVP Data Ingest Utility Script",
        epilog="Examples:\n  python -m app.cli.ingest --site_id default-site\n  python -m app.cli.ingest --site_id marketing --data_dir ./data/marketing-custom",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    # REQUIRED arguments for manual operation
    parser.add_argument("--site_id", required=True, help="Site ID (tenant) matching sites.json.")
    
    # OPTIONAL arguments with smart defaults
    parser.add_argument("--data_dir", help="Directory containing raw data (PDF/TXT) (default: ./data/{site_id})")
    # This defaults to the local fallback in config, ensuring segmentation.
    parser.add_argument("--chroma_dir", help="Output Vector Store directory (default: ./akinfoChroma/{site_id})")

    args = parser.parse_args()
    
    # -- CLI Logic --
    # 1. Resolve Data Directory. Segmented MVP pattern enforced: `./data/{site_id}`
    resolved_data_dir = Path(args.data_dir or f"./data/{args.site_id}")
    
    # 2. Resolve Chroma Directory. Segmented pattern enforced: `./akinfoChroma/{site_id}`
    resolved_chroma_dir = Path(args.chroma_dir or f"./akinfoChroma/{args.site_id}")
    
    # 3. Execution (Running async inside sync CLI loop)
    # We must invoke this function from the context of backend directory.
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_ingestion_async(args.site_id, resolved_data_dir, resolved_chroma_dir))