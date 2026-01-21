"""
Topic Classification Service

Classifies keywords into user-defined topics using semantic similarity.
Uses sentence-transformers for embeddings and cosine similarity for matching.
Based on the notebook: V2_Buyer_Journey_Keyword_Classification.ipynb
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


# Default similarity threshold (from notebook)
DEFAULT_SIMILARITY_THRESHOLD = 0.65

# Singleton model instance to avoid reloading
_model: Optional[SentenceTransformer] = None


def get_model() -> SentenceTransformer:
    """Get or initialize the sentence transformer model."""
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def create_topic_embeddings(topics: List[Dict]) -> Dict[str, np.ndarray]:
    """
    Create embeddings for topic keywords.

    Args:
        topics: List of dicts with 'name' and 'keywords' keys
                e.g., [{"name": "RV Mattress", "keywords": ["rv mattress", "custom rv mattress"]}]

    Returns:
        Dict mapping topic name to array of keyword embeddings
    """
    model = get_model()
    topic_embeddings = {}

    for topic in topics:
        topic_name = topic["name"]
        keywords = topic["keywords"]
        if keywords:
            embeddings = model.encode(keywords, normalize_embeddings=True)
            topic_embeddings[topic_name] = embeddings

    return topic_embeddings


def assign_topic(
    keyword: str,
    topic_embeddings: Dict[str, np.ndarray],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD
) -> Tuple[Optional[str], float]:
    """
    Assign a keyword to the best-matching topic.

    Args:
        keyword: The keyword to classify
        topic_embeddings: Dict of topic name -> embeddings array
        threshold: Minimum similarity score to assign (default 0.65)

    Returns:
        Tuple of (topic_name, similarity_score)
        - topic_name: Best matching topic or None if below threshold
        - similarity_score: Cosine similarity (0-1)
    """
    model = get_model()

    # Encode the keyword
    keyword_embed = model.encode([keyword], normalize_embeddings=True)[0]

    best_topic = None
    best_score = 0.0

    for topic_name, embeds in topic_embeddings.items():
        # Calculate similarity with all topic keywords
        sims = cosine_similarity(
            keyword_embed.reshape(1, -1),
            embeds
        )[0]

        max_sim = float(sims.max())

        if max_sim > best_score:
            best_score = max_sim
            best_topic = topic_name

    if best_score >= threshold:
        return best_topic, round(best_score, 3)

    return None, round(best_score, 3)


def classify_keywords_batch(
    keywords: List[str],
    topics: List[Dict],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    batch_size: int = 500
) -> List[Dict]:
    """
    Classify a batch of keywords against topics.

    Args:
        keywords: List of keywords to classify
        topics: List of topic dicts with 'name' and 'keywords'
        threshold: Minimum similarity threshold
        batch_size: Process keywords in batches of this size

    Returns:
        List of dicts with classification results:
        - keyword: Original keyword
        - assigned_topic: Matched topic name or None
        - topic_similarity: Similarity score
    """
    if not topics:
        return [{"keyword": kw, "assigned_topic": None, "topic_similarity": 0.0} for kw in keywords]

    # Create topic embeddings once
    topic_embeddings = create_topic_embeddings(topics)

    if not topic_embeddings:
        return [{"keyword": kw, "assigned_topic": None, "topic_similarity": 0.0} for kw in keywords]

    model = get_model()
    results = []

    # Process in batches to manage memory
    for i in range(0, len(keywords), batch_size):
        batch = keywords[i:i + batch_size]
        print(f"  Processing batch {i // batch_size + 1} ({len(batch)} keywords)...")

        # Encode batch of keywords at once (much faster)
        keyword_embeddings = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)

        for j, kw in enumerate(batch):
            keyword_embed = keyword_embeddings[j]
            best_topic = None
            best_score = 0.0

            for topic_name, embeds in topic_embeddings.items():
                sims = cosine_similarity(
                    keyword_embed.reshape(1, -1),
                    embeds
                )[0]
                max_sim = float(sims.max())

                if max_sim > best_score:
                    best_score = max_sim
                    best_topic = topic_name

            if best_score >= threshold:
                results.append({
                    "keyword": kw,
                    "assigned_topic": best_topic,
                    "topic_similarity": round(best_score, 3)
                })
            else:
                results.append({
                    "keyword": kw,
                    "assigned_topic": None,
                    "topic_similarity": round(best_score, 3)
                })

        # Free memory after each batch
        del keyword_embeddings

    return results


def filter_by_topic(
    classified_keywords: List[Dict],
    topic_name: Optional[str] = None,
    include_unassigned: bool = False
) -> List[Dict]:
    """
    Filter classified keywords by topic.

    Args:
        classified_keywords: Results from classify_keywords_batch
        topic_name: Filter to this topic only (None = all assigned)
        include_unassigned: Include keywords with no assigned topic

    Returns:
        Filtered list of keyword dicts
    """
    results = []
    for kw in classified_keywords:
        if topic_name:
            if kw["assigned_topic"] == topic_name:
                results.append(kw)
        elif kw["assigned_topic"] is not None:
            results.append(kw)
        elif include_unassigned:
            results.append(kw)

    return results
