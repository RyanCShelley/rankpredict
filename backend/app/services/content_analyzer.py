"""
Content Analyzer - For refresh mode (existing content)
Compares existing content against SERP and identifies gaps
Uses OpenAI for intelligent topic extraction and improvement plans
"""
import requests
import re
import json
from typing import Dict, List
from bs4 import BeautifulSoup
from app.services.semantic_service import get_semantic_service
from app.config import OPENAI_API_KEY


# Comprehensive stop words list
STOP_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
    'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did',
    'will', 'would', 'should', 'could', 'may', 'might', 'must', 'can',
    'this', 'that', 'these', 'those', 'what', 'which', 'who', 'when', 'where', 'why', 'how',
    'your', 'from', 'directly', 'their', 'them', 'they', 'we', 'our', 'you', 'it', 'its',
    'as', 'if', 'than', 'so', 'up', 'out', 'just', 'now', 'then', 'more', 'most', 'very',
    'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between',
    'under', 'again', 'further', 'once', 'here', 'there', 'when', 'where', 'why', 'how',
    'all', 'each', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
    'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'can', 'will', 'just'
}


def count_syllables(word: str) -> int:
    """
    Count syllables in a word using a simple vowel-based heuristic.
    """
    word = word.lower().strip()
    if not word:
        return 0

    vowels = "aeiouy"
    count = 0
    prev_was_vowel = False

    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_was_vowel:
            count += 1
        prev_was_vowel = is_vowel

    # Handle silent 'e' at end
    if word.endswith('e') and count > 1:
        count -= 1

    # Handle special endings
    if word.endswith('le') and len(word) > 2 and word[-3] not in vowels:
        count += 1

    return max(1, count)


class ContentAnalyzer:
    """Service for analyzing existing content and comparing against SERP"""

    def __init__(self):
        self.semantic_service = get_semantic_service()
        self.openai_api_key = OPENAI_API_KEY
    
    def analyze_existing_content(self, url: str, keyword: str) -> Dict:
        """
        Analyze existing content at URL
        
        Args:
            url: URL of existing content
            keyword: Target keyword
            
        Returns:
            Dictionary with content metrics
        """
        try:
            resp = requests.get(url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            resp.raise_for_status()
            html = resp.text
            
            soup = BeautifulSoup(html, "html.parser")
            
            # Extract text
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text()
            # Filter to only alphanumeric words
            words = [w for w in text.split() if any(c.isalpha() for c in w)]
            word_count = len(words)

            # Count sentences - look for sentence-ending punctuation
            sentence_count = len(re.findall(r'[.!?]+', text))
            if sentence_count < 1:
                sentence_count = max(1, word_count // 15)  # Estimate ~15 words per sentence

            avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 15

            # Calculate actual syllables per word (sample for performance)
            sample_size = min(100, word_count)
            if sample_size > 0:
                sample_words = words[:sample_size]
                total_syllables = sum(count_syllables(w) for w in sample_words)
                avg_syllables_per_word = total_syllables / sample_size
            else:
                avg_syllables_per_word = 1.5  # Default fallback

            # Calculate Flesch score: 206.835 - 1.015*(words/sentences) - 84.6*(syllables/words)
            flesch_score = 206.835 - 1.015 * avg_sentence_length - 84.6 * avg_syllables_per_word
            flesch_score = max(min(flesch_score, 100), 0)
            
            # Count internal links
            domain = url.split("/")[2] if "/" in url else url
            internal_links = 0
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                if href.startswith("/") or domain in href:
                    internal_links += 1
            
            # Extract schema types
            schema_types = []
            schema_scripts = soup.find_all("script", type="application/ld+json")
            for script in schema_scripts:
                try:
                    schema_data = json.loads(script.string)
                    if isinstance(schema_data, dict):
                        schema_type = schema_data.get("@type", "")
                        if schema_type:
                            schema_types.append(schema_type)
                    elif isinstance(schema_data, list):
                        for item in schema_data:
                            if isinstance(item, dict):
                                schema_type = item.get("@type", "")
                                if schema_type:
                                    schema_types.append(schema_type)
                except:
                    pass
            
            schema_count = len(schema_types)
            schema_unique = len(set(schema_types))
            
            # Compute semantic score - IMPORTANT: This should be between 0 and 1
            semantic_score = self.semantic_service.compute_semantic_score(keyword, html)
            # Ensure it's a valid score (not 1.0 by default)
            if semantic_score >= 1.0:
                semantic_score = 0.7  # Default reasonable score if calculation seems off
            
            # Extract H2 headings
            h2_headings = [h2.get_text(strip=True) for h2 in soup.find_all("h2")]

            # Extract title
            title_tag = soup.find("title")
            page_title = title_tag.get_text(strip=True) if title_tag else ""

            # Extract H1
            h1_tag = soup.find("h1")
            h1_text = h1_tag.get_text(strip=True) if h1_tag else ""

            # Extract meta description
            meta_desc = ""
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag:
                meta_desc = meta_tag.get("content", "")

            return {
                "word_count": word_count,
                "sentence_count": sentence_count,
                "average_words_per_sentence": avg_sentence_length,
                "flesch_reading_ease_score": flesch_score,
                "internal_links": internal_links,
                "total_schema_types": schema_count,
                "unique_schema_types": schema_unique,
                "semantic_topic_score": semantic_score,
                "h2_headings": h2_headings,
                "url": url,
                "raw_html": html,  # Store for OpenAI analysis
                "page_text": text,  # Clean text for annotation
                "page_title": page_title,
                "h1": h1_text,
                "meta_description": meta_desc
            }
        except Exception as e:
            print(f"Error analyzing content at {url}: {e}")
            return {
                "word_count": 0,
                "sentence_count": 0,
                "average_words_per_sentence": 0,
                "flesch_reading_ease_score": 0,
                "internal_links": 0,
                "total_schema_types": 0,
                "unique_schema_types": 0,
                "semantic_topic_score": 0,
                "h2_headings": [],
                "url": url,
                "raw_html": ""
            }
    
    def compare_against_serp(
        self,
        current_content: Dict,
        serp_medians: Dict[str, float],
        serp_results: List[Dict]
    ) -> Dict:
        """
        Compare existing content against SERP and identify gaps
        Uses OpenAI for intelligent topic extraction
        """
        gaps = {}
        improvements = []
        
        # Word count gap
        wc_gap = current_content.get("word_count", 0) - serp_medians.get("word_count", 0)
        gaps["word_count"] = {
            "current": current_content.get("word_count", 0),
            "target": serp_medians.get("word_count", 0),
            "gap": wc_gap,
            "gap_percentage": (wc_gap / serp_medians.get("word_count", 1)) * 100 if serp_medians.get("word_count", 0) > 0 else 0
        }
        if wc_gap < -500:
            improvements.append({
                "metric": "Word Count",
                "issue": f"Content is {abs(int(wc_gap))} words shorter than SERP median",
                "action": f"Add {abs(int(wc_gap))}+ words to match competitor depth",
                "priority": "High"
            })
        
        # Semantic score gap - ensure both are valid scores
        current_sem = current_content.get("semantic_topic_score", 0)
        target_sem = serp_medians.get("semantic_topic_score", 0.7)
        
        # Clamp values to reasonable range
        if current_sem > 1.0:
            current_sem = 0.7
        if target_sem > 1.0:
            target_sem = 0.7
        
        sem_gap = current_sem - target_sem
        gaps["semantic_topic_score"] = {
            "current": current_sem,
            "target": target_sem,
            "gap": sem_gap,
            "gap_percentage": (sem_gap / target_sem * 100) if target_sem > 0 else 0
        }
        if sem_gap < -0.1:
            improvements.append({
                "metric": "Semantic Alignment",
                "issue": "Content doesn't align well with query intent",
                "action": "Improve semantic alignment by using query-related terms and entities throughout",
                "priority": "High"
            })
        
        # Internal links gap
        il_gap = current_content.get("internal_links", 0) - serp_medians.get("internal_links", 0)
        gaps["internal_links"] = {
            "current": current_content.get("internal_links", 0),
            "target": serp_medians.get("internal_links", 0),
            "gap": il_gap,
            "gap_percentage": (il_gap / serp_medians.get("internal_links", 1)) * 100 if serp_medians.get("internal_links", 0) > 0 else 0
        }
        if il_gap < -5:
            improvements.append({
                "metric": "Internal Links",
                "issue": f"Missing {abs(int(il_gap))} internal links compared to SERP",
                "action": f"Add {abs(int(il_gap))}+ contextual internal links to related pages",
                "priority": "Medium"
            })
        
        # Schema gap
        schema_gap = current_content.get("total_schema_types", 0) - serp_medians.get("total_schema_types", 0)
        gaps["schema"] = {
            "current": current_content.get("total_schema_types", 0),
            "target": serp_medians.get("total_schema_types", 0),
            "gap": schema_gap,
            "gap_percentage": (schema_gap / serp_medians.get("total_schema_types", 1)) * 100 if serp_medians.get("total_schema_types", 0) > 0 else 0
        }
        if schema_gap < 0:
            improvements.append({
                "metric": "Schema Markup",
                "issue": "Missing schema markup compared to SERP",
                "action": "Add relevant schema types (Article, FAQ, HowTo, etc.)",
                "priority": "Medium"
            })
        
        # Topic gaps - use OpenAI for intelligent extraction
        missing_topics = self._extract_missing_topics_with_llm(
            current_content,
            serp_results,
            serp_medians
        )
        
        if missing_topics:
            improvements.append({
                "metric": "Topic Coverage",
                "issue": f"Missing topics: {', '.join(missing_topics[:5])}",
                "action": f"Add sections covering: {', '.join(missing_topics[:5])}",
                "priority": "High"
            })
        
        return {
            "gaps": gaps,
            "improvements": improvements,
            "missing_topics": missing_topics[:10],
            "current_metrics": current_content,
            "serp_medians": serp_medians
        }
    
    def _extract_missing_topics_with_llm(
        self,
        current_content: Dict,
        serp_results: List[Dict],
        serp_medians: Dict[str, float]
    ) -> List[str]:
        """Extract missing topics using OpenAI - filters out stop words"""
        try:
            # Prepare SERP titles and snippets
            serp_text = "\n".join([
                f"{r.get('title', '')} {r.get('snippet', '')}"
                for r in serp_results[:10]
            ])
            
            current_text = current_content.get("raw_html", "")[:2000]  # Limit for API
            
            prompt = f"""Analyze the following SERP results and existing content to identify topics that competitors cover but the existing content is missing.

SERP Results (what competitors cover):
{serp_text[:1500]}

Existing Content (first 2000 chars):
{current_text[:1500]}

Return a JSON array of 5-10 specific, meaningful topics (not stop words like "the", "from", "your", "directly") that competitors cover but the existing content is missing. Focus on substantive topics, concepts, or themes.

Format: ["topic1", "topic2", "topic3", ...]

Return ONLY the JSON array, no other text."""

            if not self.openai_api_key:
                return []
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "You are an expert content analyst. Return only valid JSON arrays."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 200
                },
                timeout=60  # Increased timeout
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # Extract JSON array
            import re
            json_match = re.search(r'\[.*?\]', content, re.DOTALL)
            if json_match:
                topics = json.loads(json_match.group(0))
                # Filter out stop words
                return [t for t in topics if isinstance(t, str) and t.lower() not in STOP_WORDS and len(t) > 2]
            
            return []
        except Exception as e:
            print(f"Error extracting topics with LLM: {e}")
            # Fallback to basic extraction
            return self._extract_topics_fallback(serp_results)
    
    def _extract_topics_fallback(self, serp_results: List[Dict]) -> List[str]:
        """Fallback topic extraction - filters stop words"""
        all_text = " ".join([
            r.get("title", "") + " " + r.get("snippet", "")
            for r in serp_results[:10]
        ]).lower()
        
        words = re.findall(r'\b\w+\b', all_text)
        from collections import Counter
        word_freq = Counter(words)
        
        # Filter out stop words and short words
        topics = [
            word for word, count in word_freq.most_common(20)
            if word not in STOP_WORDS and len(word) > 3 and count >= 2
        ]
        
        return topics[:10]
    
    def _extract_topics_from_content(self, h2_headings: List[str]) -> List[str]:
        """Extract topics from content H2 headings"""
        topics = []
        for h2 in h2_headings:
            words = re.findall(r'\b\w+\b', h2.lower())
            topics.extend([w for w in words if w not in STOP_WORDS and len(w) > 3])
        return topics
    
    def generate_improvement_plan(
        self,
        current_content: Dict,
        serp_analysis: Dict,
        keyword: str
    ) -> Dict:
        """
        Generate improvement plan using OpenAI for existing content
        """
        comparison = self.compare_against_serp(
            current_content,
            serp_analysis.get("medians", {}),
            serp_analysis.get("results", [])
        )
        
        # Use OpenAI for detailed improvement plan
        try:
            serp_data_text = self._format_serp_for_llm(serp_analysis.get("results", []), serp_analysis.get("medians", {}))
            current_content_text = current_content.get("raw_html", "")[:3000]
            
            prompt = f"""You are a senior content strategist specializing in content optimization. Using the SERP analysis data and existing content provided below, create a detailed optimization plan.

**SERP Analysis Data:**
{serp_data_text}

**Existing Content to Optimize:**
{current_content_text[:2000]}

**Keyword:** {keyword}

**Your Task:**

Analyze how the existing content compares to top competitors and generate an optimization plan that includes:

1. **Current Content Audit**
   - Current word count vs. competitor median
   - Readability score comparison
   - Schema markup present vs. competitors
   - Semantic topic coverage assessment

2. **Gap Analysis**
   - Topics competitors cover that we're missing
   - Sections that need expansion or deeper coverage
   - Content elements to add (definitions, examples, data, visuals)
   - Areas where we're stronger than competitors (protect these)

3. **Optimization Recommendations**
   - **ADD:** New sections or topics to include
   - **EXPAND:** Existing sections that need more depth
   - **UPDATE:** Outdated information or stats to refresh
   - **RESTRUCTURE:** Flow or organization improvements
   - **REMOVE:** Redundant or off-topic content hurting focus

4. **Revised Content Outline**
   - Optimized H1 recommendation (if needed)
   - Updated H2/H3 structure with new and existing sections marked
   - Target word count for each section
   - Priority ranking for each change (High/Medium/Low)

5. **Technical Optimization Checklist**
   - Schema types to add or improve
   - Internal linking opportunities (on-page SEO)
   - Readability adjustments needed
   - Featured snippet/AI answer optimization opportunities

6. **Implementation Roadmap**
   - Quick wins (implement immediately)
   - Medium effort improvements
   - Major content additions
   - Estimated time to complete optimization

Return as JSON with this structure:
{{
  "content_audit": {{...}},
  "gap_analysis": {{...}},
  "optimization_recommendations": {{...}},
  "revised_outline": {{...}},
  "technical_checklist": {{...}},
  "implementation_roadmap": {{...}}
}}

Return ONLY valid JSON."""

            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY not configured")
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "You are an expert SEO content strategist. Always return valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000
                },
                timeout=120  # Increased timeout
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # Extract JSON
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                llm_plan = json.loads(json_match.group(0))
                # Merge with our gap analysis
                return {
                    "keyword": keyword,
                    "current_url": current_content.get("url", ""),
                    "gap_analysis": comparison["gaps"],
                    "improvements": comparison["improvements"],
                    "missing_topics": comparison["missing_topics"],
                    "llm_optimization_plan": llm_plan,
                    "priority_actions": sorted(
                        comparison["improvements"],
                        key=lambda x: {"High": 3, "Medium": 2, "Low": 1}.get(x.get("priority", "Low"), 1),
                        reverse=True
                    )[:5]
                }
        except Exception as e:
            print(f"Error generating LLM improvement plan: {e}")
        
        # Fallback to basic plan
        return {
            "keyword": keyword,
            "current_url": current_content.get("url", ""),
            "gap_analysis": comparison["gaps"],
            "improvements": comparison["improvements"],
            "missing_topics": comparison["missing_topics"],
            "priority_actions": sorted(
                comparison["improvements"],
                key=lambda x: {"High": 3, "Medium": 2, "Low": 1}.get(x.get("priority", "Low"), 1),
                reverse=True
            )[:5]
        }
    
    def _format_serp_for_llm(self, serp_results: List[Dict], serp_medians: Dict[str, float]) -> str:
        """Format SERP data for LLM prompt"""
        lines = [
            f"SERP Metrics (Top 10 Medians):",
            f"- Word Count: {serp_medians.get('word_count', 0):.0f}",
            f"- Domain Trust: {serp_medians.get('dt', 0):.1f}",
            f"- Semantic Topic Score: {serp_medians.get('semantic_topic_score', 0):.3f}",
            f"\nTop 10 Results:",
        ]
        
        for i, result in enumerate(serp_results[:10], 1):
            lines.append(f"{i}. {result.get('title', '')} - {result.get('snippet', '')[:150]}")
        
        return "\n".join(lines)


def get_content_analyzer() -> ContentAnalyzer:
    """Get content analyzer instance"""
    return ContentAnalyzer()
