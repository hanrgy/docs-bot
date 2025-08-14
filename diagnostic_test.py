#!/usr/bin/env python3
"""
Diagnostic test script to identify PDF upload issues
"""
import os
import tempfile
from io import BytesIO
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_environment_variables():
    """Test if required environment variables are set"""
    print("=== Environment Variables Test ===")
    
    required_vars = [
        'OPENAI_API_KEY',
        'QDRANT_URL', 
        'QDRANT_API_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✓ {var}: {'*' * 10}...{value[-4:] if len(value) > 4 else value}")
        else:
            print(f"✗ {var}: Not set")
            missing_vars.append(var)
    
    return len(missing_vars) == 0, missing_vars

def test_file_processing():
    """Test PDF processing functionality"""
    print("\n=== File Processing Test ===")
    
    try:
        from utils.file_processor import DocumentProcessor
        
        # Create a temporary test PDF content (simple text)
        test_pdf_content = b"""%%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Hello World) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000010 00000 n 
0000000079 00000 n 
0000000173 00000 n 
0000000301 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
398
%%EOF"""
        
        # Test with temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            processor = DocumentProcessor(temp_dir)
            
            # Test file validation with a mock file object
            class MockFile:
                def __init__(self, filename, content):
                    self.filename = filename
                    self.content = BytesIO(content)
                    
                def seek(self, pos, whence=0):
                    return self.content.seek(pos, whence)
                
                def tell(self):
                    return self.content.tell()
            
            # Test PDF validation
            mock_pdf = MockFile("test.pdf", test_pdf_content)
            validation_result = processor.validate_file(mock_pdf)
            print(f"✓ PDF validation: {'Passed' if validation_result else 'Failed'}")
            
            # Test with a simple text file
            test_text = "This is a test document content."
            text_path = os.path.join(temp_dir, "test.txt")
            with open(text_path, 'w') as f:
                f.write(test_text)
            
            result = processor.process_document(text_path)
            print(f"✓ Text file processing: {result['filename']} - {result['word_count']} words")
            
        return True
        
    except Exception as e:
        print(f"✗ File processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_embeddings():
    """Test embeddings functionality (if API key available)"""
    print("\n=== Embeddings Test ===")
    
    if not os.getenv('OPENAI_API_KEY'):
        print("⚠️ Skipping embeddings test - OPENAI_API_KEY not set")
        return False
    
    try:
        from utils.embeddings import EmbeddingManager
        
        # Initialize embedding manager
        embedding_manager = EmbeddingManager()
        
        # Test connection
        connection_ok = embedding_manager.test_connection()
        print(f"{'✓' if connection_ok else '✗'} OpenAI API connection: {'OK' if connection_ok else 'Failed'}")
        
        if connection_ok:
            # Test text chunking
            test_text = "This is a test document. " * 100  # Longer text
            chunks = embedding_manager.chunk_text(test_text)
            print(f"✓ Text chunking: Generated {len(chunks)} chunks")
            
            # Test embedding generation (small test)
            if chunks:
                embeddings = embedding_manager.generate_embeddings([chunks[0]['text']])
                print(f"✓ Embedding generation: Vector dimension {len(embeddings[0])}")
        
        return connection_ok
        
    except Exception as e:
        print(f"✗ Embeddings test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_vector_store():
    """Test vector store functionality (if credentials available)"""
    print("\n=== Vector Store Test ===")
    
    if not (os.getenv('QDRANT_URL') and os.getenv('QDRANT_API_KEY')):
        print("⚠️ Skipping vector store test - QDRANT credentials not set")
        return False
    
    try:
        from utils.vector_store import QdrantStore
        
        # Initialize vector store
        vector_store = QdrantStore()
        
        # Test connection
        connection_ok = vector_store.test_connection()
        print(f"{'✓' if connection_ok else '✗'} Qdrant connection: {'OK' if connection_ok else 'Failed'}")
        
        if connection_ok:
            # Test collection info
            info = vector_store.get_collection_info()
            print(f"✓ Collection info: {info.get('points_count', 0)} points")
        
        return connection_ok
        
    except Exception as e:
        print(f"✗ Vector store test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all diagnostic tests"""
    print("🔍 Running Doc Chatbot Diagnostic Tests\n")
    
    # Test environment
    env_ok, missing_vars = test_environment_variables()
    
    # Test file processing
    file_ok = test_file_processing()
    
    # Test embeddings (if API key available)
    embeddings_ok = test_embeddings()
    
    # Test vector store (if credentials available)
    vector_ok = test_vector_store()
    
    # Summary
    print("\n=== Diagnostic Summary ===")
    print(f"Environment Variables: {'✓' if env_ok else '✗'}")
    if not env_ok:
        print(f"  Missing: {', '.join(missing_vars)}")
    print(f"File Processing: {'✓' if file_ok else '✗'}")
    print(f"OpenAI Embeddings: {'✓' if embeddings_ok else '⚠️' if not os.getenv('OPENAI_API_KEY') else '✗'}")
    print(f"Qdrant Vector Store: {'✓' if vector_ok else '⚠️' if not (os.getenv('QDRANT_URL') and os.getenv('QDRANT_API_KEY')) else '✗'}")
    
    # Recommendations
    print("\n=== Recommendations ===")
    if not env_ok:
        print("1. Create .env.local file with required API keys:")
        print("   OPENAI_API_KEY=your_openai_api_key")
        print("   QDRANT_URL=your_qdrant_cloud_url")
        print("   QDRANT_API_KEY=your_qdrant_api_key")
    
    if not file_ok:
        print("2. Fix file processing issues before testing uploads")
    
    if env_ok and file_ok:
        print("✅ Basic functionality should work - try uploading a simple text file first")
    
    return env_ok and file_ok

if __name__ == "__main__":
    main()
