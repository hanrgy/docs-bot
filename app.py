"""
Company Docs Q&A Bot - Main Flask Application
Phase 3: Production-Ready with Advanced Error Handling & Validation
"""
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
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
error_handler = None
feedback_manager = None

# Error Handlers
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(error):
    return jsonify({
        'error': 'File too large. Please use files smaller than 10MB.',
        'help': 'Try compressing your file or splitting large documents into smaller sections.'
    }), 413

@app.errorhandler(404)
def handle_not_found(error):
    if request.path.startswith('/api') or request.headers.get('Content-Type') == 'application/json':
        return jsonify({
            'error': 'Endpoint not found',
            'available_endpoints': ['/', '/upload', '/ask', '/documents', '/health']
        }), 404
    return render_template('index.html'), 404

@app.errorhandler(500)
def handle_internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'error': 'Internal server error. Please try again or contact support if the problem persists.',
        'help': 'Check that all services are properly configured and running.'
    }), 500

@app.errorhandler(Exception)
def handle_general_exception(error):
    if error_handler:
        error_message, status_code = error_handler.handle_general_error(error, 'request_processing')
        error_handler.log_error(error, {'path': request.path, 'method': request.method})
        return jsonify({'error': error_message}), status_code
    else:
        logger.error(f"Unhandled exception: {error}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/')
def index():
    """Main page with document upload and Q&A interface"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_documents():
    """Handle document upload and processing with full pipeline"""
    try:
        logger.info("📤 Upload request started")
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No files selected'}), 400
        
        logger.info(f"📁 Processing {len(files)} files")
        processed_files = []
        for i, file in enumerate(files):
            if file and file.filename:
                logger.info(f"🔍 File {i+1}: {file.filename} ({file.content_length if hasattr(file, 'content_length') else 'unknown'} bytes)")
                
                # Validate file type
                logger.info(f"✅ Validating file: {file.filename}")
                if not document_processor.validate_file(file):
                    return jsonify({'error': f'Invalid file type: {file.filename}'}), 400
                
                # Save file
                logger.info(f"💾 Saving file: {file.filename}")
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # Process document
                logger.info(f"📝 Processing document: {filename}")
                result = document_processor.process_document(filepath)
                doc_id = result['id']
                logger.info(f"✅ Document processed with ID: {doc_id}")
                
                # Generate embeddings and store in vector database
                logger.info(f"📖 Getting document content for: {doc_id}")
                text_content = document_processor.get_document_content(doc_id)
                if text_content:
                    logger.info(f"🧠 Starting embedding generation for {len(text_content)} characters...")
                    # Process document for embeddings
                    chunks_with_embeddings = embedding_manager.process_document_for_embeddings(
                        doc_id=doc_id,
                        text_content=text_content,
                        filename=result['filename'],
                        file_type=result['file_type']
                    )
                    logger.info(f"✅ Embedding generation complete: {len(chunks_with_embeddings) if chunks_with_embeddings else 0} chunks")
                    
                    # Store in Qdrant
                    if chunks_with_embeddings:
                        logger.info(f"🗄️ Storing {len(chunks_with_embeddings)} chunks in Qdrant...")
                        vector_store.store_document_chunks(chunks_with_embeddings)
                        logger.info(f"✅ Stored {len(chunks_with_embeddings)} chunks in vector database")
                        
                        # Update search engine index
                        logger.info(f"🔍 Updating search index for: {doc_id}")
                        search_engine.add_document_to_index(doc_id)
                        logger.info(f"✅ Search index updated")
                        
                        result['chunks_stored'] = len(chunks_with_embeddings)
                        result['vector_storage'] = True
                    else:
                        result['chunks_stored'] = 0
                        result['vector_storage'] = False
                        logger.warning(f"No chunks generated for {filename}")
                
                processed_files.append(result)
                logger.info(f"🎉 Successfully processed: {filename}")
        
        logger.info(f"✅ All files processed successfully! Returning response...")
        return jsonify({
            'message': f'Successfully processed {len(processed_files)} documents',
            'files': processed_files
        })
        
    except Exception as e:
        logger.error(f"💥 Error processing documents: {str(e)}")
        import traceback
        logger.error(f"💥 Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to process documents'}), 500

@app.route('/ask', methods=['POST'])
def ask_question():
    """Handle Q&A requests with enhanced hybrid search and citations"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({'error': 'No question provided'}), 400
        
        # Search for relevant context using hybrid search
        search_results = search_engine.search(question, top_k=5)
        
        if not search_results:
            return jsonify({
                'answer': 'I could not find relevant information in the uploaded documents to answer your question.',
                'confidence': 0.0,
                'citations': [],
                'context_used': 0
            })
        
        # Generate answer with citations using enhanced answer generator
        answer_data = answer_generator.generate_answer(question, search_results)
        
        logger.info(f"Answered question: {question[:50]}... (confidence: {answer_data.get('confidence', 0):.2f})")
        return jsonify(answer_data)
        
    except Exception as e:
        logger.error(f"Error answering question: {str(e)}")
        return jsonify({'error': 'Failed to process question'}), 500

@app.route('/documents', methods=['GET'])
def list_documents():
    """List all uploaded documents with enhanced metadata"""
    try:
        documents = document_processor.list_documents()
        return jsonify({'documents': documents})
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        return jsonify({'error': 'Failed to list documents'}), 500

@app.route('/documents/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """Delete a specific document from all systems"""
    try:
        # Delete from vector store first
        vector_store.delete_document(doc_id)
        
        # Remove from search engine index
        search_engine.remove_document_from_index(doc_id)
        
        # Delete from document processor
        result = document_processor.delete_document(doc_id)
        
        if result:
            logger.info(f"Document {doc_id} deleted from all systems")
            return jsonify({'message': 'Document deleted successfully'})
        else:
            return jsonify({'error': 'Document not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        return jsonify({'error': 'Failed to delete document'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Comprehensive health check endpoint"""
    try:
        health_status = {
            'status': 'healthy',
            'version': 'v2.0.0-phase2-complete',
            'timestamp': datetime.now().isoformat(),
            'features': [
                'Document Processing (PDF, Markdown, Text)',
                'OpenAI Embeddings & Chat Completion',
                'Qdrant Vector Database',
                'Hybrid Search (BM25 + Semantic)',
                'Citation-based Answers',
                'Confidence Scoring',
                'Query Caching',
                'Follow-up Questions'
            ],
            'services': {},
            'stats': {}
        }
        
        # Check service availability
        services = {
            'document_processor': document_processor,
            'embedding_manager': embedding_manager,
            'vector_store': vector_store,
            'search_engine': search_engine,
            'answer_generator': answer_generator
        }
        
        for service_name, service in services.items():
            if service is not None:
                # Test service connection if available
                if hasattr(service, 'test_connection'):
                    try:
                        health_status['services'][service_name] = {
                            'available': True,
                            'connected': service.test_connection()
                        }
                    except:
                        health_status['services'][service_name] = {
                            'available': True,
                            'connected': False
                        }
                else:
                    health_status['services'][service_name] = {
                        'available': True,
                        'connected': True
                    }
            else:
                health_status['services'][service_name] = {
                    'available': False,
                    'connected': False
                }
        
        # Gather system stats
        if document_processor:
            docs = document_processor.list_documents()
            health_status['stats']['documents'] = len(docs)
        
        if vector_store:
            try:
                vector_stats = vector_store.get_stats()
                health_status['stats']['vector_store'] = vector_stats
            except:
                health_status['stats']['vector_store'] = {'error': 'Unable to fetch stats'}
        
        if search_engine:
            try:
                search_stats = search_engine.get_search_stats()
                health_status['stats']['search_engine'] = search_stats
            except:
                health_status['stats']['search_engine'] = {'error': 'Unable to fetch stats'}
        
        # Determine overall health
        all_services_available = all(s['available'] for s in health_status['services'].values())
        all_services_connected = all(s['connected'] for s in health_status['services'].values())
        
        if all_services_available and all_services_connected:
            health_status['status'] = 'healthy'
        elif all_services_available:
            health_status['status'] = 'degraded'
        else:
            health_status['status'] = 'unhealthy'
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return jsonify({
            'status': 'error',
            'version': 'v2.0.0-phase2-complete',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# Initialize services globally
def initialize_services():
    """Initialize all application services"""
    global document_processor, embedding_manager, vector_store, search_engine, answer_generator
    
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
        search_engine = HybridSearchEngine(vector_store, document_processor, embedding_manager)
        answer_generator = AnswerGenerator()
        
        logger.info("All Phase 2 services initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        return False

if __name__ == '__main__':
    # Initialize services
    if initialize_services():
        logger.info("🚀 Docs Q&A Bot Phase 2 ready to start!")
        logger.info("Features: Enhanced search, citations, caching, validation")
    else:
        logger.error("Application starting with limited functionality")
    
    # Run the app
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)