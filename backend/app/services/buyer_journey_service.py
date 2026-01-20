"""
Buyer Journey Classification Service

Classifies keywords into buyer journey stages using regex-based pattern matching.
Based on the notebook: V2_Buyer_Journey_Keyword_Classification.ipynb
"""
import re
from typing import Tuple, Optional


# Buyer journey stage patterns (from notebook)
STAGES = {
    "Decision / Action": [
        r"\bbuy\b", r"\bpricing\b", r"\bdemo\b", r"\bconsultation\b",
        r"\bcontact\b", r"\bhire\b", r"\bsign up\b", r"\bget started\b",
        r"\bpurchase\b", r"\border\b", r"\bsubscribe\b", r"\bget quote\b",
        r"\bfree trial\b", r"\bbook\b", r"\bschedule\b"
    ],
    "Validation / Trust": [
        r"\breviews\b", r"\bcase study\b", r"\btestimonials\b",
        r"\blegit\b", r"\btrustworthy\b", r"\bworth it\b",
        r"\bis .* reliable\b", r"\bis .* accurate\b",
        r"\brating\b", r"\breputation\b", r"\bcredible\b"
    ],
    "Narrowing / Evaluation": [
        r"\bbest\b", r"\bfeatures\b", r"\bcost\b",
        r"\bpricing\b", r"\bfor .*?\b", r"\bvs\b",
        r"\bcompare\b", r"\btop\b", r"\brecommended\b",
        r"\baffordable\b", r"\bcheap\b", r"\bpremium\b"
    ],
    "Exploration / Consideration": [
        r"\balternatives\b", r"\bcomparison\b",
        r"\bpros and cons\b", r"\btools\b", r"\bplatforms\b",
        r"\boptions\b", r"\bchoices\b", r"\btypes of\b",
        r"\bsoftware\b", r"\bservices\b"
    ],
    "Trigger / Awareness": [
        r"\bwhat is\b", r"\bwhy\b", r"\bhow to\b",
        r"\bguide\b", r"\bideas\b", r"\bexamples\b",
        r"\btips\b", r"\bbenefits\b", r"\blearn\b",
        r"\bunderstand\b", r"\bexplain\b", r"\bdefinition\b"
    ]
}

# Stage order from bottom of funnel to top
STAGE_ORDER = [
    "Decision / Action",
    "Validation / Trust",
    "Narrowing / Evaluation",
    "Exploration / Consideration",
    "Trigger / Awareness"
]


def classify_buyer_journey(keyword: str) -> Tuple[str, float]:
    """
    Classify a keyword into a buyer journey stage.

    Args:
        keyword: The keyword to classify

    Returns:
        Tuple of (stage_name, confidence_score)
        - stage_name: One of the 5 journey stages
        - confidence_score: 0.0-1.0 indicating match strength
    """
    keyword_lower = keyword.lower().strip()

    # Track matches per stage
    stage_matches = {}

    for stage, patterns in STAGES.items():
        matches = 0
        for pattern in patterns:
            if re.search(pattern, keyword_lower, re.IGNORECASE):
                matches += 1
        if matches > 0:
            stage_matches[stage] = matches

    if not stage_matches:
        # No matches - default to Trigger/Awareness (top of funnel)
        return "Trigger / Awareness", 0.3

    # Find stage with most matches
    best_stage = max(stage_matches, key=stage_matches.get)
    best_count = stage_matches[best_stage]

    # Calculate confidence based on number of matches
    # 1 match = 0.5, 2 matches = 0.7, 3+ matches = 0.9
    if best_count >= 3:
        confidence = 0.9
    elif best_count == 2:
        confidence = 0.7
    else:
        confidence = 0.5

    return best_stage, confidence


def classify_keywords_batch(keywords: list[str]) -> list[dict]:
    """
    Classify a batch of keywords.

    Args:
        keywords: List of keywords to classify

    Returns:
        List of dicts with 'keyword', 'stage', and 'confidence' keys
    """
    results = []
    for kw in keywords:
        stage, confidence = classify_buyer_journey(kw)
        results.append({
            "keyword": kw,
            "buyer_journey_stage": stage,
            "journey_confidence": confidence
        })
    return results


def get_stage_color(stage: str) -> str:
    """
    Get the color code for a journey stage (for visualization).

    Args:
        stage: The journey stage name

    Returns:
        Hex color code
    """
    colors = {
        "Decision / Action": "#22c55e",      # Green
        "Validation / Trust": "#3b82f6",     # Blue
        "Narrowing / Evaluation": "#a855f7",  # Purple
        "Exploration / Consideration": "#f97316",  # Orange
        "Trigger / Awareness": "#6b7280"      # Gray
    }
    return colors.get(stage, "#6b7280")


def get_stage_order_index(stage: str) -> int:
    """
    Get the order index for a stage (0 = bottom of funnel).

    Args:
        stage: The journey stage name

    Returns:
        Integer index (0-4)
    """
    try:
        return STAGE_ORDER.index(stage)
    except ValueError:
        return 4  # Default to top of funnel
