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

def initialize_embeddings():
    """
    Use HuggingFace Inference API instead of local models
    """
    hf_token = os.getenv('HUGGINGFACE_API_KEY')
    
    if not hf_token:
        # Fallback to local model (only if absolutely necessary)
        from langchain_community.embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name='sentence-transformers/all-MiniLM-L6-v2',
            model_kwargs={'device': 'cpu'}
        )
    
    # Use API (no local model download!)
    return HuggingFaceInferenceAPIEmbeddings(
        api_key=hf_token,
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

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
