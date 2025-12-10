"""
Request schemas for RankPredict v2 API
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class ClientProfile(BaseModel):
    """Client profile for forecast calculations"""
    vertical: str = Field(..., description="Business vertical (e.g., 'legal', 'healthcare', 'ecommerce')")
    vertical_keywords: Optional[List[str]] = Field(
        default=None,
        description="Client's core topic keywords for semantic matching"
    )


class CreateKeywordListRequest(BaseModel):
    """Request to create a new keyword list"""
    name: str = Field(..., description="Name of the keyword list")
    target_domain_url: str = Field(..., description="Target domain URL")
    keywords: List[str] = Field(..., description="List of keywords")
    client_profile: Optional[ClientProfile] = Field(
        default=None,
        description="Client profile for forecast calculations"
    )


class AddKeywordsRequest(BaseModel):
    """Request to add keywords to an existing list"""
    keywords: List[str] = Field(..., description="List of keywords to add")


class ScoreKeywordsRequest(BaseModel):
    """Request to score keywords in a list"""
    list_id: int = Field(..., description="Keyword list ID")


class UpdateKeywordRequest(BaseModel):
    """Request to update a keyword"""
    is_selected: Optional[bool] = None
    content_type: Optional[str] = Field(None, description="'new' or 'existing'")
    target_url: Optional[str] = None


class GenerateOutlineRequest(BaseModel):
    """Request to generate outline"""
    keyword_id: int = Field(..., description="Keyword ID")
    content_type: str = Field(..., description="'new' or 'existing'")
    existing_url: Optional[str] = Field(None, description="URL for existing content")
    target_intent: Optional[str] = Field(
        None,
        description="Desired page intent: 'informational', 'commercial', 'transactional', 'navigational'. If not set, uses SERP-detected intent."
    )


class LoginRequest(BaseModel):
    """Request for user login"""
    username: str
    password: str
