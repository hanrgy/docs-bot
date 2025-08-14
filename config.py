"""
Configuration management for the Docs Q&A Bot
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

class Config:
    """Base configuration class"""
    
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB max file size
    
    # File upload settings
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt'}
    MAX_FILES_PER_UPLOAD = 10
    
    # OpenAI settings
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4')
    OPENAI_EMBEDDING_MODEL = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
    OPENAI_MAX_TOKENS = int(os.getenv('OPENAI_MAX_TOKENS', '4000'))
    
    # Qdrant settings
    QDRANT_URL = os.getenv('QDRANT_URL')
    QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
    QDRANT_COLLECTION_NAME = os.getenv('QDRANT_COLLECTION_NAME', 'documents')
    QDRANT_VECTOR_SIZE = int(os.getenv('QDRANT_VECTOR_SIZE', '1536'))  # text-embedding-3-small size
    
    # Text processing settings
    CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '1000'))
    CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', '200'))
    
    # Search settings
    SEARCH_TOP_K = int(os.getenv('SEARCH_TOP_K', '5'))
    HYBRID_SEARCH_ALPHA = float(os.getenv('HYBRID_SEARCH_ALPHA', '0.5'))  # 0.5 = equal weight semantic/keyword
    
    # Answer generation settings
    ANSWER_MAX_TOKENS = int(os.getenv('ANSWER_MAX_TOKENS', '500'))
    CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', '0.3'))
    
    @classmethod
    def validate_config(cls):
        """Validate that required configuration is present"""
        required_vars = []
        
        if not cls.OPENAI_API_KEY:
            required_vars.append('OPENAI_API_KEY')
        
        if not cls.QDRANT_URL:
            required_vars.append('QDRANT_URL')
        
        if not cls.QDRANT_API_KEY:
            required_vars.append('QDRANT_API_KEY')
        
        if required_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(required_vars)}")
        
        return True

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    UPLOAD_FOLDER = 'test_uploads'

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
