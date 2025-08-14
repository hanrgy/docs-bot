"""
Qdrant vector store integration for document embeddings
"""
import os
import uuid
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct, Filter, 
    FieldCondition, MatchValue, SearchRequest,
    CreateCollection, UpdateCollection
)
from dotenv import load_dotenv

load_dotenv('.env.local')

logger = logging.getLogger(__name__)

class QdrantStore:
    """Manages vector storage and retrieval using Qdrant Cloud"""
    
    def __init__(self, 
                 url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 collection_name: str = "documents",
                 vector_size: int = 1536):
        
        self.url = url or os.getenv('QDRANT_URL')
        self.api_key = api_key or os.getenv('QDRANT_API_KEY')
        self.collection_name = collection_name
        self.vector_size = vector_size
        
        if not self.url or not self.api_key:
            raise ValueError("Qdrant URL and API key are required. Set QDRANT_URL and QDRANT_API_KEY environment variables.")
        
        # Initialize Qdrant client
        try:
            self.client = QdrantClient(
                url=self.url,
                api_key=self.api_key,
                timeout=30
            )
            logger.info(f"Qdrant client initialized: {self.url}")
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {e}")
            raise
        
        # Ensure collection exists
        self._ensure_collection_exists()
    
    def _ensure_collection_exists(self):
        """Create collection if it doesn't exist"""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.collection_name not in collection_names:
                logger.info(f"Creating collection: {self.collection_name}")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Collection '{self.collection_name}' created successfully")
            else:
                logger.info(f"Collection '{self.collection_name}' already exists")
                
        except Exception as e:
            logger.error(f"Error ensuring collection exists: {e}")
            raise
    
    def store_document_chunks(self, chunks: List[Dict]) -> bool:
        """
        Store document chunks with embeddings in Qdrant
        
        Args:
            chunks: List of chunk dictionaries with embeddings and metadata
            
        Returns:
            True if successful, False otherwise
        """
        if not chunks:
            logger.warning("No chunks provided for storage")
            return False
        
        try:
            points = []
            
            for chunk in chunks:
                if not chunk.get('embedding'):
                    logger.warning(f"Chunk {chunk.get('chunk_id', 'unknown')} has no embedding, skipping")
                    continue
                
                # Generate unique point ID
                point_id = str(uuid.uuid4())
                
                # Prepare metadata payload
                payload = {
                    'doc_id': chunk.get('doc_id'),
                    'chunk_id': chunk.get('chunk_id'),
                    'filename': chunk.get('filename'),
                    'file_type': chunk.get('file_type'),
                    'text': chunk.get('text'),
                    'token_count': chunk.get('token_count'),
                    'char_count': chunk.get('char_count'),
                    'start_sentence': chunk.get('start_sentence'),
                    'end_sentence': chunk.get('end_sentence'),
                    'embedding_model': chunk.get('embedding_model'),
                    'created_at': datetime.now().isoformat()
                }
                
                # Create point
                point = PointStruct(
                    id=point_id,
                    vector=chunk['embedding'],
                    payload=payload
                )
                points.append(point)
            
            if not points:
                logger.warning("No valid points to store")
                return False
            
            # Upsert points to Qdrant
            operation_info = self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            logger.info(f"Stored {len(points)} chunks from document {chunks[0].get('doc_id')} in Qdrant")
            return True
            
        except Exception as e:
            logger.error(f"Error storing chunks in Qdrant: {e}")
            return False
    
    def search_similar(self, 
                      query_vector: List[float], 
                      top_k: int = 5,
                      doc_id: Optional[str] = None,
                      file_type: Optional[str] = None,
                      min_score: float = 0.0) -> List[Dict]:
        """
        Search for similar vectors in Qdrant
        
        Args:
            query_vector: Query embedding vector
            top_k: Number of results to return
            doc_id: Optional filter by document ID
            file_type: Optional filter by file type
            min_score: Minimum similarity score threshold
            
        Returns:
            List of search results with metadata and scores
        """
        try:
            # Build filter conditions
            filter_conditions = []
            
            if doc_id:
                filter_conditions.append(
                    FieldCondition(key="doc_id", match=MatchValue(value=doc_id))
                )
            
            if file_type:
                filter_conditions.append(
                    FieldCondition(key="file_type", match=MatchValue(value=file_type))
                )
            
            # Create filter if conditions exist
            query_filter = Filter(must=filter_conditions) if filter_conditions else None
            
            # Perform search
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
                score_threshold=min_score,
                query_filter=query_filter,
                with_payload=True,
                with_vectors=False  # Don't return vectors to save bandwidth
            )
            
            # Format results
            results = []
            for result in search_results:
                result_dict = {
                    'id': result.id,
                    'score': result.score,
                    'doc_id': result.payload.get('doc_id'),
                    'chunk_id': result.payload.get('chunk_id'),
                    'filename': result.payload.get('filename'),
                    'file_type': result.payload.get('file_type'),
                    'text': result.payload.get('text'),
                    'token_count': result.payload.get('token_count'),
                    'char_count': result.payload.get('char_count'),
                    'created_at': result.payload.get('created_at')
                }
                results.append(result_dict)
            
            logger.info(f"Found {len(results)} similar chunks (top_k={top_k})")
            return results
            
        except Exception as e:
            logger.error(f"Error searching in Qdrant: {e}")
            return []
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Delete all chunks for a specific document
        
        Args:
            doc_id: Document ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create filter for document ID
            delete_filter = Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            )
            
            # Delete points matching the filter
            operation_info = self.client.delete(
                collection_name=self.collection_name,
                points_selector=delete_filter
            )
            
            logger.info(f"Deleted chunks for document {doc_id} from Qdrant")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting document {doc_id} from Qdrant: {e}")
            return False
    
    def get_collection_info(self) -> Dict:
        """Get information about the collection"""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                'name': info.config.params.vectors.size,
                'vector_size': info.config.params.vectors.size,
                'distance': info.config.params.vectors.distance,
                'points_count': info.points_count,
                'indexed_vectors_count': info.indexed_vectors_count,
                'status': info.status
            }
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            return {}
    
    def list_documents(self) -> List[Dict]:
        """List all unique documents in the collection"""
        try:
            # This is a simplified approach - in production, you might want to maintain a separate index
            # For now, we'll do a scroll through all points and extract unique documents
            
            scroll_result = self.client.scroll(
                collection_name=self.collection_name,
                limit=1000,  # Adjust based on your needs
                with_payload=True,
                with_vectors=False
            )
            
            documents = {}
            for point in scroll_result[0]:
                doc_id = point.payload.get('doc_id')
                if doc_id and doc_id not in documents:
                    documents[doc_id] = {
                        'doc_id': doc_id,
                        'filename': point.payload.get('filename'),
                        'file_type': point.payload.get('file_type'),
                        'chunk_count': 0,
                        'first_created': point.payload.get('created_at')
                    }
                
                if doc_id:
                    documents[doc_id]['chunk_count'] += 1
            
            return list(documents.values())
            
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []
    
    def test_connection(self) -> bool:
        """Test the Qdrant connection"""
        try:
            collections = self.client.get_collections()
            logger.info("Qdrant connection test successful")
            return True
        except Exception as e:
            logger.error(f"Qdrant connection test failed: {e}")
            return False
    
    def create_test_point(self) -> bool:
        """Create a test point to verify everything is working"""
        try:
            test_vector = [0.1] * self.vector_size
            test_id = str(uuid.uuid4())
            test_point = PointStruct(
                id=test_id,
                vector=test_vector,
                payload={
                    'doc_id': 'test-doc',
                    'chunk_id': 0,
                    'filename': 'test.txt',
                    'file_type': 'txt',
                    'text': 'This is a test chunk',
                    'token_count': 5,
                    'char_count': 19,
                    'created_at': datetime.now().isoformat()
                }
            )
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[test_point]
            )
            
            # Clean up test point
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[test_id]
            )
            
            logger.info("Test point creation and deletion successful")
            return True
            
        except Exception as e:
            logger.error(f"Test point creation failed: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """Get collection statistics"""
        try:
            info = self.get_collection_info()
            documents = self.list_documents()
            
            return {
                'collection_name': self.collection_name,
                'total_points': info.get('points_count', 0),
                'indexed_vectors': info.get('indexed_vectors_count', 0),
                'unique_documents': len(documents),
                'vector_size': info.get('vector_size', self.vector_size),
                'distance_metric': info.get('distance', 'cosine'),
                'status': info.get('status', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
