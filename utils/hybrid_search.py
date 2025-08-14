"""
Hybrid search engine combining semantic and keyword search
"""
import logging
import re
from typing import List, Dict, Optional, Tuple
from collections import defaultdict, Counter
import math

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

class BM25:
    """BM25 scoring algorithm for keyword-based search"""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents = []
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        self.avgdl = 0
        
    def fit(self, documents: List[str]):
        """Fit BM25 with a corpus of documents"""
        self.documents = documents
        self.doc_len = [len(doc.split()) for doc in documents]
        self.avgdl = sum(self.doc_len) / len(self.doc_len) if self.doc_len else 0
        
        # Calculate document frequencies
        df = defaultdict(int)
        for doc in documents:
            words = set(doc.lower().split())
            for word in words:
                df[word] += 1
        
        # Calculate IDF
        N = len(documents)
        for word, freq in df.items():
            self.idf[word] = math.log((N - freq + 0.5) / (freq + 0.5) + 1.0)
    
    def score(self, query: str, doc_idx: int) -> float:
        """Calculate BM25 score for a query against a specific document"""
        if doc_idx >= len(self.documents):
            return 0.0
        
        doc = self.documents[doc_idx]
        doc_words = doc.lower().split()
        query_words = query.lower().split()
        
        score = 0.0
        doc_word_count = Counter(doc_words)
        
        for word in query_words:
            if word in doc_word_count:
                freq = doc_word_count[word]
                idf = self.idf.get(word, 0)
                
                # BM25 formula
                score += idf * (freq * (self.k1 + 1)) / (
                    freq + self.k1 * (1 - self.b + self.b * self.doc_len[doc_idx] / self.avgdl)
                )
        
        return score
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Search documents and return top-k results with scores"""
        scores = []
        for i in range(len(self.documents)):
            score = self.score(query, i)
            scores.append((i, score))
        
        # Sort by score (descending)
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

class HybridSearchEngine:
    """Combines semantic search (vector similarity) with keyword search (BM25)"""
    
    def __init__(self, 
                 vector_store,
                 document_processor,
                 embedding_manager,
                 alpha: float = 0.5):
        """
        Initialize hybrid search engine
        
        Args:
            vector_store: QdrantStore instance
            document_processor: DocumentProcessor instance  
            embedding_manager: EmbeddingManager instance
            alpha: Weight for combining scores (0.0 = only keyword, 1.0 = only semantic)
        """
        self.vector_store = vector_store
        self.document_processor = document_processor
        self.embedding_manager = embedding_manager
        self.alpha = alpha
        
        # BM25 index
        self.bm25 = BM25()
        self.chunk_documents = []  # Text chunks for BM25
        self.chunk_metadata = []   # Metadata for each chunk
        
        # Build initial index
        self._build_keyword_index()
        
        logger.info(f"HybridSearchEngine initialized with alpha={alpha}")
    
    def _build_keyword_index(self):
        """Build BM25 keyword index from existing documents"""
        try:
            # Get all document content
            all_content = self.document_processor.get_all_text_content()
            
            if not all_content:
                logger.info("No documents found for keyword indexing")
                return
            
            # Process each document into chunks for indexing
            all_chunks = []
            for doc_id, text_content in all_content:
                doc_info = self.document_processor.get_document_info(doc_id)
                if not doc_info:
                    continue
                
                # Generate chunks (similar to embedding process)
                chunks = self.embedding_manager.chunk_text(
                    text_content, 
                    metadata={
                        'doc_id': doc_id,
                        'filename': doc_info['filename'],
                        'file_type': doc_info['file_type']
                    }
                )
                
                for chunk in chunks:
                    all_chunks.append(chunk)
            
            if all_chunks:
                # Extract text for BM25
                self.chunk_documents = [chunk['text'] for chunk in all_chunks]
                self.chunk_metadata = all_chunks
                
                # Fit BM25
                self.bm25.fit(self.chunk_documents)
                
                logger.info(f"Built keyword index with {len(self.chunk_documents)} chunks")
            
        except Exception as e:
            logger.error(f"Error building keyword index: {e}")
    
    def add_document_to_index(self, doc_id: str):
        """Add a new document to the keyword index"""
        try:
            doc_info = self.document_processor.get_document_info(doc_id)
            if not doc_info:
                logger.warning(f"Document {doc_id} not found in processor")
                return
            
            text_content = self.document_processor.get_document_content(doc_id)
            if not text_content:
                logger.warning(f"No text content for document {doc_id}")
                return
            
            # Generate chunks
            chunks = self.embedding_manager.chunk_text(
                text_content,
                metadata={
                    'doc_id': doc_id,
                    'filename': doc_info['filename'],
                    'file_type': doc_info['file_type']
                }
            )
            
            # Add to existing chunks
            for chunk in chunks:
                self.chunk_documents.append(chunk['text'])
                self.chunk_metadata.append(chunk)
            
            # Rebuild BM25 index
            if self.chunk_documents:
                self.bm25.fit(self.chunk_documents)
                logger.info(f"Added document {doc_id} to keyword index")
            
        except Exception as e:
            logger.error(f"Error adding document {doc_id} to index: {e}")
    
    def remove_document_from_index(self, doc_id: str):
        """Remove a document from the keyword index"""
        try:
            # Find and remove chunks for this document
            new_documents = []
            new_metadata = []
            
            for i, metadata in enumerate(self.chunk_metadata):
                if metadata.get('doc_id') != doc_id:
                    new_documents.append(self.chunk_documents[i])
                    new_metadata.append(metadata)
            
            self.chunk_documents = new_documents
            self.chunk_metadata = new_metadata
            
            # Rebuild BM25 index
            if self.chunk_documents:
                self.bm25.fit(self.chunk_documents)
            
            logger.info(f"Removed document {doc_id} from keyword index")
            
        except Exception as e:
            logger.error(f"Error removing document {doc_id} from index: {e}")
    
    def semantic_search(self, query: str, top_k: int = 10) -> List[Dict]:
        """Perform semantic search using vector similarity"""
        try:
            # Generate query embedding
            query_vector = self.embedding_manager.generate_embedding(query)
            
            # Search in Qdrant
            results = self.vector_store.search_similar(
                query_vector=query_vector,
                top_k=top_k,
                min_score=0.1  # Minimum similarity threshold
            )
            
            logger.info(f"Semantic search found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    def keyword_search(self, query: str, top_k: int = 10) -> List[Dict]:
        """Perform keyword search using BM25"""
        try:
            if not self.chunk_documents:
                logger.warning("No documents in keyword index")
                return []
            
            # Perform BM25 search
            bm25_results = self.bm25.search(query, top_k)
            
            # Convert to standard format
            results = []
            for doc_idx, score in bm25_results:
                if doc_idx < len(self.chunk_metadata):
                    metadata = self.chunk_metadata[doc_idx]
                    result = {
                        'score': score,
                        'doc_id': metadata.get('doc_id'),
                        'chunk_id': metadata.get('chunk_id'),
                        'filename': metadata.get('filename'),
                        'file_type': metadata.get('file_type'),
                        'text': metadata.get('text'),
                        'token_count': metadata.get('token_count'),
                        'char_count': metadata.get('char_count')
                    }
                    results.append(result)
            
            logger.info(f"Keyword search found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error in keyword search: {e}")
            return []
    
    def reciprocal_rank_fusion(self, 
                              semantic_results: List[Dict], 
                              keyword_results: List[Dict],
                              k: int = 60) -> List[Dict]:
        """
        Combine search results using Reciprocal Rank Fusion (RRF)
        
        Args:
            semantic_results: Results from semantic search
            keyword_results: Results from keyword search  
            k: RRF parameter (typically 60)
            
        Returns:
            Fused and re-ranked results
        """
        # Create a map of chunk identifiers to combined scores
        chunk_scores = defaultdict(float)
        chunk_data = {}
        
        # Process semantic results
        for rank, result in enumerate(semantic_results, 1):
            chunk_key = f"{result['doc_id']}_{result['chunk_id']}"
            rrf_score = 1.0 / (k + rank)
            chunk_scores[chunk_key] += self.alpha * rrf_score
            chunk_data[chunk_key] = result
        
        # Process keyword results
        for rank, result in enumerate(keyword_results, 1):
            chunk_key = f"{result['doc_id']}_{result['chunk_id']}"
            rrf_score = 1.0 / (k + rank)
            chunk_scores[chunk_key] += (1.0 - self.alpha) * rrf_score
            
            # Use keyword result data if not already present
            if chunk_key not in chunk_data:
                chunk_data[chunk_key] = result
        
        # Sort by combined score
        sorted_chunks = sorted(
            chunk_scores.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        # Build final results
        fused_results = []
        for chunk_key, combined_score in sorted_chunks:
            if chunk_key in chunk_data:
                result = chunk_data[chunk_key].copy()
                result['combined_score'] = combined_score
                fused_results.append(result)
        
        logger.info(f"Fused {len(fused_results)} unique results")
        return fused_results
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Perform hybrid search combining semantic and keyword search
        
        Args:
            query: Search query
            top_k: Number of top results to return
            
        Returns:
            List of search results with relevance scores
        """
        try:
            # Perform both types of search
            semantic_results = self.semantic_search(query, top_k * 2)
            keyword_results = self.keyword_search(query, top_k * 2)
            
            if not semantic_results and not keyword_results:
                logger.warning("No results from either search method")
                return []
            
            # Combine using RRF
            fused_results = self.reciprocal_rank_fusion(
                semantic_results, 
                keyword_results
            )
            
            # Return top-k results
            final_results = fused_results[:top_k]
            
            logger.info(f"Hybrid search returned {len(final_results)} results for query: '{query[:50]}...'")
            return final_results
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return []
    
    def get_search_stats(self) -> Dict:
        """Get statistics about the search index"""
        return {
            'total_chunks': len(self.chunk_documents),
            'total_documents': len(set(meta.get('doc_id') for meta in self.chunk_metadata)),
            'alpha': self.alpha,
            'vector_store_connected': self.vector_store.test_connection() if hasattr(self.vector_store, 'test_connection') else False
        }
