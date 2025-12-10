"""
Intent Analysis Service - LLM-powered intent extraction
"""
import os
import requests
from typing import Dict, List, Optional
from app.config import OPENAI_API_KEY, HUGGINGFACE_API_KEY


class IntentService:
    """Service for analyzing search intent using LLM"""
    
    def __init__(self):
        self.openai_api_key = OPENAI_API_KEY
        self.huggingface_api_key = HUGGINGFACE_API_KEY
    
    def analyze_intent(
        self,
        keyword: str,
        serp_results: List[Dict]
    ) -> Dict:
        """
        Analyze search intent and recommend content format
        
        Args:
            keyword: Search keyword
            serp_results: SERP results (titles, snippets) for context
            
        Returns:
            Dictionary with:
            - intent_type: informational/commercial/transactional/navigational
            - content_format: article/how-to/product/FAQ/etc.
            - query_variants: List of alternative phrasings for better semantic matching
        """
        # Extract context from SERP
        titles = [r.get("title", "") for r in serp_results[:10]]
        snippets = [r.get("snippet", "") for r in serp_results[:10]]
        serp_context = "\n".join([f"Title: {t}\nSnippet: {s}" for t, s in zip(titles, snippets)])
        
        # Build prompt for intent analysis
        prompt = f"""Analyze the search intent for this keyword and provide recommendations.

Keyword: "{keyword}"

SERP Context (what's currently ranking):
{serp_context[:2000]}

Based on the keyword and what's ranking in the SERP, determine:

1. Intent Type (choose one):
   - informational: User wants to learn or understand something
   - commercial: User is researching products/services before buying
   - transactional: User wants to make a purchase or take action
   - navigational: User wants to find a specific website

2. Content Format Recommendation (choose the most appropriate):
   - article: General informational article
   - how-to: Step-by-step guide or tutorial
   - product: Product review, comparison, or buying guide
   - FAQ: Frequently asked questions format
   - list: Listicle or roundup format
   - comparison: Comparison table or detailed comparison
   - definition: Definition or explanation format
   - news: News article or update format

3. Query Variants: Provide 2-3 alternative phrasings of the keyword that capture the same intent (for better semantic matching).

Return your response as JSON:
{{
  "intent_type": "informational|commercial|transactional|navigational",
  "content_format": "article|how-to|product|FAQ|list|comparison|definition|news",
  "query_variants": ["variant1", "variant2", "variant3"],
  "reasoning": "Brief explanation of why this intent and format"
}}"""

        # Try OpenAI first, then Hugging Face, then fallback
        if self.openai_api_key:
            try:
                return self._analyze_with_openai(prompt)
            except Exception as e:
                print(f"Error calling OpenAI for intent analysis: {e}")
        
        if self.huggingface_api_key:
            try:
                return self._analyze_with_huggingface(prompt)
            except Exception as e:
                print(f"Error calling Hugging Face for intent analysis: {e}")
        
        # Fallback to rule-based analysis
        return self._fallback_intent_analysis(keyword, serp_results)
    
    def _analyze_with_openai(self, prompt: str) -> Dict:
        """Analyze intent using OpenAI API"""
        import json
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are an SEO expert analyzing search intent. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 500
            },
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        # Extract JSON from response
        try:
            # Try to parse as JSON directly
            return json.loads(content)
        except:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            # Fallback: try to find JSON object
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            raise ValueError("Could not parse JSON from OpenAI response")
    
    def _analyze_with_huggingface(self, prompt: str) -> Dict:
        """Analyze intent using Hugging Face API"""
        # Hugging Face inference API
        response = requests.post(
            "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2",
            headers={
                "Authorization": f"Bearer {self.huggingface_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 500,
                    "temperature": 0.3
                }
            },
            timeout=60
        )
        response.raise_for_status()
        
        result = response.json()
        # Hugging Face returns different formats, handle accordingly
        if isinstance(result, list) and len(result) > 0:
            content = result[0].get("generated_text", "")
        else:
            content = str(result)
        
        # Try to extract JSON (similar to OpenAI)
        import json
        import re
        try:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except:
            pass
        
        # Fallback
        return self._fallback_intent_analysis("", [])
    
    def _fallback_intent_analysis(self, keyword: str, serp_results: List[Dict]) -> Dict:
        """Fallback rule-based intent analysis"""
        keyword_lower = keyword.lower()
        
        # Simple intent detection
        if any(word in keyword_lower for word in ["how", "what", "why", "when", "where", "guide", "tutorial"]):
            intent_type = "informational"
            content_format = "how-to" if "how" in keyword_lower else "article"
        elif any(word in keyword_lower for word in ["buy", "price", "cost", "cheap", "best", "top", "review"]):
            intent_type = "commercial"
            content_format = "product" if "review" in keyword_lower or "best" in keyword_lower else "comparison"
        elif any(word in keyword_lower for word in ["?"]):
            intent_type = "informational"
            content_format = "FAQ"
        else:
            intent_type = "informational"
            content_format = "article"
        
        # Generate query variants
        query_variants = []
        if "how" in keyword_lower:
            query_variants.append(keyword.replace("how", "way to"))
        if "best" in keyword_lower:
            query_variants.append(keyword.replace("best", "top"))
        
        return {
            "intent_type": intent_type,
            "content_format": content_format,
            "query_variants": query_variants if query_variants else [keyword],
            "reasoning": "Rule-based fallback analysis"
        }


def get_intent_service() -> IntentService:
    """Get intent service instance"""
    return IntentService()

