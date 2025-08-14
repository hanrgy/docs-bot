"""
Comprehensive error handling and user experience utilities
"""
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from functools import wraps
import time

logger = logging.getLogger(__name__)

class ErrorHandler:
    """Centralized error handling with user-friendly messages and logging"""
    
    def __init__(self):
        self.error_counts = {}
        self.last_errors = {}
        self.rate_limit_window = 60  # seconds
        self.max_errors_per_window = 10
        
        logger.info("ErrorHandler initialized")
    
    def handle_openai_error(self, error: Exception) -> Tuple[str, int]:
        """Handle OpenAI API specific errors"""
        error_str = str(error).lower()
        
        if 'rate limit' in error_str or 'quota' in error_str:
            return (
                "Our AI service is currently experiencing high demand. Please try again in a few moments.",
                429
            )
        elif 'invalid api key' in error_str or 'authentication' in error_str:
            logger.error(f"OpenAI authentication error: {error}")
            return (
                "There's a configuration issue with our AI service. Please contact support.",
                500
            )
        elif 'timeout' in error_str or 'connection' in error_str:
            return (
                "Our AI service is temporarily unavailable. Please try again in a moment.",
                503
            )
        elif 'context length' in error_str or 'token' in error_str:
            return (
                "Your question or documents are too large to process. Please try with shorter content.",
                400
            )
        elif 'content filter' in error_str or 'safety' in error_str:
            return (
                "Your request was filtered for safety reasons. Please rephrase your question.",
                400
            )
        else:
            logger.error(f"Unexpected OpenAI error: {error}")
            return (
                "Our AI service encountered an unexpected error. Please try again.",
                500
            )
    
    def handle_qdrant_error(self, error: Exception) -> Tuple[str, int]:
        """Handle Qdrant vector database specific errors"""
        error_str = str(error).lower()
        
        if 'connection' in error_str or 'timeout' in error_str:
            return (
                "Our document search service is temporarily unavailable. Please try again.",
                503
            )
        elif 'not found' in error_str or 'collection' in error_str:
            return (
                "Document index not found. Please upload documents first.",
                404
            )
        elif 'unauthorized' in error_str or 'authentication' in error_str:
            logger.error(f"Qdrant authentication error: {error}")
            return (
                "There's a configuration issue with our search service. Please contact support.",
                500
            )
        elif 'invalid' in error_str or 'malformed' in error_str:
            return (
                "Invalid search request. Please try rephrasing your question.",
                400
            )
        else:
            logger.error(f"Unexpected Qdrant error: {error}")
            return (
                "Our search service encountered an error. Please try again.",
                500
            )
    
    def handle_file_processing_error(self, error: Exception, filename: str = None) -> Tuple[str, int]:
        """Handle file processing specific errors"""
        error_str = str(error).lower()
        file_ref = f" for file '{filename}'" if filename else ""
        
        if 'permission' in error_str or 'access' in error_str:
            return (
                f"Cannot access the uploaded file{file_ref}. Please try uploading again.",
                403
            )
        elif 'corrupted' in error_str or 'invalid' in error_str or 'damaged' in error_str:
            return (
                f"The uploaded file{file_ref} appears to be corrupted or invalid. Please check the file and try again.",
                400
            )
        elif 'size' in error_str or 'too large' in error_str:
            return (
                f"The file{file_ref} is too large. Please use files smaller than 10MB.",
                413
            )
        elif 'format' in error_str or 'type' in error_str:
            return (
                f"Unsupported file format{file_ref}. Please use PDF, Markdown, or text files.",
                415
            )
        elif 'empty' in error_str or 'no content' in error_str:
            return (
                f"The file{file_ref} appears to be empty or contains no readable text.",
                400
            )
        else:
            logger.error(f"Unexpected file processing error{file_ref}: {error}")
            return (
                f"Failed to process the uploaded file{file_ref}. Please try again with a different file.",
                500
            )
    
    def handle_general_error(self, error: Exception, context: str = None) -> Tuple[str, int]:
        """Handle general application errors"""
        context_str = f" during {context}" if context else ""
        
        if isinstance(error, (ConnectionError, TimeoutError)):
            return (
                f"Connection error{context_str}. Please check your internet connection and try again.",
                503
            )
        elif isinstance(error, ValueError):
            return (
                f"Invalid input provided{context_str}. Please check your request and try again.",
                400
            )
        elif isinstance(error, FileNotFoundError):
            return (
                f"Required file not found{context_str}. The system may need to be restarted.",
                404
            )
        elif isinstance(error, MemoryError):
            return (
                f"Not enough memory to process request{context_str}. Please try with smaller files.",
                507
            )
        else:
            logger.error(f"Unexpected error{context_str}: {error}")
            return (
                f"An unexpected error occurred{context_str}. Please try again.",
                500
            )
    
    def log_error(self, error: Exception, context: Dict[str, Any] = None, user_id: str = None):
        """Centralized error logging with context"""
        try:
            error_info = {
                'timestamp': datetime.now().isoformat(),
                'error_type': type(error).__name__,
                'error_message': str(error),
                'context': context or {},
                'user_id': user_id,
                'traceback': traceback.format_exc()
            }
            
            # Track error frequency
            error_key = f"{type(error).__name__}:{str(error)[:100]}"
            current_time = time.time()
            
            if error_key not in self.error_counts:
                self.error_counts[error_key] = []
            
            # Clean old entries
            self.error_counts[error_key] = [
                timestamp for timestamp in self.error_counts[error_key]
                if current_time - timestamp < self.rate_limit_window
            ]
            
            self.error_counts[error_key].append(current_time)
            self.last_errors[error_key] = current_time
            
            # Log with appropriate level based on frequency
            error_count = len(self.error_counts[error_key])
            if error_count > self.max_errors_per_window:
                logger.critical(f"High frequency error detected: {error_info}")
            elif error_count > 5:
                logger.error(f"Recurring error: {error_info}")
            else:
                logger.warning(f"Application error: {error_info}")
                
        except Exception as logging_error:
            # Fallback logging if our error logging fails
            logger.error(f"Error logging failed: {logging_error}")
            logger.error(f"Original error: {error}")
    
    def is_rate_limited(self, error_type: str) -> bool:
        """Check if an error type is currently rate limited"""
        try:
            current_time = time.time()
            
            for error_key in self.error_counts:
                if error_type in error_key:
                    recent_errors = [
                        timestamp for timestamp in self.error_counts[error_key]
                        if current_time - timestamp < self.rate_limit_window
                    ]
                    if len(recent_errors) > self.max_errors_per_window:
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return False
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics for monitoring"""
        try:
            current_time = time.time()
            stats = {
                'total_error_types': len(self.error_counts),
                'recent_errors': {},
                'rate_limited_errors': []
            }
            
            for error_key, timestamps in self.error_counts.items():
                recent_count = len([
                    t for t in timestamps 
                    if current_time - t < self.rate_limit_window
                ])
                
                if recent_count > 0:
                    stats['recent_errors'][error_key] = recent_count
                    
                    if recent_count > self.max_errors_per_window:
                        stats['rate_limited_errors'].append(error_key)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error generating error stats: {e}")
            return {'error': 'Unable to generate stats'}

def error_handler(error_type: str = 'general'):
    """Decorator for automatic error handling"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = ErrorHandler()
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log the error with context
                context = {
                    'function': func.__name__,
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys())
                }
                handler.log_error(e, context)
                
                # Handle based on error type
                if error_type == 'openai':
                    message, status_code = handler.handle_openai_error(e)
                elif error_type == 'qdrant':
                    message, status_code = handler.handle_qdrant_error(e)
                elif error_type == 'file_processing':
                    filename = kwargs.get('filename') or (args[1] if len(args) > 1 else None)
                    message, status_code = handler.handle_file_processing_error(e, filename)
                else:
                    message, status_code = handler.handle_general_error(e, func.__name__)
                
                # Return error in appropriate format
                if hasattr(func, '__name__') and 'api' in func.__name__.lower():
                    from flask import jsonify
                    return jsonify({'error': message}), status_code
                else:
                    raise Exception(message)
                    
        return wrapper
    return decorator

class UserFeedbackManager:
    """Manages user feedback and help systems"""
    
    def __init__(self):
        self.help_topics = {
            'upload': {
                'title': 'Document Upload Help',
                'content': 'You can upload PDF, Markdown (.md), and text (.txt) files up to 10MB each. Drag and drop files or click to browse.',
                'tips': [
                    'Ensure your PDFs contain searchable text (not just images)',
                    'Markdown files should use standard formatting',
                    'Text files should be UTF-8 encoded'
                ]
            },
            'search': {
                'title': 'Search & Questions Help',
                'content': 'Ask natural language questions about your uploaded documents. The system will search and provide answers with source citations.',
                'tips': [
                    'Be specific in your questions for better results',
                    'Use keywords from your documents',
                    'Try rephrasing if you don\'t get good results'
                ]
            },
            'citations': {
                'title': 'Understanding Citations',
                'content': 'Citations show which documents and sections were used to answer your question. Click on citations to see the source text.',
                'tips': [
                    'Higher relevance scores indicate better matches',
                    'Multiple citations provide more comprehensive answers',
                    'Check citations to verify answer accuracy'
                ]
            }
        }
    
    def get_contextual_help(self, error_message: str) -> Optional[Dict[str, Any]]:
        """Get contextual help based on error message"""
        error_lower = error_message.lower()
        
        if 'upload' in error_lower or 'file' in error_lower:
            return self.help_topics['upload']
        elif 'search' in error_lower or 'question' in error_lower:
            return self.help_topics['search']
        elif 'citation' in error_lower or 'source' in error_lower:
            return self.help_topics['citations']
        
        return None
    
    def generate_success_message(self, action: str, details: Dict[str, Any] = None) -> str:
        """Generate encouraging success messages"""
        details = details or {}
        
        if action == 'upload':
            count = details.get('file_count', 1)
            return f"🎉 Successfully uploaded and processed {count} document{'s' if count != 1 else ''}! You can now ask questions about your content."
        
        elif action == 'answer':
            confidence = details.get('confidence', 0)
            citation_count = details.get('citation_count', 0)
            if confidence > 0.8:
                return f"✅ High-confidence answer provided with {citation_count} supporting source{'s' if citation_count != 1 else ''}!"
            elif confidence > 0.5:
                return f"📝 Answer provided with {citation_count} source{'s' if citation_count != 1 else ''}. Consider the confidence level when using this information."
            else:
                return f"⚠️ Low-confidence answer with {citation_count} source{'s' if citation_count != 1 else ''}. You may want to rephrase your question or add more relevant documents."
        
        elif action == 'delete':
            return "🗑️ Document successfully deleted from all systems."
        
        return "✅ Action completed successfully!"
