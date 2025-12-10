"""
SERP Service - Fetch and enrich SERP data (based on notebook)
"""
import requests
import re
import numpy as np
from typing import Dict, List, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from app.config import SERPAPI_KEY, SERANKING_KEY, SERP_RESULTS_COUNT, TOP_N_POSITIONS


def extract_domain(url: str) -> str:
    """Extract bare domain from URL."""
    try:
        netloc = urlparse(url).netloc
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return ""


def get_domain_trust(url: str, seranking_key: str) -> float:
    """Fetch Domain Trust (DT) from SE Ranking."""
    domain = extract_domain(url)
    if not domain or not seranking_key:
        return np.nan

    endpoint = "https://api.seranking.com/v1/backlinks/authority/domain"
    params = {
        "apikey": seranking_key,
        "target": domain,
        "output": "json",
    }
    try:
        r = requests.get(endpoint, params=params, timeout=10)
        data = r.json()
        return data.get("pages", [{}])[0].get("domain_inlink_rank", np.nan)
    except Exception:
        return np.nan


def get_referring_domains(url: str, seranking_key: str) -> float:
    """Fetch number of referring domains from SE Ranking."""
    domain = extract_domain(url)
    if not domain or not seranking_key:
        return np.nan

    endpoint = "https://api.seranking.com/v1/backlinks/refdomains/count"
    params = {
        "apikey": seranking_key,
        "target": domain,
        "mode": "domain",
        "output": "json",
    }
    try:
        r = requests.get(endpoint, params=params, timeout=10)
        data = r.json()
        return data.get("metrics", [{}])[0].get("refdomains", np.nan)
    except Exception:
        return np.nan


def extract_content_features(url: str) -> tuple:
    """
    Extract content features from URL - focuses on MAIN CONTENT only.
    Returns: word_count, sentence_count, avg_words_per_sentence, flesch_score, html
    """
    try:
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        html = resp.text

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Remove non-content elements
        for tag in soup.find_all(['script', 'style', 'nav', 'header', 'footer',
                                   'aside', 'noscript', 'iframe', 'form']):
            tag.decompose()

        # Remove common non-content class/id patterns
        for tag in soup.find_all(class_=re.compile(r'(nav|menu|sidebar|footer|header|comment|widget|ad|promo|related|share|social)', re.I)):
            tag.decompose()
        for tag in soup.find_all(id=re.compile(r'(nav|menu|sidebar|footer|header|comment|widget|ad|promo|related|share|social)', re.I)):
            tag.decompose()

        # Try to find main content area
        main_content = None
        for selector in ['article', 'main', '[role="main"]', '.post-content',
                         '.entry-content', '.article-content', '.content', '#content']:
            if selector.startswith('.') or selector.startswith('#'):
                # Class or ID selector
                if selector.startswith('.'):
                    main_content = soup.find(class_=selector[1:])
                else:
                    main_content = soup.find(id=selector[1:])
            elif selector.startswith('['):
                # Attribute selector
                attr_name = selector[1:-1].split('=')[0]
                attr_val = selector[1:-1].split('=')[1].strip('"')
                main_content = soup.find(attrs={attr_name: attr_val})
            else:
                main_content = soup.find(selector)

            if main_content:
                break

        # Fall back to body if no main content found
        if not main_content:
            main_content = soup.find('body') or soup

        # Extract text from main content only
        text = main_content.get_text(separator=" ")
        text = re.sub(r"\s+", " ", text).strip()

        words = text.split()
        word_count = len(words)

        # Sentence count - look for sentence-ending punctuation
        sentence_count = len(re.findall(r'[.!?]+', text))
        if sentence_count <= 0:
            sentence_count = 1

        avg_wps = word_count / sentence_count

        # Flesch Reading Ease (assume ~1.4 syllables/word for speed)
        flesch = 206.835 - 1.015 * avg_wps - 84.6 * 1.4
        flesch = max(min(flesch, 100), 0)

        return word_count, sentence_count, avg_wps, flesch, html
    except Exception:
        return 0, 0, 0.0, 0.0, ""


def extract_schema_features(html: str) -> tuple:
    """
    Extract schema features (from notebook).
    Returns: total_schema_types, unique_schema_types
    """
    if not html:
        return 0, 0

    types = re.findall(r'"@type"\s*:\s*"([^"]+)"', html)
    if not types:
        return 0, 0

    total = len(types)
    unique = len(set(types))
    return total, unique


class SERPService:
    """Service for fetching and processing SERP data (based on notebook)"""
    
    def __init__(self):
        self.serpapi_key = SERPAPI_KEY
        self.seranking_key = SERANKING_KEY
    
    def fetch_serp_data(self, keyword: str, location: str = "United States", num_results: int = None) -> Dict:
        """
        Fetch SERP data from SERPAPI (same as notebook)

        Args:
            keyword: Search keyword
            location: Search location
            num_results: Number of results to fetch

        Returns:
            Dictionary with SERP data
        """
        if not self.serpapi_key:
            raise ValueError("SERPAPI_KEY not configured")

        num_results = num_results or SERP_RESULTS_COUNT

        params = {
            "q": keyword,
            "location": location,
            "api_key": self.serpapi_key,
            "num": num_results,
            "google_domain": "google.com",
            "gl": "us",
            "hl": "en"
        }

        try:
            response = requests.get("https://serpapi.com/search", params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error fetching SERP data: {e}")

    def extract_serp_features(self, serp_data: Dict) -> Dict:
        """
        Extract all SERP features from SERPAPI response.

        Returns dict with:
        - people_also_ask: List of PAA questions with snippets
        - related_searches: List of related search queries
        - related_questions: Additional questions from knowledge panel
        - featured_snippet: Featured snippet if present
        - knowledge_panel: Knowledge panel data if present
        - serp_features_present: List of feature types found
        """
        features = {
            "people_also_ask": [],
            "related_searches": [],
            "related_questions": [],
            "featured_snippet": None,
            "knowledge_panel": None,
            "serp_features_present": [],
            "ads_present": False,
            "local_pack": None,
            "video_results": [],
            "image_results": [],
            "news_results": [],
            "shopping_results": []
        }

        # People Also Ask (PAA)
        paa = serp_data.get("related_questions", [])
        if paa:
            features["serp_features_present"].append("people_also_ask")
            for item in paa:
                features["people_also_ask"].append({
                    "question": item.get("question", ""),
                    "snippet": item.get("snippet", ""),
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "source": item.get("source", {}).get("name", "")
                })

        # Related Searches
        related = serp_data.get("related_searches", [])
        if related:
            features["serp_features_present"].append("related_searches")
            for item in related:
                features["related_searches"].append(item.get("query", ""))

        # Featured Snippet
        featured = serp_data.get("answer_box") or serp_data.get("featured_snippet")
        if featured:
            features["serp_features_present"].append("featured_snippet")
            features["featured_snippet"] = {
                "type": featured.get("type", "paragraph"),
                "title": featured.get("title", ""),
                "snippet": featured.get("snippet", featured.get("answer", "")),
                "link": featured.get("link", ""),
                "list": featured.get("list", []),
                "table": featured.get("table", [])
            }

        # Knowledge Panel
        knowledge = serp_data.get("knowledge_graph")
        if knowledge:
            features["serp_features_present"].append("knowledge_panel")
            features["knowledge_panel"] = {
                "title": knowledge.get("title", ""),
                "type": knowledge.get("type", ""),
                "description": knowledge.get("description", ""),
                "source": knowledge.get("source", {}).get("name", ""),
                "attributes": knowledge.get("attributes", {}),
                "people_also_search_for": [
                    item.get("name", "") for item in knowledge.get("people_also_search_for", [])
                ]
            }
            # Add related questions from knowledge panel
            kp_questions = knowledge.get("questions", [])
            for q in kp_questions:
                features["related_questions"].append(q.get("question", ""))

        # Ads
        if serp_data.get("ads"):
            features["serp_features_present"].append("ads")
            features["ads_present"] = True

        # Local Pack (Map Results)
        local = serp_data.get("local_results")
        if local:
            features["serp_features_present"].append("local_pack")
            features["local_pack"] = {
                "title": local.get("title", ""),
                "places": [
                    {
                        "title": p.get("title", ""),
                        "rating": p.get("rating", 0),
                        "reviews": p.get("reviews", 0),
                        "type": p.get("type", "")
                    }
                    for p in local.get("places", [])[:5]
                ]
            }

        # Video Results
        videos = serp_data.get("inline_videos", [])
        if videos:
            features["serp_features_present"].append("video_results")
            for v in videos[:5]:
                features["video_results"].append({
                    "title": v.get("title", ""),
                    "link": v.get("link", ""),
                    "platform": v.get("platform", ""),
                    "duration": v.get("duration", "")
                })

        # Image Results
        images = serp_data.get("inline_images", [])
        if images:
            features["serp_features_present"].append("image_results")
            features["image_results"] = [img.get("title", "") for img in images[:5]]

        # News Results
        news = serp_data.get("news_results", []) or serp_data.get("top_stories", [])
        if news:
            features["serp_features_present"].append("news_results")
            for n in news[:5]:
                features["news_results"].append({
                    "title": n.get("title", ""),
                    "source": n.get("source", ""),
                    "date": n.get("date", "")
                })

        # Shopping Results
        shopping = serp_data.get("shopping_results", [])
        if shopping:
            features["serp_features_present"].append("shopping_results")
            for s in shopping[:5]:
                features["shopping_results"].append({
                    "title": s.get("title", ""),
                    "price": s.get("price", ""),
                    "source": s.get("source", "")
                })

        return features
    
    def extract_organic_results(self, serp_data: Dict) -> List[Dict]:
        """Extract organic search results from SERP data"""
        organic_results = serp_data.get("organic_results", [])
        
        extracted = []
        for result in organic_results:
            link = result.get("link")
            if not link:
                continue
            extracted.append({
                "position": result.get("position", len(extracted) + 1),
                "title": result.get("title", ""),
                "url": link,
                "snippet": result.get("snippet", ""),
                "displayed_link": result.get("displayed_link", ""),
            })
        
        return extracted
    
    def enrich_serp_results(self, serp_results: List[Dict], limit: int = 10) -> List[Dict]:
        """
        Enrich SERP results with content features (from notebook).
        Fetches HTML, extracts features, gets authority metrics.
        Limit to top N results for performance.
        """
        enriched = []
        
        # Only process top N results to speed up
        for result in serp_results[:limit]:
            url = result.get("url") or result.get("link", "")
            if not url:
                continue
            
            try:
                # Extract content features (with timeout)
                wc, sent_c, awps, flesch, html = extract_content_features(url)
                
                # Extract schema features
                schema_total, schema_unique = extract_schema_features(html)
                
                # Get authority metrics (with timeout)
                dt = get_domain_trust(url, self.seranking_key)
                ref_domains = get_referring_domains(url, self.seranking_key)
                
                # Defaults
                internal_links = 0.0  # Would need to parse HTML for actual count
                rich_result_features = 0.0  # Would need SERPAPI rich results data
                
                enriched.append({
                    **result,
                    "url": url,  # Ensure URL is set
                    "dt": float(dt) if not np.isnan(dt) else 0.0,
                    "referring_domains": float(ref_domains) if not np.isnan(ref_domains) else 0.0,
                    "word_count": wc,
                    "sentence_count": sent_c,
                    "average_words_per_sentence": awps,
                    "flesch_reading_ease_score": flesch,
                    "total_schema_types": schema_total,
                    "unique_schema_types": schema_unique,
                    "internal_links": internal_links,
                    "rich_result_features": rich_result_features,
                    "raw_html": html,  # Store HTML for semantic analysis
                })
            except Exception as e:
                print(f"Error enriching {url}: {e}")
                # Add with defaults if enrichment fails
                enriched.append({
                    **result,
                    "url": url,
                    "dt": 0.0,
                    "referring_domains": 0.0,
                    "word_count": 0,
                    "sentence_count": 0,
                    "average_words_per_sentence": 0.0,
                    "flesch_reading_ease_score": 0.0,
                    "total_schema_types": 0,
                    "unique_schema_types": 0,
                    "internal_links": 0.0,
                    "rich_result_features": 0.0,
                    "raw_html": "",
                })
        
        return enriched
    
    def calculate_serp_medians(self, enriched_results: List[Dict], top_n: int = None) -> Dict:
        """
        Calculate median values for Top-N positions (from notebook)
        
        Args:
            enriched_results: Enriched SERP results with metrics
            top_n: Number of top positions to analyze
            
        Returns:
            Dictionary with median values
        """
        top_n = top_n or TOP_N_POSITIONS
        
        top_results = enriched_results[:top_n]
        if not top_results:
            return self._get_default_medians()
        
        medians = {}
        metrics = [
            "dt", "referring_domains", "word_count", "sentence_count",
            "average_words_per_sentence", "flesch_reading_ease_score",
            "total_schema_types", "unique_schema_types", "internal_links",
            "rich_result_features"
        ]
        
        for metric in metrics:
            values = [r.get(metric, 0) for r in top_results if metric in r]
            if values:
                medians[metric] = float(np.median(values))
            else:
                medians[metric] = 0.0
        
        return medians
    
    def _get_default_medians(self) -> Dict:
        """Get default median values when SERP data is unavailable"""
        return {
            "dt": 50.0,
            "referring_domains": 30.0,
            "word_count": 2000.0,
            "sentence_count": 100.0,
            "average_words_per_sentence": 20.0,
            "flesch_reading_ease_score": 60.0,
            "total_schema_types": 2.0,
            "unique_schema_types": 1.0,
            "internal_links": 10.0,
            "rich_result_features": 1.0,
        }


def get_serp_service() -> SERPService:
    """Get SERP service instance"""
    return SERPService()

