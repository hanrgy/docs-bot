"""
Document processing utilities for PDF and Markdown files
"""
import os
import uuid
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging

import PyPDF2
import markdown
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Handles document upload, processing, and management"""
    
    def __init__(self, upload_folder: str = 'uploads'):
        self.upload_folder = upload_folder
        self.allowed_extensions = {'pdf', 'md', 'txt'}
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.documents_db = {}  # In-memory storage for MVP
        
        # Ensure upload folder exists
        os.makedirs(upload_folder, exist_ok=True)
        
    def validate_file(self, file) -> bool:
        """Validate uploaded file type and size"""
        if not file or not file.filename:
            return False
            
        # Check file extension
        filename = file.filename.lower()
        if not any(filename.endswith(f'.{ext}') for ext in self.allowed_extensions):
            logger.warning(f"Invalid file extension: {filename}")
            return False
            
        # Check file size (if available)
        file.seek(0, 2)  # Seek to end
        size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if size > self.max_file_size:
            logger.warning(f"File too large: {size} bytes")
            return False
            
        return True
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text content from PDF file"""
        try:
            text_content = []
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text.strip():
                            text_content.append(f"[Page {page_num + 1}]\n{page_text}")
                    except Exception as e:
                        logger.warning(f"Error extracting page {page_num + 1}: {e}")
                        continue
            
            if not text_content:
                raise ValueError("No text content extracted from PDF")
                
            return "\n\n".join(text_content)
            
        except Exception as e:
            logger.error(f"Error processing PDF {file_path}: {e}")
            raise
    
    def extract_text_from_markdown(self, file_path: str) -> str:
        """Extract text content from Markdown file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                
            # Convert markdown to plain text while preserving structure
            md = markdown.Markdown(extensions=['meta', 'tables', 'fenced_code'])
            html_content = md.convert(content)
            
            # For now, return the raw markdown (we could use BeautifulSoup to convert HTML to text)
            return content
            
        except Exception as e:
            logger.error(f"Error processing Markdown {file_path}: {e}")
            raise
    
    def extract_text_from_txt(self, file_path: str) -> str:
        """Extract text content from plain text file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            logger.error(f"Error processing text file {file_path}: {e}")
            raise
    
    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of file for deduplication"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def process_document(self, file_path: str) -> Dict:
        """Process a document and extract its content"""
        try:
            # Get file information
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            file_hash = self.calculate_file_hash(file_path)
            
            # Check for duplicates
            for doc_id, doc_info in self.documents_db.items():
                if doc_info['hash'] == file_hash:
                    logger.info(f"Duplicate file detected: {filename}")
                    return doc_info
            
            # Determine file type and extract text
            file_ext = filename.lower().split('.')[-1]
            
            if file_ext == 'pdf':
                text_content = self.extract_text_from_pdf(file_path)
            elif file_ext == 'md':
                text_content = self.extract_text_from_markdown(file_path)
            elif file_ext == 'txt':
                text_content = self.extract_text_from_txt(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
            
            # Generate document metadata
            doc_id = str(uuid.uuid4())
            doc_info = {
                'id': doc_id,
                'filename': filename,
                'original_name': filename,
                'file_path': file_path,
                'file_type': file_ext,
                'file_size': file_size,
                'hash': file_hash,
                'text_content': text_content,
                'word_count': len(text_content.split()),
                'character_count': len(text_content),
                'upload_time': datetime.now().isoformat(),
                'processed': True
            }
            
            # Store document info
            self.documents_db[doc_id] = doc_info
            
            logger.info(f"Successfully processed document: {filename} ({doc_info['word_count']} words)")
            
            # Return summary (without full text content for API response)
            return {
                'id': doc_id,
                'filename': filename,
                'file_type': file_ext,
                'file_size': file_size,
                'word_count': doc_info['word_count'],
                'character_count': doc_info['character_count'],
                'upload_time': doc_info['upload_time'],
                'processed': True
            }
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            raise
    
    def get_document_content(self, doc_id: str) -> Optional[str]:
        """Get the full text content of a document"""
        if doc_id in self.documents_db:
            return self.documents_db[doc_id]['text_content']
        return None
    
    def get_document_info(self, doc_id: str) -> Optional[Dict]:
        """Get document metadata"""
        return self.documents_db.get(doc_id)
    
    def list_documents(self) -> List[Dict]:
        """List all processed documents"""
        documents = []
        for doc_id, doc_info in self.documents_db.items():
            documents.append({
                'id': doc_info['id'],
                'filename': doc_info['filename'],
                'file_type': doc_info['file_type'],
                'file_size': doc_info['file_size'],
                'word_count': doc_info['word_count'],
                'upload_time': doc_info['upload_time'],
                'processed': doc_info['processed']
            })
        
        # Sort by upload time (newest first)
        documents.sort(key=lambda x: x['upload_time'], reverse=True)
        return documents
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document and its associated files"""
        if doc_id not in self.documents_db:
            return False
        
        try:
            doc_info = self.documents_db[doc_id]
            
            # Delete physical file
            if os.path.exists(doc_info['file_path']):
                os.remove(doc_info['file_path'])
                logger.info(f"Deleted file: {doc_info['file_path']}")
            
            # Remove from database
            del self.documents_db[doc_id]
            
            logger.info(f"Deleted document: {doc_info['filename']}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {e}")
            return False
    
    def get_all_text_content(self) -> List[Tuple[str, str]]:
        """Get all document text content for embedding generation"""
        content_list = []
        for doc_id, doc_info in self.documents_db.items():
            if doc_info['processed'] and doc_info['text_content']:
                content_list.append((doc_id, doc_info['text_content']))
        return content_list
    
    def cleanup_old_files(self, days: int = 7):
        """Clean up files older than specified days (for maintenance)"""
        cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        docs_to_delete = []
        for doc_id, doc_info in self.documents_db.items():
            upload_time = datetime.fromisoformat(doc_info['upload_time']).timestamp()
            if upload_time < cutoff_time:
                docs_to_delete.append(doc_id)
        
        for doc_id in docs_to_delete:
            self.delete_document(doc_id)
            
        logger.info(f"Cleaned up {len(docs_to_delete)} old documents")
        return len(docs_to_delete)
