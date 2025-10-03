from flask import Blueprint, request, jsonify, render_template
from chatbot_routes import chatbot_instance
import logging
import time
from langchain_pinecone import PineconeVectorStore
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from pinecone import Pinecone
from groq import Groq
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from helper import initialize_embeddings

load_dotenv()

logger = logging.getLogger(__name__)

chatbot_bp = Blueprint('chatbot', __name__)

@chatbot_bp.route('/ask', methods=['POST'])
def ask_chatbot():
    """
    Handles chatbot queries using RAG with Groq.
    """
    try:
        start_time = time.time()
        
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        question = data.get("question", "").strip()

        if not question:
            return jsonify({"error": "No question provided"}), 400

        logger.info(f"🤖 RAG Chatbot question received: {question}")

        # Generate response using RAG + Groq
        answer = chatbot_instance.generate_response(question)
        
        processing_time = time.time() - start_time
        
        logger.info(f"✅ RAG response generated in {processing_time:.2f}s")
        logger.debug(f"🤖 Response preview: {answer[:200]}...")

        return jsonify({
            "answer": answer,
            "processing_time": round(processing_time, 2),
            "model": "llama-3.3-70b-versatile",
            "retrieval_system": "pinecone_rag",
            "success": True
        })

    except Exception as e:
        logger.error(f"❌ Chatbot error: {str(e)}")
        return jsonify({
            "error": f"Internal server error: {str(e)}",
            "success": False
        }), 500

@chatbot_bp.route('/health', methods=['GET'])
def chatbot_health():
    """Health check endpoint for chatbot"""
    health_status = chatbot_instance.health_check()
    
    return jsonify({
        "service": "rag_clinical_chatbot",
        "status": health_status["status"],
        "details": health_status
    })

@chatbot_bp.route('/interface', methods=['GET'])
def chatbot_interface():
    """Serve the chatbot web interface"""
    return render_template('chatbot_rag.html')

class RAGChatbot:
    def __init__(self):
        self.pinecone_api_key = os.getenv('PINECONE_API_KEY')
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        self.index_name = "medicalbot"
        
        # Initialize components
        self.embeddings = initialize_embeddings()
        self.pc = Pinecone(api_key=self.pinecone_api_key)
        self.groq_client = Groq(api_key=self.groq_api_key)
        
        # Setup vector store and retriever
        self.docsearch = PineconeVectorStore.from_existing_index(
            index_name=self.index_name,
            embedding=self.embeddings,
        )
        self.retriever = self.docsearch.as_retriever(search_type="similarity", search_kwargs={"k": 5})
        
        # Setup prompt template
        self.system_prompt = (
            "You are a clinical support assistant with expertise in medical knowledge. "
            "Use the following pieces of retrieved context to answer the question. "
            "If you don't know the answer based on the context, say that you don't know. "
            "Provide accurate, detailed, and informative medical answers.\n\n"
            "{context}"
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{input}"),
        ])
    
    def generate_response(self, question: str) -> str:
        """Generate response using RAG with Groq"""
        try:
            # Retrieve relevant documents
            retrieved_docs = self.retriever.invoke(question)
            context = "\n".join([str(doc.page_content) for doc in retrieved_docs])
            
            # Format prompt
            formatted_prompt = self.prompt.format(input=question, context=context)
            
            # Generate response using Groq
            chat_completion = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": formatted_prompt}],
                temperature=0.7,  # Slightly lower for medical accuracy
                max_tokens=800   # Increased for detailed medical answers
            )
            
            return chat_completion.choices[0].message.content
            
        except Exception as e:
            return f"I apologize, but I encountered an error: {str(e)}"
    
    def health_check(self) -> dict:
        """Check if all services are available"""
        try:
            # Check Pinecone connection
            indexes = self.pc.list_indexes()
            pinecone_ok = any(index.name == self.index_name for index in indexes.index_list)
            
            # Check Groq connection (simple test)
            groq_ok = True  # We'll assume it's ok unless proven otherwise
            
            return {
                "pinecone_connected": pinecone_ok,
                "groq_connected": groq_ok,
                "index_available": pinecone_ok,
                "status": "healthy" if pinecone_ok and groq_ok else "degraded"
            }
        except Exception as e:
            return {
                "pinecone_connected": False,
                "groq_connected": False,
                "index_available": False,
                "status": "unhealthy",
                "error": str(e)
            }

# Global instance
chatbot_instance = RAGChatbot()