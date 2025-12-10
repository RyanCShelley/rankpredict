"""
Semantic similarity service using sentence-transformers (from notebook)
"""
import numpy as np
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from numpy.linalg import norm
from sentence_transformers import SentenceTransformer
from app.config import SENTENCE_TRANSFORMERS_MODEL


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors (from notebook)"""
    denom = (norm(a) * norm(b)) + 1e-8
    return float(np.dot(a, b) / denom)


class SemanticService:
    """Service for computing semantic similarity (from notebook)"""
    
    def __init__(self, model_name: str = None):
        model_name = model_name or SENTENCE_TRANSFORMERS_MODEL
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
    
    def get_query_embedding(self, query: str, query_variants: Optional[List[str]] = None) -> np.ndarray:
        """
        Represent intent as the average embedding of query and variants (from notebook)
        
        Args:
            query: Original query string
            query_variants: Optional list of query variant strings
            
        Returns:
            Average embedding vector representing query intent
        """
        texts = [query]
        if query_variants:
            texts.extend([q for q in query_variants if isinstance(q, str) and q.strip()])
        
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return np.mean(embeddings, axis=0)
    
    def extract_main_text_for_semantics(self, html: str) -> str:
        """
        Focus on meaningful part of page for semantic scoring (from notebook):
        - <title>
        - first <h1>
        - first 3–5 <p> elements
        This avoids nav/footer noise.
        """
        if not html:
            return ""
        
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            title = soup.title.get_text(" ", strip=True) if soup.title else ""
            
            h1 = soup.find("h1")
            h1_text = h1.get_text(" ", strip=True) if h1 else ""
            
            p_texts = []
            for p in soup.find_all("p"):
                t = p.get_text(" ", strip=True)
                if not t:
                    continue
                p_texts.append(t)
                if len(p_texts) >= 5:
                    break
            
            main_text = " ".join([title, h1_text] + p_texts).strip()
            return main_text[:4000]
        except Exception as e:
            print(f"Error extracting main text: {e}")
            return ""
    
    def compute_semantic_scores_for_serp(
        self,
        serp_results: List[Dict],
        query: str,
        query_variants: Optional[List[str]] = None,
        html_column: str = "raw_html"
    ) -> List[float]:
        """
        Compute semantic scores for SERP results (from notebook)
        
        For each URL in serp_results:
        - use pre-fetched HTML if available
        - extract main text (title + h1 + first paragraphs)
        - embed and compute cosine similarity with query intent
        """
        query_emb = self.get_query_embedding(query, query_variants)
        scores = []
        
        for result in serp_results:
            html = result.get(html_column, "")
            if not html:
                # Fallback: try to fetch if URL is available
                url = result.get("url", "")
                if not url:
                    scores.append(0.0)
                    continue
                try:
                    import requests
                    resp = requests.get(url, timeout=10, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    })
                    html = resp.text
                except Exception:
                    scores.append(0.0)
                    continue
            
            main_text = self.extract_main_text_for_semantics(html)
            if not main_text.strip():
                scores.append(0.0)
                continue
            
            try:
                doc_emb = self.model.encode(main_text, normalize_embeddings=True)
                score = cosine_sim(query_emb, doc_emb)
                scores.append(max(0.0, min(1.0, score)))  # Clamp to [0, 1]
            except Exception as e:
                print(f"Error encoding document for semantic score: {e}")
                scores.append(0.0)
        
        return scores
    
    def compute_semantic_score(
        self,
        query: str,
        html: str,
        query_variants: Optional[List[str]] = None
    ) -> float:
        """
        Compute semantic similarity score between a query and a document's HTML.
        
        Args:
            query: Search query
            html: Document HTML content
            query_variants: Optional query variants for better intent representation
            
        Returns:
            Semantic similarity score (0-1)
        """
        if not html or not html.strip():
            return 0.0
        
        try:
            # Get query embedding
            query_emb = self.get_query_embedding(query, query_variants)
            
            # Extract main text from HTML
            main_text = self.extract_main_text_for_semantics(html)
            if not main_text.strip():
                return 0.0
            
            # Get document embedding
            doc_emb = self.model.encode(main_text, normalize_embeddings=True)
            
            # Compute cosine similarity
            score = cosine_sim(query_emb, doc_emb)
            return max(0.0, min(1.0, score))  # Clamp to [0, 1]
        except Exception as e:
            print(f"Error computing semantic score: {e}")
            return 0.0


def get_semantic_service() -> SemanticService:
    """Get semantic service instance (singleton)"""
    if not hasattr(get_semantic_service, "_instance"):
        get_semantic_service._instance = SemanticService()
    return get_semantic_service._instance

