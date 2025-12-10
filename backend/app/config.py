"""
Configuration for RankPredict v2
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Model files directory
MODELS_DIR = BASE_DIR / "models"

# API Keys - Must be set via environment variables
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
SERANKING_KEY = os.getenv("SERANKING_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")

# LLM Provider preference: "claude" or "openai" (defaults to claude if available)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "claude")

# Model file paths
MODEL_FILE = os.getenv("MODEL_FILE", str(MODELS_DIR / "rf_model_top10_v2_20251208_2022.pkl"))
FEATURE_LIST_FILE = os.getenv("FEATURE_LIST_FILE", str(MODELS_DIR / "feature_cols_v2.json"))

# Semantic model configuration
SENTENCE_TRANSFORMERS_MODEL = os.getenv("SENTENCE_TRANSFORMERS_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# SERP Configuration
SERP_RESULTS_COUNT = int(os.getenv("SERP_RESULTS_COUNT", "25"))
TOP_N_POSITIONS = 10  # Top-10 positions for positive class

# Thresholds from notebook
HIGH_THRESH = 0.60
LOW_THRESH = 0.35

# CORS
cors_origins_str = os.getenv("ALLOWED_ORIGINS", "*")
if cors_origins_str.strip() == "*":
    ALLOWED_ORIGINS = ["*"]
else:
    ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]
    if not ALLOWED_ORIGINS:
        ALLOWED_ORIGINS = ["*"]

# Authentication
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-12345")
ALGORITHM = "HS256"
try:
    ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))
except (ValueError, TypeError):
    ACCESS_TOKEN_EXPIRE_HOURS = 24

