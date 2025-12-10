"""
SQLAlchemy database models for RankPredict v2
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    """User accounts with role-based access"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, default="user")  # "master", "admin", "user"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Master users can: manage all users, view all data, full access
    # Admin users can: manage regular users, view all data
    # Regular users can: view/edit their own data only


class KeywordList(Base):
    """Stores saved keyword lists"""
    __tablename__ = "keyword_lists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    target_domain_url = Column(String, nullable=False)
    # Client profile for forecast calculations
    client_vertical = Column(String, nullable=True)  # e.g., "legal", "healthcare"
    client_vertical_keywords = Column(JSON, nullable=True)  # List of core topic keywords
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    keywords = relationship("Keyword", back_populates="keyword_list", cascade="all, delete-orphan")


class Keyword(Base):
    """Individual keywords in a list"""
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True)
    keyword_list_id = Column(Integer, ForeignKey("keyword_lists.id"), nullable=False)
    keyword = Column(String, nullable=False, index=True)
    rankability_score = Column(Float, default=0.0)  # 0-1 probability score
    opportunity_tier = Column(String, default="LOW")  # HIGH, MEDIUM, LOW
    is_selected = Column(Boolean, default=False)
    content_type = Column(String, default="new")  # "new" or "existing"
    target_url = Column(String, nullable=True)  # URL for existing content
    # Persisted scoring data
    domain_fit = Column(Float, nullable=True)  # 0-100 score
    intent_fit = Column(Float, nullable=True)  # 0-100 score
    client_forecast = Column(Float, nullable=True)  # 0-100 weighted score
    forecast_tier = Column(String, nullable=True)  # HIGH_PRIORITY, GOOD_FIT, etc.
    scored_at = Column(DateTime(timezone=True), nullable=True)  # When scores were last computed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    keyword_list = relationship("KeywordList", back_populates="keywords")
    analyses = relationship("KeywordAnalysis", back_populates="keyword_obj", cascade="all, delete-orphan")
    outlines = relationship("Outline", back_populates="keyword", cascade="all, delete-orphan")


class KeywordAnalysis(Base):
    """Cached SERP analysis data to avoid redundant API calls"""
    __tablename__ = "keyword_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id"), nullable=False)
    keyword = Column(String, nullable=False, index=True)  # Denormalized for easier querying
    serp_data = Column(JSON)  # Full SERP results
    serp_medians = Column(JSON)  # Calculated medians
    semantic_scores = Column(JSON)  # Semantic similarity scores
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    keyword_obj = relationship("Keyword", back_populates="analyses", foreign_keys=[keyword_id])


class Outline(Base):
    """Generated content briefs for keywords"""
    __tablename__ = "outlines"

    id = Column(Integer, primary_key=True, index=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id"), nullable=False)
    # Brief metadata
    name = Column(String, nullable=True)  # User-friendly name for the brief
    content_type = Column(String, default="new")  # "new" or "existing"
    target_url = Column(String, nullable=True)  # For existing content
    target_intent = Column(String, nullable=True)  # User-selected intent override
    # Brief content (full JSON)
    brief_data = Column(JSON)  # Full OutlineResponse as JSON
    intent_analysis = Column(JSON)  # Intent type, content format, query variants
    outline_structure = Column(JSON)  # Dynamic outline structure (sections)
    serp_patterns = Column(JSON)  # SERP patterns identified
    serp_features = Column(JSON, nullable=True)  # SERP features (PAA, related, etc.)
    improvement_plan = Column(JSON, nullable=True)  # For existing content mode
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    keyword = relationship("Keyword", back_populates="outlines")

