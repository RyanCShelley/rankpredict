"""
Content fetcher service for extracting real content metrics from URLs.
Fetches HTML and extracts word count, sentence count, Flesch score, schema, etc.
Enhanced version with caching and accurate Flesch calculation.
"""
import re
import requests
from typing import Dict, Optional, Tuple, List
from bs4 import BeautifulSoup
import time


class ContentFetcherService:
    """Service for fetching and analyzing content from URLs"""

    def __init__(self):
        self._cache: Dict[str, Tuple[Dict, float]] = {}  # url -> (metrics, timestamp)
        self._cache_ttl = 1800  # 30 minute cache
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    def _is_cache_valid(self, url: str) -> bool:
        """Check if cached data is still valid"""
        if url not in self._cache:
            return False
        _, timestamp = self._cache[url]
        return (time.time() - timestamp) < self._cache_ttl

    def fetch_content_metrics(self, url: str) -> Dict:
        """
        Fetch and analyze content from a URL.

        Args:
            url: URL to analyze

        Returns:
            Dictionary with content metrics
        """
        # Check cache
        if self._is_cache_valid(url):
            metrics, _ = self._cache[url]
            return metrics

        # Fetch HTML
        html = self._fetch_html(url)
        if not html:
            return self._get_empty_metrics()

        # Extract all metrics
        metrics = self._extract_all_metrics(html, url)

        # Cache the results
        self._cache[url] = (metrics, time.time())

        return metrics

    def _fetch_html(self, url: str) -> str:
        """Fetch HTML from URL"""
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching HTML from {url}: {e}")
            return ""

    def _extract_all_metrics(self, html: str, url: str) -> Dict:
        """Extract all content metrics from HTML"""
        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        # Extract text content
        text = soup.get_text(separator=" ", strip=True)

        # Word count
        words = text.split()
        word_count = len(words)

        # Sentence count (improved detection)
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        sentence_count = max(len(sentences), 1)

        # Average words per sentence
        avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0

        # Flesch Reading Ease Score
        flesch_score = self._calculate_flesch_score(word_count, sentence_count, text)

        # Schema markup analysis
        schema_total, schema_unique, schema_types = self._extract_schema_features(html)

        # Link analysis
        internal_links, external_links = self._count_links(soup, url)

        # Title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # H1
        h1_tag = soup.find("h1")
        h1 = h1_tag.get_text(strip=True) if h1_tag else ""

        # Meta description
        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": "description"})
        if meta_tag:
            meta_desc = meta_tag.get("content", "")

        # First paragraph
        first_para = ""
        for p in soup.find_all("p"):
            p_text = p.get_text(strip=True)
            if p_text and len(p_text) > 50:
                first_para = p_text[:500]
                break

        return {
            "word_count": word_count,
            "sentence_count": sentence_count,
            "average_words_per_sentence": avg_sentence_length,
            "flesch_reading_ease_score": flesch_score,
            "total_schema_types": schema_total,
            "unique_schema_types": schema_unique,
            "schema_types": schema_types,
            "internal_links": internal_links,
            "external_links": external_links,
            "title": title,
            "h1": h1,
            "meta_description": meta_desc,
            "first_paragraph": first_para,
            "raw_html": html,
        }

    def _calculate_flesch_score(self, word_count: int, sentence_count: int, text: str) -> float:
        """
        Calculate Flesch Reading Ease Score.
        Formula: 206.835 - 1.015 * (words/sentences) - 84.6 * (syllables/words)
        """
        if word_count == 0 or sentence_count == 0:
            return 0.0

        avg_words_per_sentence = word_count / sentence_count

        # Estimate syllables
        syllable_count = self._estimate_syllables(text)
        avg_syllables_per_word = syllable_count / word_count if word_count > 0 else 1.5

        flesch = 206.835 - (1.015 * avg_words_per_sentence) - (84.6 * avg_syllables_per_word)

        # Clamp to valid range
        return max(0.0, min(100.0, flesch))

    def _estimate_syllables(self, text: str) -> int:
        """Estimate syllable count using vowel groups"""
        text = text.lower()
        words = text.split()
        total_syllables = 0

        for word in words:
            word = re.sub(r'[^a-z]', '', word)
            if not word:
                continue

            syllables = len(re.findall(r'[aeiouy]+', word))

            if word.endswith('e') and len(word) > 2:
                syllables = max(1, syllables - 1)
            if word.endswith('le') and len(word) > 2 and word[-3] not in 'aeiou':
                syllables += 1

            total_syllables += max(1, syllables)

        return total_syllables

    def _extract_schema_features(self, html: str) -> Tuple[int, int, List[str]]:
        """Extract schema markup information from HTML."""
        if not html:
            return 0, 0, []

        types = re.findall(r'"@type"\s*:\s*"([^"]+)"', html)
        microdata_types = re.findall(r'itemtype="[^"]*schema\.org/([^"]+)"', html)
        types.extend(microdata_types)

        if not types:
            return 0, 0, []

        total = len(types)
        unique = len(set(types))
        return total, unique, list(set(types))

    def _count_links(self, soup: BeautifulSoup, page_url: str) -> Tuple[int, int]:
        """Count internal and external links on a page."""
        from urllib.parse import urlparse

        page_domain = urlparse(page_url).netloc.replace("www.", "")

        internal = 0
        external = 0

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]

            if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
                continue

            if href.startswith("/") or not href.startswith("http"):
                internal += 1
                continue

            try:
                link_domain = urlparse(href).netloc.replace("www.", "")
                if link_domain == page_domain:
                    internal += 1
                else:
                    external += 1
            except:
                external += 1

        return internal, external

    def _get_empty_metrics(self) -> Dict:
        """Return empty metrics when fetch fails"""
        return {
            "word_count": 0,
            "sentence_count": 0,
            "average_words_per_sentence": 0,
            "flesch_reading_ease_score": 0,
            "total_schema_types": 0,
            "unique_schema_types": 0,
            "schema_types": [],
            "internal_links": 0,
            "external_links": 0,
            "title": "",
            "h1": "",
            "meta_description": "",
            "first_paragraph": "",
            "raw_html": "",
        }

    def fetch_batch_metrics(self, urls: List[str]) -> Dict[str, Dict]:
        """Fetch content metrics for multiple URLs."""
        results = {}
        for url in urls:
            try:
                results[url] = self.fetch_content_metrics(url)
            except Exception as e:
                print(f"Error fetching metrics for {url}: {e}")
                results[url] = self._get_empty_metrics()
        return results


# Global service instance
_content_fetcher_service: Optional[ContentFetcherService] = None


def get_content_fetcher_service() -> ContentFetcherService:
    """Get or initialize the global content fetcher service instance"""
    global _content_fetcher_service
    if _content_fetcher_service is None:
        _content_fetcher_service = ContentFetcherService()
    return _content_fetcher_service
