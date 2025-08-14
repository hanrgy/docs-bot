"""
OpenAI embeddings and text chunking utilities
"""
import os
import re
import logging
from typing import List, Dict, Tuple, Optional
import tiktoken
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv('.env.local')

logger = logging.getLogger(__name__)

class EmbeddingManager:
    """Manages text chunking and OpenAI embeddings generation"""
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 model: str = "text-embedding-3-small",
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200):
        
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.api_key)
        
        # Initialize tokenizer for accurate token counting
        try:
            self.encoding = tiktoken.encoding_for_model("gpt-4")
        except KeyError:
            # Fallback to a default encoding if model-specific encoding is not available
            self.encoding = tiktoken.get_encoding("cl100k_base")
        
        logger.info(f"EmbeddingManager initialized with model: {self.model}")
    
    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text string"""
        return len(self.encoding.encode(text))
    
    def chunk_text(self, text: str, metadata: Optional[Dict] = None) -> List[Dict]:
        """
        Split text into overlapping chunks with metadata
        
        Args:
            text: The text to chunk
            metadata: Optional metadata to attach to each chunk
            
        Returns:
            List of chunk dictionaries with text, metadata, and position info
        """
        if not text or not text.strip():
            return []
        
        # Clean and normalize text
        text = self.clean_text(text)
        
        # Split into sentences for better semantic boundaries
        sentences = self.split_into_sentences(text)
        
        chunks = []
        current_chunk = ""
        current_token_count = 0
        sentence_start_idx = 0
        
        for i, sentence in enumerate(sentences):
            sentence_tokens = self.count_tokens(sentence)
            
            # If adding this sentence would exceed chunk size, finalize current chunk
            if current_token_count + sentence_tokens > self.chunk_size and current_chunk:
                chunk_dict = self.create_chunk_dict(
                    text=current_chunk.strip(),
                    chunk_id=len(chunks),
                    start_sentence=sentence_start_idx,
                    end_sentence=i - 1,
                    token_count=current_token_count,
                    metadata=metadata
                )
                chunks.append(chunk_dict)
                
                # Start new chunk with overlap
                overlap_text = self.get_overlap_text(current_chunk, self.chunk_overlap)
                current_chunk = overlap_text + " " + sentence if overlap_text else sentence
                current_token_count = self.count_tokens(current_chunk)
                sentence_start_idx = max(0, i - self.calculate_overlap_sentences(overlap_text, sentences[:i]))
            else:
                # Add sentence to current chunk
                current_chunk += " " + sentence if current_chunk else sentence
                current_token_count += sentence_tokens
        
        # Add final chunk if it has content
        if current_chunk.strip():
            chunk_dict = self.create_chunk_dict(
                text=current_chunk.strip(),
                chunk_id=len(chunks),
                start_sentence=sentence_start_idx,
                end_sentence=len(sentences) - 1,
                token_count=current_token_count,
                metadata=metadata
            )
            chunks.append(chunk_dict)
        
        logger.info(f"Split text into {len(chunks)} chunks (avg {sum(c['token_count'] for c in chunks) // len(chunks) if chunks else 0} tokens per chunk)")
        return chunks
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page markers (common in PDFs)
        text = re.sub(r'\[Page \d+\]\s*', '', text)
        
        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        return text.strip()
    
    def split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences using simple heuristics"""
        # Simple sentence splitting - could be improved with nltk
        sentence_endings = r'[.!?]+(?:\s+|$)'
        sentences = re.split(sentence_endings, text)
        
        # Clean up sentences
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def get_overlap_text(self, text: str, max_tokens: int) -> str:
        """Get the last part of text that fits within token limit for overlap"""
        if max_tokens <= 0:
            return ""
        
        words = text.split()
        overlap_text = ""
        
        # Build overlap from the end, word by word
        for i in range(len(words) - 1, -1, -1):
            test_text = " ".join(words[i:])
            if self.count_tokens(test_text) <= max_tokens:
                overlap_text = test_text
            else:
                break
        
        return overlap_text
    
    def calculate_overlap_sentences(self, overlap_text: str, previous_sentences: List[str]) -> int:
        """Calculate how many sentences the overlap covers"""
        if not overlap_text or not previous_sentences:
            return 0
        
        overlap_words = set(overlap_text.lower().split())
        
        for i in range(len(previous_sentences) - 1, -1, -1):
            sentence_words = set(previous_sentences[i].lower().split())
            if overlap_words.intersection(sentence_words):
                return len(previous_sentences) - i
        
        return 0
    
    def create_chunk_dict(self, text: str, chunk_id: int, start_sentence: int, 
                         end_sentence: int, token_count: int, metadata: Optional[Dict] = None) -> Dict:
        """Create a standardized chunk dictionary"""
        chunk_dict = {
            'chunk_id': chunk_id,
            'text': text,
            'token_count': token_count,
            'start_sentence': start_sentence,
            'end_sentence': end_sentence,
            'char_count': len(text)
        }
        
        if metadata:
            chunk_dict.update(metadata)
        
        return chunk_dict
    
    async def generate_embeddings_async(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts asynchronously (future enhancement)"""
        # For now, use the synchronous method
        return self.generate_embeddings(texts)
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        try:
            # OpenAI embedding API supports batch processing
            response = self.client.embeddings.create(
                model=self.model,
                input=texts
            )
            
            embeddings = [embedding.embedding for embedding in response.data]
            
            logger.info(f"Generated {len(embeddings)} embeddings using {self.model}")
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        return self.generate_embeddings([text])[0]
    
    def process_document_for_embeddings(self, doc_id: str, text_content: str, 
                                      filename: str = None, file_type: str = None) -> List[Dict]:
        """
        Process a document into chunks with embeddings
        
        Args:
            doc_id: Unique document identifier
            text_content: Full text content of the document
            filename: Original filename
            file_type: File type (pdf, md, txt)
            
        Returns:
            List of chunks with embeddings and metadata
        """
        # Prepare metadata
        metadata = {
            'doc_id': doc_id,
            'filename': filename or 'unknown',
            'file_type': file_type or 'unknown'
        }
        
        # Chunk the text
        chunks = self.chunk_text(text_content, metadata)
        
        if not chunks:
            logger.warning(f"No chunks generated for document {doc_id}")
            return []
        
        # Extract texts for embedding
        chunk_texts = [chunk['text'] for chunk in chunks]
        
        # Generate embeddings
        try:
            embeddings = self.generate_embeddings(chunk_texts)
            
            # Attach embeddings to chunks
            for i, chunk in enumerate(chunks):
                chunk['embedding'] = embeddings[i]
                chunk['embedding_model'] = self.model
            
            logger.info(f"Processed document {doc_id} into {len(chunks)} chunks with embeddings")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings for document {doc_id}: {e}")
            # Return chunks without embeddings (they can still be used for keyword search)
            for chunk in chunks:
                chunk['embedding'] = None
                chunk['embedding_model'] = None
            return chunks
    
    def test_connection(self) -> bool:
        """Test the OpenAI API connection"""
        try:
            # Try a simple embedding request
            response = self.client.embeddings.create(
                model=self.model,
                input=["test connection"]
            )
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"OpenAI API connection test failed: {e}")
            return False
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings for the current model"""
        # Known dimensions for OpenAI models
        model_dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536
        }
        
        return model_dimensions.get(self.model, 1536)  # Default to 1536
