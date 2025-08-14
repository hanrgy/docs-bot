"""
Company Docs Q&A Bot - Main Flask Application
"""
import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv('.env.local')

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# Create upload directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for services (will be initialized after imports)
document_processor = None
embedding_manager = None
vector_store = None
search_engine = None
answer_generator = None

@app.route('/')
def index():
    """Main page with document upload and Q&A interface"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_documents():
    """Handle document upload and processing"""
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No files selected'}), 400
        
        processed_files = []
        for file in files:
            if file and file.filename:
                # Validate file type
                if not document_processor.validate_file(file):
                    return jsonify({'error': f'Invalid file type: {file.filename}'}), 400
                
                # Save file
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # Process document
                result = document_processor.process_document(filepath)
                processed_files.append(result)
                
                logger.info(f"Successfully processed: {filename}")
        
        return jsonify({
            'message': f'Successfully processed {len(processed_files)} documents',
            'files': processed_files
        })
        
    except Exception as e:
        logger.error(f"Error processing documents: {str(e)}")
        return jsonify({'error': 'Failed to process documents'}), 500

@app.route('/ask', methods=['POST'])
def ask_question():
    """Handle Q&A requests"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({'error': 'No question provided'}), 400
        
        # Search for relevant context
        search_results = search_engine.search(question, top_k=5)
        
        if not search_results:
            return jsonify({
                'answer': 'I could not find relevant information in the uploaded documents to answer your question.',
                'confidence': 0.0,
                'citations': []
            })
        
        # Generate answer with citations
        answer_data = answer_generator.generate_answer(question, search_results)
        
        logger.info(f"Answered question: {question[:50]}...")
        return jsonify(answer_data)
        
    except Exception as e:
        logger.error(f"Error answering question: {str(e)}")
        return jsonify({'error': 'Failed to process question'}), 500

@app.route('/documents', methods=['GET'])
def list_documents():
    """List all uploaded documents"""
    try:
        documents = document_processor.list_documents()
        return jsonify({'documents': documents})
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        return jsonify({'error': 'Failed to list documents'}), 500

@app.route('/documents/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """Delete a specific document"""
    try:
        result = document_processor.delete_document(doc_id)
        if result:
            return jsonify({'message': 'Document deleted successfully'})
        else:
            return jsonify({'error': 'Document not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        return jsonify({'error': 'Failed to delete document'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'services': {
            'document_processor': document_processor is not None,
            'embedding_manager': embedding_manager is not None,
            'vector_store': vector_store is not None,
            'search_engine': search_engine is not None,
            'answer_generator': answer_generator is not None
        }
    })

if __name__ == '__main__':
    # Import and initialize services
    try:
        from utils.file_processor import DocumentProcessor
        from utils.embeddings import EmbeddingManager
        from utils.vector_store import QdrantStore
        from utils.hybrid_search import HybridSearchEngine
        from utils.answer_generator import AnswerGenerator
        
        # Initialize services
        document_processor = DocumentProcessor(app.config['UPLOAD_FOLDER'])
        embedding_manager = EmbeddingManager()
        vector_store = QdrantStore()
        search_engine = HybridSearchEngine(vector_store, document_processor)
        answer_generator = AnswerGenerator()
        
        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        # Continue without services for development
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5000)
