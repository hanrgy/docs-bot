#!/usr/bin/env python3
"""
Test the upload process step by step to identify where it hangs
"""
import os
import tempfile
from dotenv import load_dotenv
import logging

# Load environment
load_dotenv('.env.local')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_upload_process():
    """Test the complete upload process step by step"""
    print("🧪 Testing complete upload process...")
    
    try:
        # Initialize services (same as app.py)
        print("1. Initializing services...")
        from utils.file_processor import DocumentProcessor
        from utils.embeddings import EmbeddingManager
        from utils.vector_store import QdrantStore
        from utils.hybrid_search import HybridSearchEngine
        
        document_processor = DocumentProcessor('uploads')
        embedding_manager = EmbeddingManager()
        vector_store = QdrantStore()
        search_engine = HybridSearchEngine(vector_store, document_processor, embedding_manager)
        print("✓ All services initialized")
        
        # Create a test file
        print("2. Creating test file...")
        test_content = "This is a test document for upload testing. " * 50
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(test_content)
            test_file_path = f.name
        
        print(f"✓ Test file created: {test_file_path}")
        
        # Step 3: Process document (similar to app.py line 102)
        print("3. Processing document...")
        result = document_processor.process_document(test_file_path)
        doc_id = result['id']
        print(f"✓ Document processed: {doc_id}")
        
        # Step 4: Get document content (app.py line 106)
        print("4. Getting document content...")
        text_content = document_processor.get_document_content(doc_id)
        if text_content:
            print(f"✓ Content retrieved: {len(text_content)} characters")
        else:
            print("✗ No content retrieved")
            return False
        
        # Step 5: Process for embeddings (app.py line 109-114) - THIS IS WHERE IT LIKELY HANGS
        print("5. Processing document for embeddings...")
        print("   This step may take a while as it calls OpenAI API...")
        
        chunks_with_embeddings = embedding_manager.process_document_for_embeddings(
            doc_id=doc_id,
            text_content=text_content,
            filename=result['filename'],
            file_type=result['file_type']
        )
        
        if chunks_with_embeddings:
            print(f"✓ Embeddings generated: {len(chunks_with_embeddings)} chunks")
        else:
            print("✗ No embeddings generated")
            return False
        
        # Step 6: Store in Qdrant (app.py line 117-118)
        print("6. Storing in vector database...")
        storage_result = vector_store.store_document_chunks(chunks_with_embeddings)
        if storage_result:
            print("✓ Chunks stored in Qdrant")
        else:
            print("✗ Failed to store chunks")
            return False
        
        # Step 7: Update search index (app.py line 122)
        print("7. Updating search index...")
        search_engine.add_document_to_index(doc_id)
        print("✓ Search index updated")
        
        print("\n🎉 Complete upload process successful!")
        
        # Cleanup
        os.unlink(test_file_path)
        return True
        
    except Exception as e:
        print(f"\n💥 Upload process failed at step: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_upload_process()
