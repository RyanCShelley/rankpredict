"""
ML Model wrapper for rankability prediction
Uses rf_model_top10_v2_20251208_2022.pkl with 15 features
"""
import json
import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional
from app.config import MODEL_FILE, FEATURE_LIST_FILE, HIGH_THRESH, LOW_THRESH


def safe_ratio(num, den, default=1.0):
    """Avoid division by zero / NaN in ratio calculations (from notebook)"""
    try:
        if den is None or den == 0 or np.isnan(den):
            return default
        if num is None or np.isnan(num):
            return default
        return float(num) / float(den)
    except Exception:
        return default


def classify_opportunity(p: float, high_thresh: float = None, low_thresh: float = None) -> str:
    """Turn probability into HIGH / MEDIUM / LOW opportunity tiers (from notebook)"""
    high_thresh = high_thresh or HIGH_THRESH
    low_thresh = low_thresh or LOW_THRESH
    
    if p >= high_thresh:
        return "HIGH"
    if p >= low_thresh:
        return "MEDIUM"
    return "LOW"


class MLModel:
    """ML Model wrapper for rankability prediction"""
    
    def __init__(self):
        self.model = None
        self.feature_list = None
        self.loaded = False
    
    def load_model(self):
        """Load model and feature list"""
        if self.loaded:
            return
        
        # Load model
        model_path = Path(MODEL_FILE)
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {MODEL_FILE}")
        
        self.model = joblib.load(model_path)
        print(f"Loaded model from {MODEL_FILE}")
        
        # Load feature list
        feature_path = Path(FEATURE_LIST_FILE)
        if not feature_path.exists():
            raise FileNotFoundError(f"Feature list file not found: {FEATURE_LIST_FILE}")
        
        with open(feature_path, "r") as f:
            self.feature_list = json.load(f)
        
        print(f"Loaded {len(self.feature_list)} feature columns: {self.feature_list}")
        self.loaded = True
    
    def build_feature_vector(
        self,
        user_metrics: Dict[str, float],
        serp_medians: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Build feature vector with 15 features (from feature_cols_v2.json)
        Based on notebook logic: gap and ratio features vs Top 10 medians
        """
        if not self.loaded:
            self.load_model()
        
        # Calculate gaps and ratios (from notebook)
        top10_dt = serp_medians.get("dt", 1)
        top10_refdoms = serp_medians.get("referring_domains", 1)
        top10_wc = serp_medians.get("word_count", 1)
        top10_sent = serp_medians.get("sentence_count", 1)
        top10_awps = serp_medians.get("average_words_per_sentence", 1)
        top10_flesch = serp_medians.get("flesch_reading_ease_score", 1)
        top10_sem = serp_medians.get("semantic_topic_score", 1)
        top10_il = serp_medians.get("internal_links", 1)
        top10_schema_total = serp_medians.get("total_schema_types", 1)
        top10_schema_unique = serp_medians.get("unique_schema_types", 1)
        top10_rich = serp_medians.get("rich_result_features", 1)
        
        user_dt = user_metrics.get("domain_trust", 0)
        user_refdoms = user_metrics.get("referring_domains", 0)
        user_wc = user_metrics.get("word_count", 0)
        user_sent = user_metrics.get("sentence_count", 0)
        user_awps = user_metrics.get("average_words_per_sentence", 0)
        user_flesch = user_metrics.get("flesch_reading_ease_score", 0)
        user_sem = user_metrics.get("semantic_topic_score", 0)
        user_il = user_metrics.get("internal_links", 0)
        user_schema_total = user_metrics.get("total_schema_types", 0)
        user_schema_unique = user_metrics.get("unique_schema_types", 0)
        user_rich = user_metrics.get("rich_result_features", 0)
        
        # Build feature vector (15 features from feature_cols_v2.json)
        features = {}
        
        # 1. dt_gap
        features["dt_gap"] = (user_dt - top10_dt) / top10_dt if top10_dt > 0 else 0.0
        # 2. dt_ratio
        features["dt_ratio"] = safe_ratio(user_dt, top10_dt)
        # 3. refdoms_gap
        features["refdoms_gap"] = (user_refdoms - top10_refdoms) / top10_refdoms if top10_refdoms > 0 else 0.0
        # 4. refdoms_ratio
        features["refdoms_ratio"] = safe_ratio(user_refdoms, top10_refdoms)
        # 5. wc_gap
        features["wc_gap"] = (user_wc - top10_wc) / top10_wc if top10_wc > 0 else 0.0
        # 6. wc_ratio
        features["wc_ratio"] = safe_ratio(user_wc, top10_wc)
        # 7. sent_count_gap
        features["sent_count_gap"] = (user_sent - top10_sent) / top10_sent if top10_sent > 0 else 0.0
        # 8. awps_gap
        features["awps_gap"] = (user_awps - top10_awps) / top10_awps if top10_awps > 0 else 0.0
        # 9. flesch_gap
        features["flesch_gap"] = (user_flesch - top10_flesch) / top10_flesch if top10_flesch > 0 else 0.0
        # 10. semantic_gap
        features["semantic_gap"] = (user_sem - top10_sem) / top10_sem if top10_sem > 0 else 0.0
        # 11. semantic_ratio
        features["semantic_ratio"] = safe_ratio(user_sem, top10_sem)
        # 12. internal_links_gap
        features["internal_links_gap"] = (user_il - top10_il) / top10_il if top10_il > 0 else 0.0
        # 13. schema_total_gap
        features["schema_total_gap"] = (user_schema_total - top10_schema_total) / top10_schema_total if top10_schema_total > 0 else 0.0
        # 14. schema_unique_gap
        features["schema_unique_gap"] = (user_schema_unique - top10_schema_unique) / top10_schema_unique if top10_schema_unique > 0 else 0.0
        # 15. rich_features_gap
        features["rich_features_gap"] = (user_rich - top10_rich) / top10_rich if top10_rich > 0 else 0.0
        
        return features
    
    def predict_rankability(
        self,
        user_metrics: Dict[str, float],
        serp_medians: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Predict rankability score using ML model
        
        Args:
            user_metrics: User's page metrics
            serp_medians: SERP median values (Top 10)
            
        Returns:
            Dictionary with rankability_score (0-1) and opportunity_tier (HIGH/MEDIUM/LOW)
        """
        if not self.loaded:
            self.load_model()
        
        # Build feature vector
        feature_vector = self.build_feature_vector(user_metrics, serp_medians)
        
        # Ensure feature order matches model exactly
        feature_array = []
        for feature_name in self.feature_list:
            feature_array.append(feature_vector.get(feature_name, 0.0))
        
        # Create DataFrame with exact feature order
        X = pd.DataFrame([feature_array], columns=self.feature_list)
        X = X.astype(float)
        
        # Predict probability
        try:
            probability = self.model.predict_proba(X)[0][1]  # Probability of positive class (Top-10)
            probability = float(probability)
        except Exception as e:
            print(f"ERROR in predict_proba: {e}")
            raise ValueError(f"Model prediction failed: {str(e)}") from e
        
        # Classify opportunity tier
        opportunity_tier = classify_opportunity(probability)
        
        return {
            "rankability_score": probability,
            "opportunity_tier": opportunity_tier
        }


def get_model() -> MLModel:
    """Get ML model instance (singleton)"""
    if not hasattr(get_model, "_instance"):
        get_model._instance = MLModel()
    return get_model._instance

