from flask import Blueprint, request, jsonify, render_template
from chatbot_routes import chatbot_instance
import logging
import time

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