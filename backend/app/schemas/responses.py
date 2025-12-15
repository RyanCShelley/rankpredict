"""
Response schemas for RankPredict v2 API
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class FitScore(BaseModel):
    """Fit score with explanation"""
    score: float = Field(..., description="Score 0-100")
    explanation: str = Field(..., description="Human-readable explanation")


class ClientForecast(BaseModel):
    """Client-specific forecast result"""
    score: float = Field(..., description="Forecast percentage 0-100")
    tier: str = Field(..., description="HIGH_PRIORITY, GOOD_FIT, CONSIDER, LONG_TERM, or NOT_RECOMMENDED")
    recommendation: str = Field(..., description="Business recommendation")


class KeywordResponse(BaseModel):
    """Keyword response model"""
    id: int
    keyword: str
    rankability_score: float = Field(..., description="Rankability score (0-1)")
    opportunity_tier: str = Field(..., description="T1_GO_NOW, T2_STRATEGIC, T3_LONG_GAME, or T4_NOT_WORTH_IT")
    forecast_pct: Optional[float] = Field(None, description="Forecast percentage (0-100)")
    tier_explanation: Optional[str] = Field(None, description="Explanation for tier classification")
    # Client profile fit scores
    domain_fit: Optional[FitScore] = Field(None, description="DomainFit score - authority match vs SERP")
    intent_fit: Optional[FitScore] = Field(None, description="IntentFit score - keyword relevance to vertical")
    client_forecast: Optional[ClientForecast] = Field(None, description="Client-specific forecast")
    is_selected: bool
    content_type: str = Field(..., description="'new' or 'existing'")
    target_url: Optional[str] = None
    created_at: datetime


class KeywordListResponse(BaseModel):
    """Keyword list response model"""
    id: int
    name: str
    target_domain_url: str
    keyword_count: int
    created_at: datetime
    updated_at: datetime


class ClientProfileResponse(BaseModel):
    """Client profile response"""
    vertical: str
    vertical_keywords: Optional[List[str]] = None


class KeywordListDetailResponse(BaseModel):
    """Detailed keyword list response with keywords"""
    id: int
    name: str
    target_domain_url: str
    client_profile: Optional[ClientProfileResponse] = None
    keywords: List[KeywordResponse]
    created_at: datetime
    updated_at: datetime


class ScoreKeywordsResponse(BaseModel):
    """Response after scoring keywords"""
    list_id: int
    keywords_scored: int
    keywords: List[KeywordResponse]


class OutlineSectionResponse(BaseModel):
    """Outline section response"""
    heading: str
    h3_subsections: List[str] = []
    topics: List[str] = []
    word_count_target: int = 0
    entities: List[str] = []
    semantic_focus: str = ""
    key_points: List[str] = []
    # For existing content optimization
    status: Optional[str] = None  # KEEP, MODIFY, ADD, REMOVE


class ContentAnnotation(BaseModel):
    """Content annotation for existing content improvements"""
    original_text: str
    improved_text: str
    reason: str
    priority: str = "medium"


class QuestionToAnswer(BaseModel):
    """Question that must be answered in the content"""
    question: str
    priority: str = "medium"
    format: str = "paragraph"
    placement: str = ""


class SERPFeaturesResponse(BaseModel):
    """SERP features extracted from search results"""
    people_also_ask: List[Dict[str, Any]] = []
    related_searches: List[str] = []
    related_questions: List[str] = []
    featured_snippet: Optional[Dict[str, Any]] = None
    knowledge_panel: Optional[Dict[str, Any]] = None
    serp_features_present: List[str] = []
    ads_present: bool = False
    local_pack: Optional[Dict[str, Any]] = None
    video_results: List[Dict[str, Any]] = []
    image_results: List[str] = []
    news_results: List[Dict[str, Any]] = []
    shopping_results: List[Dict[str, Any]] = []


class OutlineResponse(BaseModel):
    """Content brief / outline response model"""
    keyword: str
    intent_analysis: Dict[str, Any]
    serp_patterns: Dict[str, Any] = {}
    sections: List[OutlineSectionResponse]
    word_count_target: int
    topics: List[str] = []
    entities: List[str] = []
    structure_type: str
    structure_reasoning: Any = ""  # Can be string or list
    # New fields for enhanced brief
    title_recommendation: Optional[str] = None
    meta_description: Optional[str] = None
    content_strategy: Optional[Dict[str, Any]] = None
    search_intent: Optional[Dict[str, Any]] = None
    questions_to_answer: List[Dict[str, Any]] = []
    related_topics: List[str] = []
    serp_optimization: Optional[Dict[str, Any]] = None
    competitive_gaps: Optional[Dict[str, Any]] = None
    serp_features: Optional[SERPFeaturesResponse] = None
    # Existing content optimization fields
    optimization_mode: bool = False
    existing_url: Optional[str] = None
    content_annotations: List[ContentAnnotation] = []
    improvement_plan: Optional[Dict[str, Any]] = None


class ImprovementPlanResponse(BaseModel):
    """Improvement plan response for existing content"""
    keyword: str
    current_url: str
    gap_analysis: Dict[str, Any]
    improvements: List[Dict[str, Any]]
    missing_topics: List[str]
    priority_actions: List[Dict[str, Any]]


class TokenResponse(BaseModel):
    """Authentication token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int

