"""
Strategy Dashboard API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.database import get_db, SessionLocal
from app.models.database import KeywordList, Keyword, KeywordAnalysis, StrategyProject
from app.schemas.requests import CreateKeywordListRequest, AddKeywordsRequest, ScoreKeywordsRequest, UpdateKeywordRequest, ScoreSpecificKeywordsRequest, UpdateKeywordListRequest
from app.schemas.responses import (
    KeywordListResponse, KeywordListDetailResponse, KeywordResponse, ScoreKeywordsResponse,
    FitScore, ClientForecast, ClientProfileResponse, ProjectInfoResponse
)
from app.services.serp_service import get_serp_service, strip_html_for_storage
from app.services.semantic_service import get_semantic_service
from app.models.ml_model import get_model
from app.services.forecast_service import get_forecast_service
import json
import queue
import threading

router = APIRouter()


def _build_project_info(keyword_list, db) -> Optional[ProjectInfoResponse]:
    """Build ProjectInfoResponse if list is linked to a project."""
    if not keyword_list.project_id:
        return None
    project = db.query(StrategyProject).filter(StrategyProject.id == keyword_list.project_id).first()
    if not project:
        return None
    return ProjectInfoResponse(
        id=project.id,
        name=project.name,
        domain=project.domain,
        persona=project.persona,
        core_topics=project.core_topics
    )


@router.post("/lists", response_model=KeywordListDetailResponse)
def create_keyword_list(
    request: CreateKeywordListRequest,
    db: Session = Depends(get_db)
):
    """Create a new keyword list"""
    try:
        # Create keyword list with optional client profile
        keyword_list = KeywordList(
            name=request.name,
            target_domain_url=request.target_domain_url,
            client_vertical=request.client_profile.vertical if request.client_profile else None,
            client_vertical_keywords=request.client_profile.vertical_keywords if request.client_profile else None
        )
        db.add(keyword_list)
        db.flush()  # Get the ID

        # Create keywords
        keywords = []
        for kw in request.keywords:
            keyword = Keyword(
                keyword_list_id=keyword_list.id,
                keyword=kw.strip(),
                rankability_score=0.0,
                opportunity_tier="LOW",
                is_selected=False,
                content_type="new"
            )
            db.add(keyword)
            keywords.append(keyword)

        db.commit()
        db.refresh(keyword_list)

        # Build response
        keyword_responses = [
            KeywordResponse(
                id=k.id,
                keyword=k.keyword,
                volume=k.volume,
                rankability_score=k.rankability_score,
                opportunity_tier=k.opportunity_tier,
                forecast_pct=None,
                tier_explanation=None,
                domain_fit=None,
                intent_fit=None,
                client_forecast=None,
                is_selected=k.is_selected,
                action_status=k.action_status or "none",
                content_type=k.content_type,
                target_url=k.target_url,
                has_outline=len(k.outlines) > 0,
                created_at=k.created_at
            )
            for k in keywords
        ]

        # Build client profile response
        client_profile_response = None
        if keyword_list.client_vertical:
            client_profile_response = ClientProfileResponse(
                vertical=keyword_list.client_vertical,
                vertical_keywords=keyword_list.client_vertical_keywords
            )

        return KeywordListDetailResponse(
            id=keyword_list.id,
            name=keyword_list.name,
            target_domain_url=keyword_list.target_domain_url,
            client_profile=client_profile_response,
            project=_build_project_info(keyword_list, db),
            keywords=keyword_responses,
            created_at=keyword_list.created_at,
            updated_at=keyword_list.updated_at
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating keyword list: {str(e)}")


@router.get("/lists", response_model=List[KeywordListResponse])
def get_keyword_lists(db: Session = Depends(get_db)):
    """Get all keyword lists"""
    lists = db.query(KeywordList).order_by(KeywordList.created_at.desc()).all()
    
    return [
        KeywordListResponse(
            id=l.id,
            name=l.name,
            target_domain_url=l.target_domain_url,
            keyword_count=len(l.keywords),
            created_at=l.created_at,
            updated_at=l.updated_at
        )
        for l in lists
    ]


@router.get("/lists/{list_id}", response_model=KeywordListDetailResponse)
def get_keyword_list(list_id: int, db: Session = Depends(get_db)):
    """Get a specific keyword list with keywords including persisted scores"""
    keyword_list = db.query(KeywordList).filter(KeywordList.id == list_id).first()
    if not keyword_list:
        raise HTTPException(status_code=404, detail="Keyword list not found")

    keyword_responses = []
    for k in keyword_list.keywords:
        # Build fit score responses from persisted data
        domain_fit_response = None
        intent_fit_response = None
        client_forecast_response = None

        if k.domain_fit is not None:
            domain_fit_response = FitScore(
                score=k.domain_fit,
                explanation="Domain authority fit score"
            )
        if k.intent_fit is not None:
            intent_fit_response = FitScore(
                score=k.intent_fit,
                explanation="Intent alignment score"
            )
        if k.client_forecast is not None:
            client_forecast_response = ClientForecast(
                score=k.client_forecast,
                tier=k.forecast_tier or "UNKNOWN",
                recommendation=f"Based on {k.forecast_tier} tier" if k.forecast_tier else ""
            )

        keyword_responses.append(KeywordResponse(
            id=k.id,
            keyword=k.keyword,
            volume=k.volume,
            rankability_score=k.rankability_score,
            opportunity_tier=k.opportunity_tier,
            forecast_pct=k.rankability_score * 100 if k.rankability_score else None,
            tier_explanation=None,
            domain_fit=domain_fit_response,
            intent_fit=intent_fit_response,
            client_forecast=client_forecast_response,
            is_selected=k.is_selected,
            action_status=k.action_status or "none",
            content_type=k.content_type,
            target_url=k.target_url,
            has_outline=len(k.outlines) > 0,
            created_at=k.created_at
        ))

    # Build client profile response
    client_profile_response = None
    if keyword_list.client_vertical:
        client_profile_response = ClientProfileResponse(
            vertical=keyword_list.client_vertical,
            vertical_keywords=keyword_list.client_vertical_keywords
        )

    return KeywordListDetailResponse(
        id=keyword_list.id,
        name=keyword_list.name,
        target_domain_url=keyword_list.target_domain_url,
        client_profile=client_profile_response,
        project=_build_project_info(keyword_list, db),
        keywords=keyword_responses,
        created_at=keyword_list.created_at,
        updated_at=keyword_list.updated_at
    )


@router.post("/lists/{list_id}/score", response_model=ScoreKeywordsResponse)
def score_keywords(
    list_id: int,
    force_rescore: bool = Query(False, description="Force re-scoring of all keywords"),
    db: Session = Depends(get_db)
):
    """
    Score keywords in a list using ML model.
    By default, only scores keywords that haven't been scored yet.
    Use force_rescore=true to re-score all keywords.
    """
    keyword_list = db.query(KeywordList).filter(KeywordList.id == list_id).first()
    if not keyword_list:
        raise HTTPException(status_code=404, detail="Keyword list not found")

    serp_service = get_serp_service()
    semantic_service = get_semantic_service()
    forecast_service = get_forecast_service()

    keywords_scored = 0
    keywords_skipped = 0
    keyword_responses = []

    for keyword_obj in keyword_list.keywords:
        # Skip already-scored keywords unless force_rescore
        if keyword_obj.scored_at and not force_rescore:
            # Return existing scores
            domain_fit_response = None
            intent_fit_response = None
            client_forecast_response = None

            if keyword_obj.domain_fit is not None:
                domain_fit_response = FitScore(
                    score=keyword_obj.domain_fit,
                    explanation=f"Domain authority fit score"
                )
            if keyword_obj.intent_fit is not None:
                intent_fit_response = FitScore(
                    score=keyword_obj.intent_fit,
                    explanation=f"Intent alignment score"
                )
            if keyword_obj.client_forecast is not None:
                client_forecast_response = ClientForecast(
                    score=keyword_obj.client_forecast,
                    tier=keyword_obj.forecast_tier or "UNKNOWN",
                    recommendation=f"Based on {keyword_obj.forecast_tier} tier"
                )

            keyword_responses.append(KeywordResponse(
                id=keyword_obj.id,
                keyword=keyword_obj.keyword,
                volume=keyword_obj.volume,
                rankability_score=keyword_obj.rankability_score,
                opportunity_tier=keyword_obj.opportunity_tier,
                forecast_pct=keyword_obj.rankability_score * 100 if keyword_obj.rankability_score else None,
                tier_explanation=None,
                domain_fit=domain_fit_response,
                intent_fit=intent_fit_response,
                client_forecast=client_forecast_response,
                is_selected=keyword_obj.is_selected,
                action_status=keyword_obj.action_status or "none",
                content_type=keyword_obj.content_type,
                target_url=keyword_obj.target_url,
                has_outline=len(keyword_obj.outlines) > 0,
                created_at=keyword_obj.created_at
            ))
            keywords_skipped += 1
            continue
        try:
            keyword = keyword_obj.keyword
            
            # Check if we have cached analysis
            cached_analysis = db.query(KeywordAnalysis).filter(
                KeywordAnalysis.keyword == keyword
            ).order_by(KeywordAnalysis.analyzed_at.desc()).first()
            
            if cached_analysis:
                # Use cached data
                serp_medians = cached_analysis.serp_medians or {}
                enriched_results = cached_analysis.serp_data.get("enriched_results", [])
                # Fix for cached data with buggy flesch/word_count values
                if serp_medians.get("flesch_reading_ease_score", 0) < 10:
                    serp_medians["flesch_reading_ease_score"] = 55.0
                if serp_medians.get("word_count", 0) < 100:
                    serp_medians["word_count"] = 1500.0
            else:
                # Fetch fresh SERP data (limit to top 10 for speed)
                serp_data = serp_service.fetch_serp_data(keyword, num_results=10)
                organic_results = serp_service.extract_organic_results(serp_data)
                # Only enrich top 10 results to speed up
                enriched_results = serp_service.enrich_serp_results(organic_results, limit=10)
                
                # Compute semantic scores (only for top 10)
                semantic_scores = semantic_service.compute_semantic_scores_for_serp(
                    enriched_results,
                    query=keyword,
                    html_column="raw_html"
                )
                
                # Add semantic scores to results
                for i, score in enumerate(semantic_scores):
                    if i < len(enriched_results):
                        enriched_results[i]["semantic_topic_score"] = score
                
                # Calculate medians
                serp_medians = serp_service.calculate_serp_medians(enriched_results)
                serp_medians["semantic_topic_score"] = sum(semantic_scores[:10]) / len(semantic_scores[:10]) if semantic_scores else 0.7
                
                # Cache analysis (strip raw_html to prevent OOM on large inserts)
                analysis = KeywordAnalysis(
                    keyword_id=keyword_obj.id,
                    keyword=keyword,
                    serp_data={"enriched_results": strip_html_for_storage(enriched_results)},
                    serp_medians=serp_medians,
                    semantic_scores=semantic_scores
                )
                db.add(analysis)
            
            # Use forecast approach: build synthetic profiles from Top 10
            # Get target domain URL from keyword list
            target_domain_url = keyword_list.target_domain_url
            
            forecast = forecast_service.forecast_keyword_rank_likelihood(
                keyword=keyword,
                enriched_results=enriched_results,
                serp_medians=serp_medians,
                target_domain_url=target_domain_url
            )
            
            # Use baseline_median_pct as the rankability score
            rankability_score = forecast["forecast_pct"]["baseline_median_pct"] / 100.0  # Convert to 0-1

            # Use the new tier system from forecast
            opportunity_tier = forecast.get("forecast_tiers", {}).get("baseline_median_tier", "T4_NOT_WORTH_IT")

            # Update keyword
            keyword_obj.rankability_score = rankability_score
            keyword_obj.opportunity_tier = opportunity_tier

            keywords_scored += 1

            # Compute client profile fit scores if client profile is set
            domain_fit_response = None
            intent_fit_response = None
            client_forecast_response = None

            if keyword_list.client_vertical:
                # Enhance forecast with client profile analysis
                enhanced_forecast = forecast_service.analyze_keyword_with_client_profile(
                    keyword=keyword,
                    forecast_result=forecast,
                    client_vertical=keyword_list.client_vertical,
                    client_vertical_keywords=keyword_list.client_vertical_keywords
                )

                # Extract fit scores
                if "domain_fit" in enhanced_forecast:
                    domain_fit_response = FitScore(
                        score=enhanced_forecast["domain_fit"]["score"],
                        explanation=enhanced_forecast["domain_fit"]["explanation"]
                    )

                if "intent_fit" in enhanced_forecast:
                    intent_fit_response = FitScore(
                        score=enhanced_forecast["intent_fit"]["score"],
                        explanation=enhanced_forecast["intent_fit"]["explanation"]
                    )

                if "client_forecast" in enhanced_forecast:
                    client_forecast_response = ClientForecast(
                        score=enhanced_forecast["client_forecast"]["score"],
                        tier=enhanced_forecast["client_forecast"]["tier"],
                        recommendation=enhanced_forecast["client_forecast"]["recommendation"]
                    )

                # Persist fit scores to database
                keyword_obj.domain_fit = enhanced_forecast.get("domain_fit", {}).get("score")
                keyword_obj.intent_fit = enhanced_forecast.get("intent_fit", {}).get("score")
                keyword_obj.client_forecast = enhanced_forecast.get("client_forecast", {}).get("score")
                keyword_obj.forecast_tier = enhanced_forecast.get("client_forecast", {}).get("tier")

            # Mark as scored
            keyword_obj.scored_at = datetime.utcnow()

            keyword_responses.append(KeywordResponse(
                id=keyword_obj.id,
                keyword=keyword_obj.keyword,
                volume=keyword_obj.volume,
                rankability_score=keyword_obj.rankability_score,
                opportunity_tier=keyword_obj.opportunity_tier,
                forecast_pct=forecast.get("forecast_pct", {}).get("baseline_median_pct"),
                tier_explanation=forecast.get("tier_explanation"),
                domain_fit=domain_fit_response,
                intent_fit=intent_fit_response,
                client_forecast=client_forecast_response,
                is_selected=keyword_obj.is_selected,
                action_status=keyword_obj.action_status or "none",
                content_type=keyword_obj.content_type,
                target_url=keyword_obj.target_url,
                has_outline=len(keyword_obj.outlines) > 0,
                created_at=keyword_obj.created_at
            ))
        except Exception as e:
            print(f"Error scoring keyword '{keyword_obj.keyword}': {e}")
            continue
    
    db.commit()
    
    return ScoreKeywordsResponse(
        list_id=list_id,
        keywords_scored=keywords_scored,
        keywords=keyword_responses
    )


@router.patch("/keywords/{keyword_id}", response_model=KeywordResponse)
def update_keyword(
    keyword_id: int,
    request: UpdateKeywordRequest,
    db: Session = Depends(get_db)
):
    """Update keyword selection and content type"""
    keyword = db.query(Keyword).filter(Keyword.id == keyword_id).first()
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")
    
    if request.is_selected is not None:
        keyword.is_selected = request.is_selected
    if request.action_status is not None:
        keyword.action_status = request.action_status
    if request.content_type is not None:
        keyword.content_type = request.content_type
    if request.target_url is not None:
        keyword.target_url = request.target_url

    db.commit()
    db.refresh(keyword)

    return KeywordResponse(
        id=keyword.id,
        keyword=keyword.keyword,
        volume=keyword.volume,
        rankability_score=keyword.rankability_score,
        opportunity_tier=keyword.opportunity_tier,
        forecast_pct=None,
        tier_explanation=None,
        domain_fit=None,
        intent_fit=None,
        client_forecast=None,
        is_selected=keyword.is_selected,
        action_status=keyword.action_status or "none",
        content_type=keyword.content_type,
        target_url=keyword.target_url,
        has_outline=len(keyword.outlines) > 0,
        created_at=keyword.created_at
    )


@router.post("/lists/{list_id}/keywords", response_model=KeywordListDetailResponse)
def add_keywords_to_list(
    list_id: int,
    request: AddKeywordsRequest,
    db: Session = Depends(get_db)
):
    """Add keywords to an existing list"""
    keyword_list = db.query(KeywordList).filter(KeywordList.id == list_id).first()
    if not keyword_list:
        raise HTTPException(status_code=404, detail="Keyword list not found")
    
    try:
        # Create new keywords
        new_keywords = []
        for kw in request.keywords:
            # Check if keyword already exists in this list
            existing = db.query(Keyword).filter(
                Keyword.keyword_list_id == list_id,
                Keyword.keyword == kw.strip()
            ).first()
            
            if not existing:
                keyword = Keyword(
                    keyword_list_id=keyword_list.id,
                    keyword=kw.strip(),
                    rankability_score=0.0,
                    opportunity_tier="LOW",
                    is_selected=False,
                    content_type="new"
                )
                db.add(keyword)
                new_keywords.append(keyword)
        
        db.commit()
        
        # Reload the list to return updated data
        db.refresh(keyword_list)
        
        keyword_responses = [
            KeywordResponse(
                id=k.id,
                keyword=k.keyword,
                volume=k.volume,
                rankability_score=k.rankability_score,
                opportunity_tier=k.opportunity_tier,
                forecast_pct=None,
                tier_explanation=None,
                domain_fit=None,
                intent_fit=None,
                client_forecast=None,
                is_selected=k.is_selected,
                action_status=k.action_status or "none",
                content_type=k.content_type,
                target_url=k.target_url,
                has_outline=len(k.outlines) > 0,
                created_at=k.created_at
            )
            for k in keyword_list.keywords
        ]

        # Build client profile response
        client_profile_response = None
        if keyword_list.client_vertical:
            client_profile_response = ClientProfileResponse(
                vertical=keyword_list.client_vertical,
                vertical_keywords=keyword_list.client_vertical_keywords
            )

        return KeywordListDetailResponse(
            id=keyword_list.id,
            name=keyword_list.name,
            target_domain_url=keyword_list.target_domain_url,
            client_profile=client_profile_response,
            project=_build_project_info(keyword_list, db),
            keywords=keyword_responses,
            created_at=keyword_list.created_at,
            updated_at=keyword_list.updated_at
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error adding keywords: {str(e)}")


@router.patch("/lists/{list_id}")
def update_keyword_list(
    list_id: int,
    request: UpdateKeywordListRequest,
    db: Session = Depends(get_db)
):
    """Update keyword list settings (name, client profile)"""
    keyword_list = db.query(KeywordList).filter(KeywordList.id == list_id).first()
    if not keyword_list:
        raise HTTPException(status_code=404, detail="Keyword list not found")

    if request.name is not None:
        keyword_list.name = request.name
    if request.client_vertical is not None:
        keyword_list.client_vertical = request.client_vertical
    if request.client_vertical_keywords is not None:
        keyword_list.client_vertical_keywords = request.client_vertical_keywords

    keyword_list.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(keyword_list)

    # Build client profile response
    client_profile_response = None
    if keyword_list.client_vertical:
        client_profile_response = ClientProfileResponse(
            vertical=keyword_list.client_vertical,
            vertical_keywords=keyword_list.client_vertical_keywords
        )

    return {
        "id": keyword_list.id,
        "name": keyword_list.name,
        "target_domain_url": keyword_list.target_domain_url,
        "client_profile": client_profile_response,
        "updated_at": keyword_list.updated_at
    }


@router.post("/lists/{list_id}/score-selected")
def score_selected_keywords(
    list_id: int,
    request: ScoreSpecificKeywordsRequest,
    db: Session = Depends(get_db)
):
    """Score specific keywords by ID, streaming progress via SSE."""
    keyword_list = db.query(KeywordList).filter(KeywordList.id == list_id).first()
    if not keyword_list:
        raise HTTPException(status_code=404, detail="Keyword list not found")

    # Get only the keywords that were requested
    keywords_to_score = db.query(Keyword).filter(
        Keyword.id.in_(request.keyword_ids),
        Keyword.keyword_list_id == list_id
    ).all()

    total = len(keywords_to_score)

    # Collect IDs to re-query in the worker thread's own DB session
    keyword_ids_to_score = [kw.id for kw in keywords_to_score]
    list_id_for_worker = keyword_list.id

    # Use a queue + background thread so we can send heartbeats while scoring
    event_queue = queue.Queue()
    HEARTBEAT_INTERVAL = 15  # seconds between keepalive pings

    def scoring_worker():
        """Run scoring in a background thread with its own DB session."""
        thread_db = SessionLocal()
        try:
            serp_service = get_serp_service()
            semantic_service = get_semantic_service()
            forecast_service = get_forecast_service()

            thread_keyword_list = thread_db.query(KeywordList).filter(KeywordList.id == list_id_for_worker).first()
            thread_keywords = thread_db.query(Keyword).filter(Keyword.id.in_(keyword_ids_to_score)).all()
            # Preserve original ordering
            id_order = {kid: i for i, kid in enumerate(keyword_ids_to_score)}
            thread_keywords.sort(key=lambda kw: id_order.get(kw.id, 0))

            keywords_scored = 0

            for idx, keyword_obj in enumerate(thread_keywords):
                # Send progress event
                event_queue.put(f"data: {json.dumps({'type': 'progress', 'current': idx + 1, 'total': total, 'keyword': keyword_obj.keyword})}\n\n")

                try:
                    keyword = keyword_obj.keyword

                    # Check if we have cached analysis
                    cached_analysis = thread_db.query(KeywordAnalysis).filter(
                        KeywordAnalysis.keyword == keyword
                    ).order_by(KeywordAnalysis.analyzed_at.desc()).first()

                    if cached_analysis:
                        serp_medians = cached_analysis.serp_medians or {}
                        enriched_results = cached_analysis.serp_data.get("enriched_results", [])
                        if serp_medians.get("flesch_reading_ease_score", 0) < 10:
                            serp_medians["flesch_reading_ease_score"] = 55.0
                        if serp_medians.get("word_count", 0) < 100:
                            serp_medians["word_count"] = 1500.0
                    else:
                        serp_data = serp_service.fetch_serp_data(keyword, num_results=10)
                        organic_results = serp_service.extract_organic_results(serp_data)
                        enriched_results = serp_service.enrich_serp_results(organic_results, limit=10)

                        semantic_scores = semantic_service.compute_semantic_scores_for_serp(
                            enriched_results,
                            query=keyword,
                            html_column="raw_html"
                        )

                        for i, score in enumerate(semantic_scores):
                            if i < len(enriched_results):
                                enriched_results[i]["semantic_topic_score"] = score

                        serp_medians = serp_service.calculate_serp_medians(enriched_results)
                        serp_medians["semantic_topic_score"] = sum(semantic_scores[:10]) / len(semantic_scores[:10]) if semantic_scores else 0.7

                        analysis = KeywordAnalysis(
                            keyword_id=keyword_obj.id,
                            keyword=keyword,
                            serp_data={"enriched_results": strip_html_for_storage(enriched_results)},
                            serp_medians=serp_medians,
                            semantic_scores=semantic_scores
                        )
                        thread_db.add(analysis)

                    target_domain_url = thread_keyword_list.target_domain_url

                    forecast = forecast_service.forecast_keyword_rank_likelihood(
                        keyword=keyword,
                        enriched_results=enriched_results,
                        serp_medians=serp_medians,
                        target_domain_url=target_domain_url
                    )

                    rankability_score = forecast["forecast_pct"]["baseline_median_pct"] / 100.0
                    opportunity_tier = forecast.get("forecast_tiers", {}).get("baseline_median_tier", "T4_NOT_WORTH_IT")

                    keyword_obj.rankability_score = rankability_score
                    keyword_obj.opportunity_tier = opportunity_tier

                    keywords_scored += 1

                    if thread_keyword_list.client_vertical:
                        enhanced_forecast = forecast_service.analyze_keyword_with_client_profile(
                            keyword=keyword,
                            forecast_result=forecast,
                            client_vertical=thread_keyword_list.client_vertical,
                            client_vertical_keywords=thread_keyword_list.client_vertical_keywords
                        )

                        keyword_obj.domain_fit = enhanced_forecast.get("domain_fit", {}).get("score")
                        keyword_obj.intent_fit = enhanced_forecast.get("intent_fit", {}).get("score")
                        keyword_obj.client_forecast = enhanced_forecast.get("client_forecast", {}).get("score")
                        keyword_obj.forecast_tier = enhanced_forecast.get("client_forecast", {}).get("tier")

                    keyword_obj.scored_at = datetime.utcnow()
                    thread_db.commit()

                    # Confirm keyword was scored (used by frontend for retry tracking)
                    event_queue.put(f"data: {json.dumps({'type': 'scored', 'keyword_id': keyword_obj.id, 'keyword': keyword_obj.keyword})}\n\n")

                except Exception as e:
                    print(f"Error scoring keyword '{keyword_obj.keyword}': {e}")
                    thread_db.rollback()
                    event_queue.put(f"data: {json.dumps({'type': 'error', 'keyword': keyword_obj.keyword, 'error': str(e)})}\n\n")
                    continue

            # Send completion event
            event_queue.put(f"data: {json.dumps({'type': 'done', 'keywords_scored': keywords_scored, 'total': total})}\n\n")
            event_queue.put(None)  # Sentinel to signal generator to stop
        except Exception as e:
            print(f"Scoring worker crashed: {e}")
            event_queue.put(f"data: {json.dumps({'type': 'error', 'keyword': 'unknown', 'error': str(e)})}\n\n")
            event_queue.put(None)
        finally:
            thread_db.close()

    def generate():
        """Yield SSE events from the queue, sending heartbeats to keep the connection alive."""
        worker = threading.Thread(target=scoring_worker, daemon=True)
        worker.start()

        while True:
            try:
                event = event_queue.get(timeout=HEARTBEAT_INTERVAL)
                if event is None:
                    break  # Scoring complete
                yield event
            except queue.Empty:
                # No event within interval — send heartbeat to keep connection alive
                yield f": heartbeat\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.delete("/keywords/{keyword_id}")
def delete_keyword(keyword_id: int, db: Session = Depends(get_db)):
    """Delete a keyword from a list"""
    keyword = db.query(Keyword).filter(Keyword.id == keyword_id).first()
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")
    
    list_id = keyword.keyword_list_id
    db.delete(keyword)
    db.commit()
    
    return {"message": "Keyword deleted successfully"}


@router.delete("/lists/{list_id}")
def delete_keyword_list(list_id: int, db: Session = Depends(get_db)):
    """Delete a keyword list"""
    keyword_list = db.query(KeywordList).filter(KeywordList.id == list_id).first()
    if not keyword_list:
        raise HTTPException(status_code=404, detail="Keyword list not found")

    db.delete(keyword_list)
    db.commit()

    return {"message": "Keyword list deleted successfully"}


@router.post("/lists/{list_id}/fetch-volumes")
def fetch_keyword_volumes(list_id: int, db: Session = Depends(get_db)):
    """
    Fetch search volumes from Keywords Everywhere API for all keywords in a list.
    Only fetches volumes for keywords that don't already have volume data.
    """
    from app.services.keywords_everywhere_service import get_keywords_everywhere_service

    keyword_list = db.query(KeywordList).filter(KeywordList.id == list_id).first()
    if not keyword_list:
        raise HTTPException(status_code=404, detail="Keyword list not found")

    # Get keywords that need volume data
    keywords_needing_volume = [k for k in keyword_list.keywords if k.volume is None]

    if not keywords_needing_volume:
        return {
            "message": "All keywords already have volume data",
            "keywords_updated": 0
        }

    # Fetch volumes from Keywords Everywhere
    kwe_service = get_keywords_everywhere_service()
    keyword_texts = [k.keyword for k in keywords_needing_volume]

    try:
        volume_data = kwe_service.get_keyword_data(keyword_texts, country="us")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching volumes: {str(e)}")

    # Update keywords with volume data
    keywords_updated = 0
    for keyword_obj in keywords_needing_volume:
        kw_lower = keyword_obj.keyword.lower()
        if kw_lower in volume_data:
            keyword_obj.volume = volume_data[kw_lower].get("volume", 0)
            keywords_updated += 1

    db.commit()

    return {
        "message": f"Updated volumes for {keywords_updated} keywords",
        "keywords_updated": keywords_updated,
        "total_keywords": len(keyword_list.keywords)
    }

