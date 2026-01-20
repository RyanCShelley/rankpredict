"""
Keywords Everywhere API Service - Fetch search volume data for keywords
"""
import requests
from typing import Dict, List, Optional
from app.config import KEYWORDS_EVERYWHERE_API_KEY


class KeywordsEverywhereService:
    """Service for fetching keyword volume data from Keywords Everywhere API"""

    def __init__(self):
        self.api_key = KEYWORDS_EVERYWHERE_API_KEY
        self.base_url = "https://api.keywordseverywhere.com/v1"

    def get_keyword_data(
        self,
        keywords: List[str],
        country: str = "us",
        currency: str = "USD"
    ) -> Dict[str, Dict]:
        """
        Fetch search volume and CPC data for a list of keywords.

        Args:
            keywords: List of keywords to fetch data for (max 100 per request)
            country: Two-letter country code (default: "us")
            currency: Currency for CPC (default: "USD")

        Returns:
            Dictionary mapping keyword to its data (vol, cpc, competition, trend)
        """
        if not self.api_key:
            print("Warning: KEYWORDS_EVERYWHERE_API_KEY not configured")
            return {}

        if not keywords:
            return {}

        # API accepts max 100 keywords at a time
        results = {}
        for i in range(0, len(keywords), 100):
            batch = keywords[i:i + 100]
            batch_results = self._fetch_batch(batch, country, currency)
            results.update(batch_results)

        return results

    def _fetch_batch(
        self,
        keywords: List[str],
        country: str,
        currency: str
    ) -> Dict[str, Dict]:
        """Fetch a single batch of up to 100 keywords"""
        endpoint = f"{self.base_url}/get_keyword_data"

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # Build form data with kw[] array format
        data = {
            "country": country,
            "currency": currency,
            "dataSource": "gkp"  # Google Keyword Planner
        }

        # Add keywords as kw[] array
        for kw in keywords:
            if "kw[]" not in data:
                data["kw[]"] = []
            if isinstance(data["kw[]"], list):
                data["kw[]"].append(kw)

        try:
            response = requests.post(
                endpoint,
                headers=headers,
                data=data,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            # Parse response into keyword -> data mapping
            keyword_data = {}
            if "data" in result:
                for item in result["data"]:
                    kw = item.get("keyword", "")
                    if kw:
                        keyword_data[kw.lower()] = {
                            "volume": item.get("vol", 0),
                            "cpc": item.get("cpc", {}).get("value", 0) if isinstance(item.get("cpc"), dict) else item.get("cpc", 0),
                            "competition": item.get("competition", 0),
                            "trend": item.get("trend", [])
                        }

            return keyword_data

        except requests.exceptions.RequestException as e:
            print(f"Error fetching keyword data from Keywords Everywhere: {e}")
            return {}
        except Exception as e:
            print(f"Error parsing Keywords Everywhere response: {e}")
            return {}


# Singleton instance
_service_instance: Optional[KeywordsEverywhereService] = None


def get_keywords_everywhere_service() -> KeywordsEverywhereService:
    """Get Keywords Everywhere service instance (singleton)"""
    global _service_instance
    if _service_instance is None:
        _service_instance = KeywordsEverywhereService()
    return _service_instance


async def fetch_keyword_volumes(keywords: List[str]) -> Dict[str, int]:
    """
    Async helper to fetch volumes for a list of keywords.

    Returns:
        Dict mapping keyword to volume (integer)
    """
    service = get_keywords_everywhere_service()
    data = service.get_keyword_data(keywords)

    # Extract just volumes
    volumes = {}
    for kw, info in data.items():
        vol = info.get("volume", 0)
        if vol:
            volumes[kw] = vol

    return volumes
