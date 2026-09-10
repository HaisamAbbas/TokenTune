"""Minimal fixture-corpus ingestion script for the sample RAG app.

Reads the short text documents under `corpus/`, embeds each one with the
dense embedding service configured via `rag.config` (TEI serving BAAI/bge-m3
by default) and with the sparse BM25 model used by `QdrantSearch`, then
(re)creates the Qdrant collection and upserts the points.

This intentionally replaces the source app's Wikipedia/Docling ingestion
notebook (`notebooks/create_collection.py` in the upstream repo) with
something small enough to run in a few seconds for demo/smoke-test purposes.

Usage (from the `sample-rag-app` directory, with the app's env vars set,
e.g. via `docker compose run --rm sample-rag-app python scripts/ingest.py`):

    uv run python scripts/ingest.py
"""

import asyncio
from pathlib import Path

from fastembed import SparseTextEmbedding
from qdrant_client import models

from rag import config

CORPUS_DIR = Path(__file__).parent.parent / "corpus"

DENSE_INDEX = "dense"
SPARSE_INDEX = "sparse"

# Dimensionality of BAAI/bge-m3 dense embeddings.
DENSE_SIZE = 1024


async def main() -> None:
    """Embed and upsert every document in `corpus/` into the Qdrant collection."""
    settings = config.settings
    embed = config.get_openai_embed()
    qdrant = config.get_qdrant().qdrant
    bm25 = SparseTextEmbedding(model_name="Qdrant/bm25")

    paths = sorted(CORPUS_DIR.glob("*.txt"))
    if not paths:
        raise SystemExit(f"No documents found in {CORPUS_DIR}")

    print(f"Found {len(paths)} documents in {CORPUS_DIR}")

    documents = [path.read_text(encoding="utf-8").strip() for path in paths]

    print(f"Recreating Qdrant collection '{settings.qdrant_collection}'...")
    await qdrant.recreate_collection(
        collection_name=settings.qdrant_collection,
        vectors_config={
            DENSE_INDEX: models.VectorParams(
                size=DENSE_SIZE, distance=models.Distance.COSINE
            )
        },
        sparse_vectors_config={SPARSE_INDEX: models.SparseVectorParams()},
    )

    points = []
    for i, (path, text) in enumerate(zip(paths, documents, strict=True), start=1):
        print(f"Embedding ({i}/{len(documents)}): {path.name}")

        dense_vector = await embed.generate_embedding(text=text)
        sparse_vector = next(iter(bm25.query_embed(text)))

        points.append(
            models.PointStruct(
                id=i,
                vector={
                    DENSE_INDEX: dense_vector,
                    SPARSE_INDEX: models.SparseVector(
                        indices=sparse_vector.indices.astype(float).tolist(),
                        values=sparse_vector.values.astype(float).tolist(),
                    ),
                },
                payload={"content": text, "source": path.name},
            )
        )

    print(f"Upserting {len(points)} points...")
    await qdrant.upsert(settings.qdrant_collection, points, wait=True)

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
