"""
Answer generation using OpenAI with citation support
"""
import os
import re
import logging
from typing import List, Dict, Optional, Tuple
import json

from openai import OpenAI
from dotenv import load_dotenv
# from .validator import AnswerValidator  # TODO: Implement in Phase 3

load_dotenv('.env.local')

logger = logging.getLogger(__name__)

class AnswerGenerator:
    """Generates answers from search results using OpenAI LLM"""
    
    def __init__(self,
                 api_key: Optional[str] = None,
                 model: str = "gpt-4",
                 max_tokens: int = 500,
                 temperature: float = 0.1):
        
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self.client = OpenAI(api_key=self.api_key)
        # self.validator = AnswerValidator()  # TODO: Implement in Phase 3
        
        logger.info(f"AnswerGenerator initialized with model: {self.model}")
    
    def build_context(self, search_results: List[Dict], max_context_tokens: int = 3000) -> Tuple[str, List[Dict]]:
        """
        Build context string from search results and prepare citation info
        
        Args:
            search_results: List of search result dictionaries
            max_context_tokens: Maximum tokens to use for context
            
        Returns:
            Tuple of (context_string, citation_list)
        """
        if not search_results:
            return "", []
        
        context_parts = []
        citations = []
        current_tokens = 0
        
        for i, result in enumerate(search_results):
            # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
            text = result.get('text', '')
            estimated_tokens = len(text) // 4
            
            if current_tokens + estimated_tokens > max_context_tokens:
                break
            
            # Add to context with citation marker
            citation_id = i + 1
            context_part = f"[Source {citation_id}] {text}"
            context_parts.append(context_part)
            
            # Prepare citation info
            citation = {
                'id': citation_id,
                'doc_id': result.get('doc_id'),
                'chunk_id': result.get('chunk_id'),
                'filename': result.get('filename', 'Unknown'),
                'file_type': result.get('file_type', 'unknown'),
                'text': text,
                'score': result.get('score', result.get('combined_score', 0))
            }
            citations.append(citation)
            
            current_tokens += estimated_tokens
        
        context_string = "\n\n".join(context_parts)
        
        logger.info(f"Built context with {len(citations)} sources ({current_tokens} estimated tokens)")
        return context_string, citations
    
    def create_system_prompt(self) -> str:
        """Create the system prompt for the LLM"""
        return """You are a helpful AI assistant that answers questions based on provided document excerpts. 

Guidelines:
1. Answer questions accurately based only on the provided sources
2. Include specific citations in your answer using [Source X] format
3. If the sources don't contain enough information, say so clearly
4. Be concise but comprehensive
5. Maintain a professional, helpful tone
6. If asked about something not in the sources, politely explain the limitation

Always cite your sources when making specific claims."""
    
    def create_user_prompt(self, question: str, context: str) -> str:
        """Create the user prompt with question and context"""
        return f"""Question: {question}

Sources:
{context}

Please answer the question based on the provided sources. Include citations using [Source X] format when referencing specific information."""
    
    def generate_answer(self, question: str, search_results: List[Dict]) -> Dict:
        """
        Generate an answer to a question using search results
        
        Args:
            question: The user's question
            search_results: List of relevant document chunks
            
        Returns:
            Dictionary with answer, confidence, and citations
        """
        try:
            if not search_results:
                return {
                    'answer': "I couldn't find relevant information in the uploaded documents to answer your question.",
                    'confidence': 0.0,
                    'citations': []
                }
            
            # Build context and citations
            context, citations = self.build_context(search_results)
            
            if not context:
                return {
                    'answer': "I couldn't extract enough relevant information from the documents to answer your question.",
                    'confidence': 0.0,
                    'citations': []
                }
            
            # Create prompts
            system_prompt = self.create_system_prompt()
            user_prompt = self.create_user_prompt(question, context)
            
            # Generate answer using OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            answer_text = response.choices[0].message.content
            
            # Calculate confidence score
            confidence = self.calculate_confidence(
                question=question,
                answer=answer_text,
                search_results=search_results,
                context=context
            )
            
            # Process citations in the answer
            processed_citations = self.process_answer_citations(answer_text, citations)
            
            # Validate answer quality
            # TODO: Implement validation in Phase 3
            # validation_report = self.validator.validate_answer_against_sources(answer_text, search_results)
            # should_flag, flag_reason = self.validator.should_flag_answer(validation_report)
            # validation_summary = self.validator.get_validation_summary(validation_report)
            validation_report = {}
            should_flag = False
            flag_reason = None
            validation_summary = "Validation not implemented yet"
            
            # Adjust confidence based on validation
            adjusted_confidence = confidence  # No validation adjustment until Phase 3
            
            logger.info(f"Generated answer with confidence {adjusted_confidence:.2f} | Validation: {validation_summary}")
            
            result = {
                'answer': answer_text,
                'confidence': adjusted_confidence,
                'citations': processed_citations,
                'context_used': len(citations),
                'validation': {
                    'score': validation_report.get('overall_score', 0.0),
                    'summary': validation_summary,
                    'flagged': should_flag,
                    'flag_reason': flag_reason if should_flag else None,
                    'recommendations': validation_report.get('recommendations', [])
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return {
                'answer': "I encountered an error while processing your question. Please try again.",
                'confidence': 0.0,
                'citations': []
            }
    
    def calculate_confidence(self, 
                           question: str, 
                           answer: str, 
                           search_results: List[Dict],
                           context: str) -> float:
        """
        Calculate confidence score for the generated answer
        
        Factors considered:
        - Number of sources used
        - Quality of search results (scores)
        - Length and completeness of answer
        - Presence of citations in answer
        """
        try:
            confidence_factors = []
            
            # Factor 1: Number of sources (normalized to 0-1)
            num_sources = len(search_results)
            source_factor = min(num_sources / 3.0, 1.0)  # Max confidence at 3+ sources
            confidence_factors.append(source_factor)
            
            # Factor 2: Average search result quality
            if search_results:
                avg_score = sum(
                    result.get('score', result.get('combined_score', 0)) 
                    for result in search_results
                ) / len(search_results)
                # Normalize score (assuming max score around 1.0)
                score_factor = min(avg_score, 1.0)
                confidence_factors.append(score_factor)
            
            # Factor 3: Answer completeness (based on length)
            answer_length_factor = min(len(answer) / 200.0, 1.0)  # Max confidence at 200+ chars
            confidence_factors.append(answer_length_factor)
            
            # Factor 4: Citation presence
            citation_pattern = r'\[Source \d+\]'
            citations_found = len(re.findall(citation_pattern, answer))
            citation_factor = min(citations_found / 2.0, 1.0)  # Max confidence at 2+ citations
            confidence_factors.append(citation_factor)
            
            # Factor 5: Avoid uncertainty indicators
            uncertainty_phrases = [
                "i don't know", "i'm not sure", "unclear", "might be", 
                "possibly", "perhaps", "could be", "not enough information"
            ]
            uncertainty_penalty = 0.0
            answer_lower = answer.lower()
            for phrase in uncertainty_phrases:
                if phrase in answer_lower:
                    uncertainty_penalty += 0.2
            
            # Calculate weighted average
            base_confidence = sum(confidence_factors) / len(confidence_factors)
            final_confidence = max(0.0, base_confidence - uncertainty_penalty)
            
            return min(final_confidence, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating confidence: {e}")
            return 0.5  # Default moderate confidence
    
    def process_answer_citations(self, answer: str, available_citations: List[Dict]) -> List[Dict]:
        """
        Process citations mentioned in the answer and return relevant citation data
        
        Args:
            answer: The generated answer text
            available_citations: List of available citation dictionaries
            
        Returns:
            List of citations that were actually referenced in the answer
        """
        try:
            # Find all citation references in the answer
            citation_pattern = r'\[Source (\d+)\]'
            cited_numbers = [int(match) for match in re.findall(citation_pattern, answer)]
            
            # Get corresponding citation data
            used_citations = []
            for cite_num in set(cited_numbers):  # Remove duplicates
                # Citation numbers are 1-indexed
                if 1 <= cite_num <= len(available_citations):
                    citation = available_citations[cite_num - 1].copy()
                    citation['mentioned_in_answer'] = True
                    used_citations.append(citation)
            
            # Sort by citation ID for consistent ordering
            used_citations.sort(key=lambda x: x.get('id', 0))
            
            logger.info(f"Processed {len(used_citations)} citations from answer")
            return used_citations
            
        except Exception as e:
            logger.error(f"Error processing citations: {e}")
            return available_citations  # Return all if processing fails
    
    def generate_follow_up_questions(self, question: str, answer: str, citations: List[Dict]) -> List[str]:
        """
        Generate relevant follow-up questions based on the answer and available sources
        
        Args:
            question: Original question
            answer: Generated answer
            citations: Available citations
            
        Returns:
            List of suggested follow-up questions
        """
        try:
            # This could be enhanced with another LLM call, but for MVP, use simple heuristics
            follow_ups = []
            
            # Extract key topics from citations
            topics = set()
            for citation in citations:
                filename = citation.get('filename', '')
                if filename:
                    # Extract potential topics from filename
                    base_name = filename.split('.')[0].replace('_', ' ').replace('-', ' ')
                    topics.add(base_name)
            
            # Generate basic follow-up questions
            for topic in list(topics)[:3]:  # Limit to 3 topics
                follow_ups.append(f"What else does {topic} say about this topic?")
            
            # Add generic follow-ups based on answer content
            if "policy" in answer.lower():
                follow_ups.append("What are the exceptions to this policy?")
            
            if "process" in answer.lower() or "procedure" in answer.lower():
                follow_ups.append("What are the next steps in this process?")
            
            return follow_ups[:3]  # Return max 3 follow-ups
            
        except Exception as e:
            logger.error(f"Error generating follow-up questions: {e}")
            return []
    
    def test_connection(self) -> bool:
        """Test the OpenAI API connection"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            return len(response.choices) > 0
        except Exception as e:
            logger.error(f"OpenAI connection test failed: {e}")
            return False
