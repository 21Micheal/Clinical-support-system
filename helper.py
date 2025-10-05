from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_community.embeddings import HuggingFaceEmbeddings



# Extract data from the pdf file
def load_pdf_file(data):
    loader = DirectoryLoader(data,
                             glob="*.pdf",
                             loader_cls=PyPDFLoader)
    documents= loader.load()
    
    return documents

def split_documents(documents, chunk_size: int = 500, chunk_overlap: int = 20):
    """
    Split the loaded documents into smaller text chunks.
    """
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    text_chunks = splitter.split_documents(documents)
    return text_chunks

def initialize_embeddings(model_name: str = 'sentence-transformers/all-MiniLM-L6-v2'):
    """
    Initialize Hugging Face embeddings with caching.
    """
    import os
    
    # Set cache directory to persist across requests
    cache_dir = os.getenv('HF_HOME', '/tmp/huggingface_cache')
    os.makedirs(cache_dir, exist_ok=True)
    
    embeddings = HuggingFaceEmbeddings(
        model_name=model_name,
        cache_folder=cache_dir,
        model_kwargs={'device': 'cpu'}  # Ensure CPU usage
    )
    return embeddings

# Split the data into text chunks
def text_split(extracted_data):
    text_splitter=RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap= 20)
    text_chunks= text_splitter.split_documents(extracted_data)
    return text_chunks
    # Function for Qa pipeline
from transformers import pipeline
def initialize_qa_pipeline(model_name: str = "deepset/roberta-base-squad2"):
    """
    Initialize the QA model with a more detailed Hugging Face model.
    """
    qa_pipe = pipeline("question-answering", model="distilbert-base-cased-distilled-squad")

    return qa_pipe

# Function to download embeddings from huggingface
def download_hugging_face_embeddings():
    embeddings = HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')
    return embeddings
