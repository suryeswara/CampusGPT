from functools import lru_cache

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from backend import config


@lru_cache(maxsize=1)
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name=config.EMBED_MODEL,
        encode_kwargs={"normalize_embeddings": True},
    )


@lru_cache(maxsize=1)
def get_vectorstore():
    return Chroma(
        persist_directory=config.DB_DIR,
        embedding_function=get_embeddings(),
        collection_name=config.COLLECTION,
        collection_metadata={"hnsw:space": "cosine"},
    )
