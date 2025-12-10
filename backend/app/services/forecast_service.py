"""
Forecast Service - Predicts rankability using forecast approach with competitive gravity calibration
Builds synthetic profiles from Top 10 and predicts probability with realistic adjustments
Applies risk penalizers based on authority gap, referring domains, giant brands, and head terms

Also computes client-specific opportunity scores:
- DomainFit: Your domain authority vs SERP median DT
- IntentFit: How well the keyword matches your vertical
- Forecast %: Chance this is a sensible, winnable term for this client
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
from app.models.ml_model import get_model
from app.services.serp_service import get_serp_service
from app.services.semantic_service import get_semantic_service
from app.config import SERANKING_KEY
import requests


# Giant brand domains that dominate SERPs
GIANT_DOMAINS = [
    "google.com", "support.google.com", "developers.google.com",
    "wikipedia.org", "youtube.com",
    "amazon.com", "linkedin.com", "facebook.com", "instagram.com",
    "hubspot.com", "semrush.com", "ahrefs.com", "moz.com",
    "shopify.com", "mailchimp.com", "salesforce.com"
]

# Vertical keyword patterns for IntentFit scoring
VERTICAL_PATTERNS = {
    "legal": {
        "keywords": ["lawyer", "attorney", "law", "legal", "court", "litigation", "lawsuit",
                    "divorce", "custody", "injury", "accident", "criminal", "defense", "estate",
                    "bankruptcy", "immigration", "patent", "trademark", "contract"],
        "modifiers": ["firm", "office", "services", "consultation", "representation"]
    },
    "healthcare": {
        "keywords": ["doctor", "hospital", "clinic", "medical", "health", "treatment", "therapy",
                    "surgery", "diagnosis", "symptoms", "disease", "condition", "care", "patient",
                    "dental", "dentist", "orthodontist", "physician", "specialist"],
        "modifiers": ["center", "practice", "services", "treatment", "provider"]
    },
    "ecommerce": {
        "keywords": ["buy", "shop", "store", "price", "cheap", "discount", "sale", "deal",
                    "product", "order", "shipping", "delivery", "review", "best", "top"],
        "modifiers": ["online", "free shipping", "wholesale", "retail"]
    },
    "saas": {
        "keywords": ["software", "app", "tool", "platform", "solution", "system", "api",
                    "automation", "integration", "dashboard", "analytics", "management"],
        "modifiers": ["free", "trial", "pricing", "enterprise", "cloud"]
    },
    "finance": {
        "keywords": ["loan", "mortgage", "credit", "investment", "insurance", "bank", "finance",
                    "tax", "accounting", "financial", "advisor", "wealth", "retirement"],
        "modifiers": ["rates", "calculator", "services", "planning"]
    },
    "real_estate": {
        "keywords": ["home", "house", "property", "real estate", "realtor", "agent", "buy",
                    "sell", "rent", "apartment", "condo", "listing", "mls"],
        "modifiers": ["for sale", "for rent", "near me", "local"]
    },
    "home_services": {
        "keywords": ["plumber", "electrician", "hvac", "roofing", "contractor", "repair",
                    "install", "maintenance", "service", "cleaning", "landscaping", "painting"],
        "modifiers": ["near me", "local", "emergency", "residential", "commercial"]
    },
    "marketing": {
        "keywords": ["seo", "marketing", "advertising", "ppc", "social media", "content",
                    "brand", "agency", "campaign", "digital", "email", "conversion"],
        "modifiers": ["services", "strategy", "agency", "consultant"]
    },
    "defense": {
        "keywords": ["defense", "military", "aerospace", "government", "dod", "contractor",
                    "security", "clearance", "weapons", "systems", "tactical", "intel",
                    "cybersecurity", "satellite", "missiles", "naval", "army", "air force"],
        "modifiers": ["contractor", "supplier", "solutions", "systems", "services"]
    },
    "local_business": {
        "keywords": ["near me", "local", "city", "town", "neighborhood", "community",
                    "small business", "family owned", "locally owned", "shop local"],
        "modifiers": ["near me", "in", "nearby", "around", "closest"]
    },
    "manufacturing": {
        "keywords": ["manufacturing", "factory", "production", "industrial", "fabrication",
                    "assembly", "machining", "cnc", "oem", "supplier", "parts", "components",
                    "custom", "precision", "tooling", "warehouse", "distribution"],
        "modifiers": ["company", "services", "solutions", "supplier", "manufacturer"]
    }
}


def count_giant_brands(enriched_results: List[Dict]) -> int:
    """Count how many giant brand domains appear in the SERP"""
    domains = []
    for result in enriched_results:
        url = result.get("url", "")
        domain = extract_domain(url)
        if domain:
            domains.append(domain.lower())
    
    giant_count = sum(1 for d in domains if any(g in d for g in GIANT_DOMAINS))
    return giant_count


def calibrate_rank_probability(
    raw_prob: float,
    median_dt_serp: float,
    median_ref_serp: float,
    my_dt: float,
    my_ref: float,
    query: str,
    giant_brand_count: int
) -> float:
    """
    Balanced Mode calibration with competitive gravity risk penalizers.
    
    Applies multiple risk factors:
      - Authority gap (DT gap)
      - Referring domains ratio
      - Brand dominance in SERP
      - Head-term generic query
    
    Args:
        raw_prob: Raw model predicted probability (0-1)
        median_dt_serp: Median Domain Trust of Top 10 SERP results
        median_ref_serp: Median referring domains of Top 10 SERP results
        my_dt: Your domain's Domain Trust
        my_ref: Your domain's referring domains
        query: The search query
        giant_brand_count: Number of giant brand domains in SERP
        
    Returns:
        Calibrated probability (clamped to realistic SEO range 1%-50%)
    """
    if raw_prob is None or np.isnan(raw_prob):
        return 0.0
    
    # Authority adjustment based on DT gap
    if median_dt_serp is None or np.isnan(median_dt_serp) or np.isnan(my_dt):
        factor_dt = 1.0
    else:
        dt_gap = my_dt - median_dt_serp
        if dt_gap >= 0:
            factor_dt = 1.0
        elif dt_gap > -10:
            factor_dt = 0.85
        elif dt_gap > -20:
            factor_dt = 0.70
        else:
            factor_dt = 0.50
    
    # Referring domains adjustment
    if median_ref_serp is None or np.isnan(median_ref_serp) or median_ref_serp <= 0 or np.isnan(my_ref):
        factor_ref = 1.0
    else:
        ratio = my_ref / median_ref_serp
        if ratio >= 1.0:
            factor_ref = 1.0
        elif ratio >= 0.5:
            factor_ref = 0.9
        elif ratio >= 0.2:
            factor_ref = 0.75
        elif ratio >= 0.05:
            factor_ref = 0.40
        else:
            factor_ref = 0.20
    
    # Brand dominance adjustment
    if giant_brand_count >= 4:
        factor_brand = 0.40
    elif giant_brand_count >= 2:
        factor_brand = 0.70
    else:
        factor_brand = 1.0
    
    # Head-term adjustment (generic, super-competitive)
    q_tokens = len(query.strip().split())
    if q_tokens <= 2:
        factor_head = 0.50
    elif q_tokens <= 3:
        factor_head = 0.80
    else:
        factor_head = 1.0
    
    # Combine all factors
    comp_factor = factor_dt * factor_ref * factor_brand * factor_head
    
    calibrated = raw_prob * comp_factor
    
    # Clamp to realistic SEO range (1%-50%)
    calibrated = max(min(calibrated, 0.50), 0.01)
    
    return calibrated


def bucket_keyword_forecast_tier(pct: float) -> str:
    """
    Balanced mode tiers for *keyword-level* winnability for YOUR domain.
    
    Args:
        pct: Forecast percentage (0-100)
        
    Returns:
        Tier string: T1_GO_NOW, T2_STRATEGIC, T3_LONG_GAME, T4_NOT_WORTH_IT
    """
    if pct >= 20:
        return "T1_GO_NOW"
    if pct >= 10:
        return "T2_STRATEGIC"
    if pct >= 4:
        return "T3_LONG_GAME"
    return "T4_NOT_WORTH_IT"


def get_tier_explanation(tier: str, pct: float, dt_gap: float, giant_brand_count: int, query: str) -> str:
    """
    Generate human-readable explanation for why a keyword is in a specific tier.
    
    Args:
        tier: Tier string (T1_GO_NOW, etc.)
        pct: Forecast percentage
        dt_gap: Domain Trust gap (my_dt - serp_median_dt)
        giant_brand_count: Number of giant brands in SERP
        query: Search query
        
    Returns:
        Explanation string
    """
    reasons = []
    
    # Authority gap
    if dt_gap < -20:
        reasons.append("Significant authority gap (DT -" + str(abs(int(dt_gap))) + " points)")
    elif dt_gap < -10:
        reasons.append("Moderate authority gap (DT -" + str(abs(int(dt_gap))) + " points)")
    elif dt_gap < 0:
        reasons.append("Slight authority gap (DT -" + str(abs(int(dt_gap))) + " points)")
    
    # Giant brands
    if giant_brand_count >= 4:
        reasons.append(f"Highly dominated by giant brands ({giant_brand_count} major brands)")
    elif giant_brand_count >= 2:
        reasons.append(f"Some giant brand competition ({giant_brand_count} major brands)")
    
    # Head term
    q_tokens = len(query.strip().split())
    if q_tokens <= 2:
        reasons.append("Very generic head term (highly competitive)")
    elif q_tokens <= 3:
        reasons.append("Moderately generic term")
    
    if not reasons:
        reasons.append("Competitive but achievable with strong execution")
    
    tier_meanings = {
        "T1_GO_NOW": "High-Probability Wins - Your site can credibly break into Top-10 if you build a strong page",
        "T2_STRATEGIC": "Strategic Targets - Competitive, but achievable with great execution",
        "T3_LONG_GAME": "Long-Game Plays - Very competitive, require long-term authority growth",
        "T4_NOT_WORTH_IT": "Not Worth It - Dominated by giant brands/head terms, unlikely to crack Top-10"
    }
    
    base_explanation = tier_meanings.get(tier, "Unknown tier")
    return f"{base_explanation}. Factors: {', '.join(reasons)}."


def extract_domain(url: str) -> str:
    """Extract bare domain from URL"""
    try:
        netloc = urlparse(url).netloc
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return ""


def get_dt_for_domain(domain: str) -> Optional[float]:
    """Fetch Domain Trust (DT) from SE Ranking"""
    if not domain or not SERANKING_KEY:
        return None
    
    endpoint = "https://api.seranking.com/v1/backlinks/authority/domain"
    params = {
        "apikey": SERANKING_KEY,
        "target": domain,
        "output": "json",
    }
    try:
        r = requests.get(endpoint, params=params, timeout=10)
        data = r.json()
        dt = data.get("pages", [{}])[0].get("domain_inlink_rank", None)
        return float(dt) if dt is not None else None
    except Exception as e:
        print(f"Error fetching DT for {domain}: {e}")
        return None


def get_refdoms_for_domain(domain: str) -> Optional[float]:
    """Fetch number of referring domains from SE Ranking"""
    if not domain or not SERANKING_KEY:
        return None
    
    endpoint = "https://api.seranking.com/v1/backlinks/refdomains/count"
    params = {
        "apikey": SERANKING_KEY,
        "target": domain,
        "mode": "domain",
        "output": "json",
    }
    try:
        r = requests.get(endpoint, params=params, timeout=10)
        data = r.json()
        refdoms = data.get("metrics", [{}])[0].get("refdomains", None)
        return float(refdoms) if refdoms is not None else None
    except Exception as e:
        print(f"Error fetching referring domains for {domain}: {e}")
        return None


class ForecastService:
    """Service for forecasting keyword rank likelihood using forecast approach with calibration"""
    
    def __init__(self):
        self.model = get_model()
        self.serp_service = get_serp_service()
        self.semantic_service = get_semantic_service()
    
    def forecast_keyword_rank_likelihood(
        self,
        keyword: str,
        enriched_results: List[Dict],
        serp_medians: Dict[str, float],
        target_domain_url: Optional[str] = None,
        num_results: int = 25
    ) -> Dict:
        """
        Forecast how likely YOUR site is to break into Top 10 for this keyword.
        
        Uses:
        - Your domain's actual DT and referring domains
        - Top 10 content/schema profiles (median, 25th, 75th percentile)
        - Competitive gravity calibration with risk penalizers
        
        Returns:
          dict with calibrated probabilities, tiers, and explanations
        """
        # Focus on Top 10 results
        top10 = enriched_results[:10] if len(enriched_results) >= 10 else enriched_results
        
        if not top10:
            return {
                "keyword": keyword,
                "baseline_median_pct": 0.0,
                "weaker_25th_pct": 0.0,
                "stronger_75th_pct": 0.0,
                "error": "No SERP results available"
            }
        
        # Count giant brands in SERP
        giant_brand_count = count_giant_brands(enriched_results)
        
        # Get your domain's authority metrics
        my_dt = None
        my_refdoms = None
        if target_domain_url:
            domain = extract_domain(target_domain_url)
            my_dt = get_dt_for_domain(domain)
            my_refdoms = get_refdoms_for_domain(domain)
        
        # Get SERP median DT and referring domains for gap calculation
        serp_median_dt = serp_medians.get("dt", 0)
        serp_median_refdoms = serp_medians.get("referring_domains", 0)
        
        # Calculate DT gap (use your DT if available, otherwise use SERP median as proxy)
        if my_dt is not None:
            dt_gap = my_dt - serp_median_dt
        else:
            # If we can't get your DT, assume you match SERP median (gap = 0)
            dt_gap = 0.0
            my_dt = serp_median_dt
            my_refdoms = serp_median_refdoms
        
        # Build content profiles from Top 10 (median, 25th, 75th percentile)
        content_metrics = {
            "word_count": [r.get("word_count", 0) for r in top10],
            "sentence_count": [r.get("sentence_count", 0) for r in top10],
            "average_words_per_sentence": [r.get("average_words_per_sentence", 0) for r in top10],
            "flesch_reading_ease_score": [r.get("flesch_reading_ease_score", 0) for r in top10],
            "total_schema_types": [r.get("total_schema_types", 0) for r in top10],
            "unique_schema_types": [r.get("unique_schema_types", 0) for r in top10],
            "internal_links": [r.get("internal_links", 0) for r in top10],
            "rich_result_features": [r.get("rich_result_features", 0) for r in top10],
            "semantic_topic_score": [r.get("semantic_topic_score", 0.7) for r in top10]
        }
        
        # Calculate percentiles for content metrics
        median_content = {k: np.median(v) for k, v in content_metrics.items()}
        q25_content = {k: np.percentile(v, 25) for k, v in content_metrics.items()}
        q75_content = {k: np.percentile(v, 75) for k, v in content_metrics.items()}
        
        # Build user metrics for each scenario (using YOUR domain authority)
        def build_user_metrics(content_profile: Dict) -> Dict:
            return {
                "domain_trust": my_dt if my_dt is not None else serp_median_dt,
                "referring_domains": my_refdoms if my_refdoms is not None else serp_median_refdoms,
                **content_profile
            }
        
        median_user_metrics = build_user_metrics(median_content)
        q25_user_metrics = build_user_metrics(q25_content)
        q75_user_metrics = build_user_metrics(q75_content)
        
        # Build feature vectors and get raw probabilities
        def get_raw_prob(user_metrics: Dict) -> float:
            feature_vector = self.model.build_feature_vector(user_metrics, serp_medians)
            feature_array = [feature_vector.get(f, 0.0) for f in self.model.feature_list]
            X = pd.DataFrame([feature_array], columns=self.model.feature_list)
            try:
                return float(self.model.model.predict_proba(X)[:, 1][0])
            except Exception as e:
                print(f"Error in predict_proba: {e}")
                return 0.0
        
        raw_median = get_raw_prob(median_user_metrics)
        raw_q25 = get_raw_prob(q25_user_metrics)
        raw_q75 = get_raw_prob(q75_user_metrics)
        
        # Calibrate probabilities using competitive gravity (multi-factor risk penalizers)
        cal_median = calibrate_rank_probability(
            raw_median, 
            float(serp_median_dt) if serp_median_dt else 40.0,
            float(serp_median_refdoms) if serp_median_refdoms else 0.0,
            float(my_dt) if my_dt is not None else 40.0,
            float(my_refdoms) if my_refdoms is not None else 0.0,
            keyword,
            giant_brand_count
        )
        cal_q25 = calibrate_rank_probability(
            raw_q25,
            float(serp_median_dt) if serp_median_dt else 40.0,
            float(serp_median_refdoms) if serp_median_refdoms else 0.0,
            float(my_dt) if my_dt is not None else 40.0,
            float(my_refdoms) if my_refdoms is not None else 0.0,
            keyword,
            giant_brand_count
        )
        cal_q75 = calibrate_rank_probability(
            raw_q75,
            float(serp_median_dt) if serp_median_dt else 40.0,
            float(serp_median_refdoms) if serp_median_refdoms else 0.0,
            float(my_dt) if my_dt is not None else 40.0,
            float(my_refdoms) if my_refdoms is not None else 0.0,
            keyword,
            giant_brand_count
        )
        
        # Convert to percentages
        median_pct = round(cal_median * 100, 1)
        q25_pct = round(cal_q25 * 100, 1)
        q75_pct = round(cal_q75 * 100, 1)
        
        # Assign tiers
        median_tier = bucket_keyword_forecast_tier(median_pct)
        q25_tier = bucket_keyword_forecast_tier(q25_pct)
        q75_tier = bucket_keyword_forecast_tier(q75_pct)
        
        # Generate explanations
        median_explanation = get_tier_explanation(median_tier, median_pct, dt_gap, giant_brand_count, keyword)
        
        result = {
            "keyword": keyword,
            "my_domain": extract_domain(target_domain_url) if target_domain_url else None,
            "serp_median_dt": float(serp_median_dt),
            "serp_median_refdoms": float(serp_median_refdoms) if serp_median_refdoms else 0.0,
            "my_dt": float(my_dt) if my_dt is not None else None,
            "my_referring_domains": float(my_refdoms) if my_refdoms is not None else None,
            "dt_gap": float(dt_gap),
            "giant_brand_count": giant_brand_count,
            "raw_probs": {
                "median_content_like_top10": round(raw_median, 3),
                "weaker_25th_content": round(raw_q25, 3),
                "stronger_75th_content": round(raw_q75, 3),
            },
            "forecast_pct": {
                "baseline_median_pct": median_pct,
                "weaker_25th_pct": q25_pct,
                "stronger_75th_pct": q75_pct,
            },
            "forecast_tiers": {
                "baseline_median_tier": median_tier,
                "weaker_25th_tier": q25_tier,
                "stronger_75th_tier": q75_tier,
            },
            "tier_explanation": median_explanation
        }
        
        return result

    # ==================== Client Profile / Fit Methods ====================

    def compute_domain_fit(
        self,
        client_domain_trust: float,
        client_referring_domains: float,
        serp_median_dt: float,
        serp_median_refdoms: float
    ) -> Tuple[float, str]:
        """
        Compute DomainFit score: How well does client's authority match the SERP?

        Args:
            client_domain_trust: Client's domain trust score
            client_referring_domains: Client's referring domain count
            serp_median_dt: Median DT of SERP top 10
            serp_median_refdoms: Median referring domains of SERP top 10

        Returns:
            Tuple of (score 0-100, explanation string)
        """
        # Calculate ratios
        dt_ratio = client_domain_trust / serp_median_dt if serp_median_dt > 0 else 1.0
        rd_ratio = client_referring_domains / serp_median_refdoms if serp_median_refdoms > 0 else 1.0

        # Weighted average (DT slightly more important)
        combined_ratio = (dt_ratio * 0.55 + rd_ratio * 0.45)

        # Convert to 0-100 score with diminishing returns above 1.0
        if combined_ratio >= 1.0:
            score = min(100, 50 + (combined_ratio - 1.0) * 50 / 1.0)
        else:
            score = max(0, combined_ratio * 50)

        # Generate explanation
        if score >= 80:
            explanation = "Strong authority match - your domain can compete with current Top 10"
        elif score >= 60:
            explanation = "Good authority match - competitive but may need content edge"
        elif score >= 40:
            explanation = "Moderate authority gap - focus on content quality and relevance"
        elif score >= 20:
            explanation = "Significant authority gap - target long-tail or build authority first"
        else:
            explanation = "Large authority gap - this SERP may be out of reach currently"

        return round(score, 1), explanation

    def compute_intent_fit(
        self,
        keyword: str,
        client_vertical: str,
        client_vertical_keywords: Optional[List[str]] = None
    ) -> Tuple[float, str]:
        """
        Compute IntentFit score: How well does keyword match client's vertical?

        Args:
            keyword: Target keyword
            client_vertical: Client's business vertical (e.g., "legal", "healthcare")
            client_vertical_keywords: Optional list of client's core topic keywords

        Returns:
            Tuple of (score 0-100, explanation string)
        """
        keyword_lower = keyword.lower()
        score = 0.0
        matches = []

        # Pattern matching against vertical keywords
        if client_vertical.lower() in VERTICAL_PATTERNS:
            patterns = VERTICAL_PATTERNS[client_vertical.lower()]

            for kw in patterns.get("keywords", []):
                if kw.lower() in keyword_lower:
                    score += 25
                    matches.append(kw)
                    break

            for mod in patterns.get("modifiers", []):
                if mod.lower() in keyword_lower:
                    score += 10
                    matches.append(mod)
                    break

        # Semantic similarity with client's vertical keywords
        if client_vertical_keywords:
            try:
                keyword_emb = self.semantic_service.model.encode(
                    keyword, normalize_embeddings=True
                )
                topic_embs = self.semantic_service.model.encode(
                    client_vertical_keywords, normalize_embeddings=True
                )
                similarities = np.dot(topic_embs, keyword_emb)
                max_sim = float(np.max(similarities))
                score += max_sim * 50
            except Exception as e:
                print(f"Error computing semantic intent fit: {e}")
                for topic in client_vertical_keywords:
                    if topic.lower() in keyword_lower or keyword_lower in topic.lower():
                        score += 15
                        break

        score = min(100, score)

        if score >= 75:
            explanation = f"Excellent vertical match - keyword directly relates to your {client_vertical} focus"
        elif score >= 50:
            explanation = f"Good vertical match - keyword is relevant to {client_vertical}"
        elif score >= 25:
            explanation = f"Partial vertical match - some relevance to {client_vertical}"
        else:
            explanation = f"Low vertical match - keyword may be outside your core {client_vertical} focus"

        if matches:
            explanation += f" (matched: {', '.join(matches[:3])})"

        return round(score, 1), explanation

    def compute_client_forecast(
        self,
        win_score: float,
        domain_fit: float,
        intent_fit: float,
        keyword_difficulty: Optional[float] = None,
        search_volume: Optional[int] = None
    ) -> Tuple[float, str, str]:
        """
        Compute overall Forecast % - chance this is a sensible, winnable term.

        Combines:
        - Win Score (model probability)
        - Domain Fit (authority match)
        - Intent Fit (vertical relevance)

        Args:
            win_score: Model's predicted probability (0-1)
            domain_fit: DomainFit score (0-100)
            intent_fit: IntentFit score (0-100)
            keyword_difficulty: Optional KD score (0-100)
            search_volume: Optional monthly search volume

        Returns:
            Tuple of (forecast_pct 0-100, tier, business_recommendation)
        """
        # Normalize win_score to 0-100
        win_score_pct = win_score * 100

        # Base forecast is weighted combination
        # Win Score: 40%, Domain Fit: 35%, Intent Fit: 25%
        base_forecast = (
            win_score_pct * 0.40 +
            domain_fit * 0.35 +
            intent_fit * 0.25
        )

        # Adjust for keyword difficulty if available
        if keyword_difficulty is not None:
            kd_adjustment = (50 - keyword_difficulty) * 0.1
            base_forecast += kd_adjustment

        # Volume bonus for high-volume keywords
        if search_volume is not None and search_volume > 1000:
            volume_bonus = min(5, search_volume / 2000)
            base_forecast += volume_bonus

        forecast_pct = max(0, min(100, base_forecast))

        # Determine tier
        if forecast_pct >= 70:
            tier = "HIGH_PRIORITY"
            recommendation = "Strong opportunity - prioritize this keyword for content creation"
        elif forecast_pct >= 50:
            tier = "GOOD_FIT"
            recommendation = "Good opportunity - include in content strategy with proper optimization"
        elif forecast_pct >= 35:
            tier = "CONSIDER"
            recommendation = "Moderate opportunity - consider if strategically important or low competition"
        elif forecast_pct >= 20:
            tier = "LONG_TERM"
            recommendation = "Challenging opportunity - better suited for long-term authority building"
        else:
            tier = "NOT_RECOMMENDED"
            recommendation = "Poor fit - focus efforts elsewhere unless strategically critical"

        # Add specific guidance based on component scores
        if domain_fit < 30 and intent_fit >= 60:
            recommendation += ". Note: Good topical fit but authority gap - consider link building."
        elif intent_fit < 30 and domain_fit >= 60:
            recommendation += ". Note: Strong authority but weak topical relevance - ensure content alignment."
        elif win_score < 0.3 and domain_fit >= 50 and intent_fit >= 50:
            recommendation += ". Note: Competitive SERP - differentiate with unique content angle."

        return round(forecast_pct, 1), tier, recommendation

    def analyze_keyword_with_client_profile(
        self,
        keyword: str,
        forecast_result: Dict,
        client_vertical: str,
        client_vertical_keywords: Optional[List[str]] = None
    ) -> Dict:
        """
        Enhance forecast result with client profile analysis.

        Args:
            keyword: Target keyword
            forecast_result: Result from forecast_keyword_rank_likelihood
            client_vertical: Client's business vertical
            client_vertical_keywords: Optional client topic keywords

        Returns:
            Enhanced result with domain_fit, intent_fit, and client_forecast
        """
        # Extract values from existing forecast
        my_dt = forecast_result.get("my_dt", 0) or 0
        my_refdoms = forecast_result.get("my_referring_domains", 0) or 0
        serp_median_dt = forecast_result.get("serp_median_dt", 0) or 0
        serp_median_refdoms = forecast_result.get("serp_median_refdoms", 0) or 0
        win_score = forecast_result.get("forecast_pct", {}).get("baseline_median_pct", 0) / 100.0

        # Compute DomainFit
        domain_fit_score, domain_fit_reason = self.compute_domain_fit(
            my_dt, my_refdoms, serp_median_dt, serp_median_refdoms
        )

        # Compute IntentFit
        intent_fit_score, intent_fit_reason = self.compute_intent_fit(
            keyword, client_vertical, client_vertical_keywords
        )

        # Compute Client Forecast
        client_forecast_pct, client_tier, client_recommendation = self.compute_client_forecast(
            win_score, domain_fit_score, intent_fit_score
        )

        # Enhance the result
        enhanced_result = {
            **forecast_result,
            "domain_fit": {
                "score": domain_fit_score,
                "explanation": domain_fit_reason
            },
            "intent_fit": {
                "score": intent_fit_score,
                "explanation": intent_fit_reason
            },
            "client_forecast": {
                "score": client_forecast_pct,
                "tier": client_tier,
                "recommendation": client_recommendation
            }
        }

        return enhanced_result


def get_forecast_service() -> ForecastService:
    """Get forecast service instance"""
    return ForecastService()
