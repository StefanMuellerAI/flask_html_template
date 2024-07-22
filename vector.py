import re
import chromadb
import chromadb.utils.embedding_functions as embedding_functions
from dotenv import load_dotenv
import os
import fitz  # PyMuPDF
import hashlib
import tiktoken
from typing import List
from openai import AzureOpenAI
import logging

load_dotenv()


chroma_client = chromadb.PersistentClient(path="chroma")

AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_MODEL = os.getenv("AZURE_MODEL", "gpt-35-turbo")
AZURE_EMBEDDING_MODEL = os.getenv("AZURE_EMBEDDING_MODEL", "text-embedding-ada-002")

azure_openai_client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    api_version="2024-02-15-preview",
    azure_endpoint=AZURE_ENDPOINT
)

def clean_collection_name(name: str) -> str:
    umlaut_mapping = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
        'ß': 'ss'
    }
    for umlaut, replacement in umlaut_mapping.items():
        name = name.replace(umlaut, replacement)
    return re.sub(r'\W+', '_', name)

def list_collections() -> List[str]:
    collections = chroma_client.list_collections()
    return [collection.name for collection in collections]

def collection_exists(collection_name: str) -> bool:
    existing_collections = list_collections()
    return collection_name in existing_collections

def create_embedding_function():
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=AZURE_OPENAI_KEY,
        api_base=AZURE_ENDPOINT,
        api_type="azure",
        api_version="2024-02-01",
        model_name=AZURE_EMBEDDING_MODEL
    )
    return openai_ef

def create_embedding(text: str) -> List[float]:
    response = azure_openai_client.embeddings.create(
        input=text,
        model=AZURE_EMBEDDING_MODEL,
    )
    return response.data[0].embedding

def create_chroma_collection(name: str, embedding_function):
    try:
        # Versuche, eine vorhandene Collection abzurufen
        return chroma_client.get_collection(name=name, embedding_function=embedding_function)
    except ValueError:
        # Wenn die Collection nicht existiert, erstelle eine neue
        return chroma_client.create_collection(name=name, embedding_function=embedding_function)

def extract_text_from_pdf(file_path: str) -> tuple:
    with fitz.open(file_path) as doc:
        total_pages = doc.page_count
        text = ""
        for page in doc:
            text += page.get_text()
    return total_pages, text

def hash_file_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()

def tokenize_and_chunk_text(text: str, max_tokens_per_chunk: int) -> tuple:
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    chunks = [tokens[i:i + max_tokens_per_chunk] for i in range(0, len(tokens), max_tokens_per_chunk)]
    text_chunks = [encoding.decode(chunk) for chunk in chunks]
    return text_chunks, len(chunks)

def clean_text(text: str) -> str:
    # Implement text cleaning logic here
    return text

def create_embedding(text: str) -> List[float]:
    response = azure_openai_client.embeddings.create(
        input=text,
        model=AZURE_EMBEDDING_MODEL,
    )
    return response.data[0].embedding

def create_description(text: str) -> str:
    response = azure_openai_client.chat.completions.create(
        model=AZURE_MODEL,
        messages=[
            {"role": "system", "content": "Du bist ein hilfreicher KI-Assistent, der anhand eines vorgegebenen Textes eine passende Beschreibung mit maximal 3 Sätzen erstellen soll."},
            {"role": "user", "content": f"Um diesen Text geht es: {text}."},
        ],
        max_tokens=4000,
        temperature=0.7
    )
    return response.choices[0].message.content


def process_pdf_and_add_to_collection(file_path: str, collection_name: str, max_tokens_per_chunk: int = 512):
    logging.info(f"Processing file: {file_path} for collection: {collection_name}")
    collection = create_chroma_collection(collection_name, create_embedding_function())

    total_pages, text = extract_text_from_pdf(file_path)
    logging.info(f"Extracted {total_pages} pages from {file_path}")

    hash_value = hash_file_content(text)
    document_description = create_description(text[:1000])

    text_chunks, chunk_count = tokenize_and_chunk_text(text, max_tokens_per_chunk)
    logging.info(f"Created {chunk_count} chunks from {file_path}")

    chunks_per_page = chunk_count / total_pages

    for i, chunk in enumerate(text_chunks):
        clean_chunk = clean_text(chunk)
        page_number = int(i / chunks_per_page) + 1
        embedding = create_embedding(clean_chunk)
        chunk_id = f"{os.path.basename(file_path)}_{i}"

        collection.add(
            embeddings=[embedding],
            documents=[clean_chunk],
            metadatas=[{
                "source": os.path.basename(file_path),
                "hash": hash_value,
                "description": document_description,
                "chunk_id": chunk_id,
                "page_number": page_number
            }],
            ids=[chunk_id]
        )


    logging.info(f"Added {chunk_count} chunks to collection {collection_name} from {file_path}")
    return {"message": f"PDF processed and added to collection {collection_name}"}