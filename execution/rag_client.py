#!/usr/bin/env python3
"""
Beauty Connect Shop — RAG Knowledge Base Client
DO Architecture Execution Script

Indexes all directives/brand/*.md files into ChromaDB and provides
semantic query interface for the blog generator.

Usage:
    # Index / re-index knowledge base (run after adding/editing brand docs)
    python execution/rag_client.py --index

    # Query the knowledge base (for testing)
    python execution/rag_client.py --query "acne treatment protocol" --n 5

    # List all indexed documents
    python execution/rag_client.py --list
"""

import os
import sys
import argparse
import logging
import re
from typing import List, Dict, Optional
from pathlib import Path

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ─── Constants ─────────────────────────────────────────────────────────────────
CHROMA_DB_PATH = ".tmp/chroma_db"
COLLECTION_NAME = "beauty_connect_kb"
KNOWLEDGE_BASE_DIR = "directives/brand"

# Map filenames to semantic categories for filtered queries
CATEGORY_MAP = {
    "brand_voice.md": "brand_voice",
    "eeat_signals.md": "eeat_signals",
    "product_catalog.md": "products",
    "protocols.md": "protocols",
    "ingredient_library.md": "ingredients",
}


# ─── Chunking ──────────────────────────────────────────────────────────────────

def chunk_markdown(text: str, source_file: str, category: str) -> List[Dict]:
    """
    Split markdown into chunks on ## headings.
    Each chunk = one H2 section with its full content.
    Includes the H2 heading in the chunk for context.

    Returns list of: {text, metadata{source, category, heading, chunk_index}}
    """
    chunks = []

    # Split on ## (H2) boundaries — keep the heading with its content
    sections = re.split(r'\n(?=## )', text)

    for i, section in enumerate(sections):
        section = section.strip()
        if not section or len(section) < 50:
            continue

        # Extract heading for metadata
        heading_match = re.match(r'^#+\s+(.+)', section)
        heading = heading_match.group(1).strip() if heading_match else f"Section {i}"

        # For very long sections, sub-chunk on ### boundaries
        if len(section) > 1500:
            sub_sections = re.split(r'\n(?=### )', section)
            for j, sub in enumerate(sub_sections):
                sub = sub.strip()
                if len(sub) < 50:
                    continue
                sub_heading_match = re.match(r'^#+\s+(.+)', sub)
                sub_heading = sub_heading_match.group(1).strip() if sub_heading_match else heading
                chunks.append({
                    "text": sub,
                    "metadata": {
                        "source": source_file,
                        "category": category,
                        "heading": sub_heading,
                        "chunk_index": f"{i}_{j}"
                    }
                })
        else:
            chunks.append({
                "text": section,
                "metadata": {
                    "source": source_file,
                    "category": category,
                    "heading": heading,
                    "chunk_index": str(i)
                }
            })

    return chunks


# ─── RAG Client ────────────────────────────────────────────────────────────────

class KnowledgeBaseRAG:
    """
    Manages the ChromaDB vector store for Beauty Connect Shop knowledge base.

    Indexing: Reads all directives/brand/*.md files, chunks by H2 section,
              embeds using ChromaDB's default embedding function (sentence-transformers).

    Querying: Returns the top-N most semantically relevant chunks for a query.
    """

    def __init__(self, persist_dir: str = CHROMA_DB_PATH):
        try:
            import chromadb
            from chromadb.utils import embedding_functions
        except ImportError:
            logger.error("chromadb not installed. Run: pip install chromadb")
            sys.exit(1)

        os.makedirs(persist_dir, exist_ok=True)

        self._chromadb = chromadb
        self._ef = embedding_functions

        self.client = chromadb.PersistentClient(path=persist_dir)
        self._collection = None

    def _get_embedding_function(self):
        """Use sentence-transformers (free, local) for embeddings."""
        try:
            return self._ef.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
        except Exception as e:
            logger.warning(f"SentenceTransformer not available: {e}. Falling back to default.")
            return self._ef.DefaultEmbeddingFunction()

    def _get_collection(self, create_if_missing: bool = False):
        """Get or create the ChromaDB collection."""
        ef = self._get_embedding_function()
        if create_if_missing:
            return self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=ef,
                metadata={"description": "Beauty Connect Shop brand knowledge base"}
            )
        try:
            return self.client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=ef
            )
        except Exception:
            return None

    def index(self, kb_dir: str = KNOWLEDGE_BASE_DIR) -> Dict:
        """
        Index all .md files in the knowledge base directory into ChromaDB.
        Deletes and recreates the collection on each run to stay fresh.
        """
        kb_path = Path(kb_dir)
        if not kb_path.exists():
            logger.error(f"Knowledge base directory not found: {kb_dir}")
            return {"success": False, "error": f"Directory not found: {kb_dir}"}

        # Delete existing collection to start fresh
        try:
            self.client.delete_collection(COLLECTION_NAME)
            logger.info("Deleted existing collection — re-indexing from scratch")
        except Exception:
            pass  # Collection didn't exist yet

        collection = self._get_collection(create_if_missing=True)
        self._collection = collection

        all_chunks = []
        files_indexed = []

        md_files = list(kb_path.glob("*.md"))
        if not md_files:
            logger.warning(f"No .md files found in {kb_dir}")
            return {"success": False, "error": "No markdown files found"}

        for md_file in md_files:
            filename = md_file.name
            category = CATEGORY_MAP.get(filename, "general")

            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            chunks = chunk_markdown(content, filename, category)
            all_chunks.extend(chunks)
            files_indexed.append(f"{filename} ({len(chunks)} chunks)")
            logger.info(f"  Chunked: {filename} → {len(chunks)} chunks")

        if not all_chunks:
            return {"success": False, "error": "No chunks generated from files"}

        # Add to ChromaDB in batches of 100
        batch_size = 100
        total_added = 0

        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]

            documents = [c["text"] for c in batch]
            metadatas = [c["metadata"] for c in batch]
            # IDs must be unique strings
            ids = [f"{c['metadata']['source']}_{c['metadata']['chunk_index']}" for c in batch]

            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            total_added += len(batch)

        logger.info(f"✓ Indexed {total_added} chunks from {len(files_indexed)} files")

        return {
            "success": True,
            "total_chunks": total_added,
            "files": files_indexed
        }

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        category: Optional[str] = None,
        min_chars: int = 100
    ) -> str:
        """
        Query the knowledge base and return relevant chunks as formatted text.

        Args:
            query_text: Natural language query (e.g., "acne treatment protocol")
            n_results: Number of top chunks to return
            category: Optional filter — "products" | "protocols" | "ingredients"
                      | "eeat_signals" | "brand_voice"
            min_chars: Minimum chunk length to include

        Returns:
            Formatted string of relevant knowledge chunks for use in LLM prompts.
        """
        if self._collection is None:
            self._collection = self._get_collection(create_if_missing=False)

        if self._collection is None:
            logger.warning("Knowledge base not indexed. Run: python execution/rag_client.py --index")
            return ""

        try:
            where = {"category": category} if category else None

            total = self._collection.count()
            if total == 0:
                return ""

            results = self._collection.query(
                query_texts=[query_text],
                n_results=min(n_results, total),
                where=where
            )

            if not results or not results.get("documents") or not results["documents"][0]:
                return ""

            chunks = []
            for doc, meta, distance in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            ):
                if len(doc) < min_chars:
                    continue
                # Lower distance = more relevant (cosine similarity)
                relevance = round(1 - distance, 3)
                source_label = f"{meta['source']} › {meta['heading']}"
                chunks.append(f"[{source_label}] (relevance: {relevance})\n{doc}")

            return "\n\n---\n\n".join(chunks)

        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return ""

    def query_multi(self, queries: Dict[str, str], n_per_query: int = 3) -> Dict[str, str]:
        """
        Run multiple targeted queries at once.

        Args:
            queries: Dict of {label: query_text}
                     e.g. {"products": "acne products", "protocols": "acne protocol steps"}
            n_per_query: Results per query

        Returns:
            Dict of {label: formatted_results}
        """
        results = {}
        for label, query_text in queries.items():
            results[label] = self.query(query_text, n_results=n_per_query)
        return results

    def build_article_context(self, keyword: str, intent: str) -> Dict[str, str]:
        """
        Build a complete context packet for article generation.
        Runs 5 targeted queries to retrieve all relevant knowledge.

        Args:
            keyword: Article keyword (e.g., "snail mucin serum sensitive skin")
            intent: "informational" | "commercial"

        Returns:
            Dict with keys: brand_voice, products, protocols, ingredients, eeat_signals
        """
        logger.info(f"Building RAG context for: '{keyword}' ({intent})")

        context = {}

        # Always load full brand voice (small file, always relevant)
        context["brand_voice"] = self.query(
            "brand voice tone writing style health canada compliance",
            n_results=6,
            category="brand_voice"
        )

        # Keyword-relevant products (more results for commercial intent)
        n_products = 5 if intent == "commercial" else 3
        context["products"] = self.query(
            f"{keyword} product recommendation",
            n_results=n_products,
            category="products"
        )

        # Relevant protocols
        context["protocols"] = self.query(
            f"{keyword} treatment protocol steps",
            n_results=3,
            category="protocols"
        )

        # Relevant ingredients
        context["ingredients"] = self.query(
            f"{keyword} ingredient how it works",
            n_results=4,
            category="ingredients"
        )

        # E-E-A-T signals
        context["eeat_signals"] = self.query(
            f"{keyword} {intent} brand authority trust experience",
            n_results=4,
            category="eeat_signals"
        )

        # Log what was retrieved
        for key, val in context.items():
            chunk_count = val.count("---") + 1 if val else 0
            logger.info(f"  RAG [{key}]: {chunk_count} chunks retrieved")

        return context

    def list_documents(self) -> List[Dict]:
        """List all indexed documents with metadata."""
        collection = self._get_collection()
        if not collection:
            return []
        result = collection.get(include=["metadatas"])
        return result.get("metadatas", [])

    def count(self) -> int:
        """Return total number of indexed chunks."""
        collection = self._get_collection()
        if not collection:
            return 0
        return collection.count()


# ─── Singleton for use in blog generator ───────────────────────────────────────

_rag_instance: Optional[KnowledgeBaseRAG] = None


def get_rag() -> KnowledgeBaseRAG:
    """Get or create the singleton RAG client instance."""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = KnowledgeBaseRAG()
    return _rag_instance


# ─── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Beauty Connect Shop — RAG Knowledge Base Manager"
    )
    parser.add_argument("--index", action="store_true",
                        help="Index/re-index all brand knowledge files into ChromaDB")
    parser.add_argument("--query", type=str,
                        help="Query the knowledge base with a text string")
    parser.add_argument("--n", type=int, default=5,
                        help="Number of results to return (default: 5)")
    parser.add_argument("--category", type=str,
                        choices=["products", "protocols", "ingredients", "eeat_signals", "brand_voice"],
                        help="Filter results by category")
    parser.add_argument("--list", action="store_true",
                        help="List all indexed documents")
    parser.add_argument("--context", type=str,
                        help="Build full article context for a keyword (test mode)")
    parser.add_argument("--intent", type=str, default="informational",
                        choices=["informational", "commercial"],
                        help="Intent for --context mode")
    args = parser.parse_args()

    rag = KnowledgeBaseRAG()

    if args.index:
        print("\n=== Indexing Knowledge Base ===")
        result = rag.index()
        if result["success"]:
            print(f"\n✓ Indexed {result['total_chunks']} chunks")
            print("Files:")
            for f in result["files"]:
                print(f"  - {f}")
        else:
            print(f"\n❌ Indexing failed: {result.get('error')}")

    elif args.query:
        print(f"\n=== Querying: '{args.query}' ===")
        count = rag.count()
        if count == 0:
            print("❌ Knowledge base is empty. Run: python execution/rag_client.py --index")
            return
        result = rag.query(args.query, n_results=args.n, category=args.category)
        if result:
            print(result)
        else:
            print("No results found.")

    elif args.list:
        print("\n=== Indexed Documents ===")
        docs = rag.list_documents()
        if not docs:
            print("No documents indexed. Run: python execution/rag_client.py --index")
            return
        by_file: Dict[str, List] = {}
        for meta in docs:
            src = meta.get("source", "unknown")
            by_file.setdefault(src, []).append(meta.get("heading", "—"))
        for src, headings in sorted(by_file.items()):
            print(f"\n{src} ({len(headings)} chunks):")
            for h in headings:
                print(f"  • {h}")
        print(f"\nTotal: {len(docs)} chunks across {len(by_file)} files")

    elif args.context:
        print(f"\n=== Article Context: '{args.context}' ({args.intent}) ===")
        count = rag.count()
        if count == 0:
            print("❌ Knowledge base is empty. Run: python execution/rag_client.py --index")
            return
        context = rag.build_article_context(args.context, args.intent)
        for key, val in context.items():
            print(f"\n{'='*50}")
            print(f"[{key.upper()}]")
            print('='*50)
            print(val[:800] + "..." if len(val) > 800 else val)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
