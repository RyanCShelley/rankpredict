"""
Outline Builder API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.database import Keyword, KeywordAnalysis, Outline, KeywordList
from app.schemas.requests import GenerateOutlineRequest
from app.schemas.responses import OutlineResponse, ImprovementPlanResponse
from app.services.serp_service import get_serp_service
from app.services.semantic_service import get_semantic_service
from app.services.intent_service import get_intent_service
from app.services.outline_service import get_outline_service
from app.services.content_analyzer import get_content_analyzer
import json

router = APIRouter()


@router.get("/projects", response_model=list)
def get_projects(db: Session = Depends(get_db)):
    """
    Get all keyword lists (projects) for the outline builder
    """
    lists = db.query(KeywordList).order_by(KeywordList.created_at.desc()).all()
    return [
        {
            "id": l.id,
            "name": l.name,
            "target_domain_url": l.target_domain_url,
            "keyword_count": len(l.keywords),
            "selected_count": sum(1 for k in l.keywords if k.is_selected)
        }
        for l in lists
    ]


@router.get("/keywords", response_model=list)
def get_keywords(
    list_id: Optional[int] = Query(None, description="Filter by keyword list ID"),
    db: Session = Depends(get_db)
):
    """
    Get keywords for outline builder.
    Only returns keywords that are SELECTED (approved) in the Strategy Dashboard.
    If list_id is provided, filters to that specific project.
    """
    if list_id:
        # Get selected keywords from specific list
        keywords = db.query(Keyword).filter(
            Keyword.keyword_list_id == list_id,
            Keyword.is_selected == True  # Only approved keywords
        ).order_by(Keyword.rankability_score.desc()).all()
    else:
        # Get all selected keywords across all lists
        keywords = db.query(Keyword).filter(
            Keyword.is_selected == True
        ).order_by(Keyword.rankability_score.desc()).all()

    return [
        {
            "id": k.id,
            "keyword": k.keyword,
            "rankability_score": k.rankability_score,
            "opportunity_tier": k.opportunity_tier,
            "content_type": k.content_type,
            "target_url": k.target_url,
            "keyword_list_id": k.keyword_list_id
        }
        for k in keywords
    ]


@router.post("/generate", response_model=OutlineResponse)
def generate_outline(
    request: GenerateOutlineRequest,
    db: Session = Depends(get_db)
):
    """
    Generate dynamic content brief for a keyword
    Includes PAA, related searches, SERP features, and AI-generated outline
    """
    keyword_obj = db.query(Keyword).filter(Keyword.id == request.keyword_id).first()
    if not keyword_obj:
        raise HTTPException(status_code=404, detail="Keyword not found")

    keyword = keyword_obj.keyword

    # Get or fetch SERP analysis
    cached_analysis = db.query(KeywordAnalysis).filter(
        KeywordAnalysis.keyword == keyword
    ).order_by(KeywordAnalysis.analyzed_at.desc()).first()

    serp_service = get_serp_service()
    semantic_service = get_semantic_service()
    intent_service = get_intent_service()
    outline_service = get_outline_service()

    # Track raw SERP data for feature extraction
    raw_serp_data = None
    serp_features = None

    if cached_analysis:
        # Use cached data
        enriched_results = cached_analysis.serp_data.get("enriched_results", [])
        serp_medians = cached_analysis.serp_medians or {}
        # Try to get cached SERP features
        serp_features = cached_analysis.serp_data.get("serp_features", None)
        raw_serp_data = cached_analysis.serp_data.get("raw_serp_data", None)

        # Fix for cached data with buggy flesch/word_count values
        if serp_medians.get("flesch_reading_ease_score", 0) < 10:
            serp_medians["flesch_reading_ease_score"] = 55.0
        if serp_medians.get("word_count", 0) < 100:
            serp_medians["word_count"] = 1500.0
    else:
        # Fetch fresh SERP data
        raw_serp_data = serp_service.fetch_serp_data(keyword)
        organic_results = serp_service.extract_organic_results(raw_serp_data)
        enriched_results = serp_service.enrich_serp_results(organic_results)

        # Compute semantic scores
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

    # Extract SERP features (PAA, related searches, featured snippets, etc.)
    if raw_serp_data and not serp_features:
        serp_features = serp_service.extract_serp_features(raw_serp_data)
    elif not serp_features:
        # If no raw data available, fetch just for features
        try:
            fresh_serp_data = serp_service.fetch_serp_data(keyword)
            serp_features = serp_service.extract_serp_features(fresh_serp_data)
        except Exception as e:
            print(f"Warning: Could not fetch SERP features: {e}")
            serp_features = {
                "people_also_ask": [],
                "related_searches": [],
                "serp_features_present": [],
                "featured_snippet": None
            }

    # Run intent analysis
    serp_results_for_intent = [
        {"title": r.get("title", ""), "snippet": r.get("snippet", "")}
        for r in enriched_results[:10]
    ]
    intent_analysis = intent_service.analyze_intent(keyword, serp_results_for_intent)

    # If user specified a target intent, override the detected intent
    if request.target_intent:
        intent_analysis["intent_type"] = request.target_intent
        intent_analysis["user_override"] = True

    # If existing content mode, analyze the existing content first
    existing_content_data = None
    improvement_plan = None
    if request.content_type == "existing" and (request.existing_url or request.existing_content):
        content_analyzer = get_content_analyzer()

        if request.existing_url:
            # Scrape from URL
            existing_content_data = content_analyzer.analyze_existing_content(request.existing_url, keyword)
        elif request.existing_content:
            # Use pasted content
            existing_content_data = content_analyzer.analyze_pasted_content(request.existing_content, keyword)

        improvement_plan = content_analyzer.generate_improvement_plan(
            current_content=existing_content_data,
            serp_analysis={
                "medians": serp_medians,
                "results": enriched_results
            },
            keyword=keyword
        )

    # Generate dynamic content brief with SERP features
    try:
        outline_data = outline_service.generate_outline(
            keyword=keyword,
            serp_results=enriched_results,
            serp_medians=serp_medians,
            intent_analysis=intent_analysis,
            content_type=request.content_type,
            serp_features=serp_features,
            existing_content=existing_content_data
        )
    except Exception as e:
        error_detail = str(e)
        print(f"Error generating outline: {error_detail}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )
    
    # Build the response first so we can save it
    sections = [
        {
            "heading": s.get("heading", ""),
            "h3_subsections": s.get("h3_subsections", []),
            "topics": s.get("topics", []),
            "word_count_target": s.get("word_count_target", 0),
            "entities": s.get("entities", []),
            "semantic_focus": s.get("semantic_focus", ""),
            "key_points": s.get("key_points", [])
        }
        for s in outline_data.get("sections", [])
    ]

    structure_reasoning = outline_data.get("structure_reasoning", "")
    if isinstance(structure_reasoning, list):
        structure_reasoning = "\n".join(str(x) for x in structure_reasoning)

    serp_features_response = None
    if serp_features:
        serp_features_response = {
            "people_also_ask": serp_features.get("people_also_ask", []),
            "related_searches": serp_features.get("related_searches", []),
            "related_questions": serp_features.get("related_questions", []),
            "featured_snippet": serp_features.get("featured_snippet"),
            "knowledge_panel": serp_features.get("knowledge_panel"),
            "serp_features_present": serp_features.get("serp_features_present", []),
            "ads_present": serp_features.get("ads_present", False),
            "local_pack": serp_features.get("local_pack"),
            "video_results": serp_features.get("video_results", []),
            "image_results": serp_features.get("image_results", []),
            "news_results": serp_features.get("news_results", []),
            "shopping_results": serp_features.get("shopping_results", [])
        }

    # Build full brief data as JSON for storage
    brief_data = {
        "keyword": keyword,
        "intent_analysis": outline_data.get("intent_analysis", intent_analysis),
        "serp_patterns": outline_data.get("serp_patterns", {}),
        "sections": sections,
        "word_count_target": outline_data.get("word_count_target", 0),
        "topics": outline_data.get("topics", []),
        "entities": outline_data.get("entities", []),
        "structure_type": outline_data.get("structure_type", "article"),
        "structure_reasoning": structure_reasoning,
        "title_recommendation": outline_data.get("title_recommendation"),
        "meta_description": outline_data.get("meta_description"),
        "content_strategy": outline_data.get("content_strategy"),
        "search_intent": outline_data.get("search_intent"),
        "questions_to_answer": outline_data.get("questions_to_answer", []),
        "related_topics": outline_data.get("related_topics", []),
        "serp_optimization": outline_data.get("serp_optimization"),
        "competitive_gaps": outline_data.get("competitive_gaps"),
        "serp_features": serp_features_response,
        # Existing content optimization fields
        "optimization_mode": outline_data.get("optimization_mode", False),
        "existing_url": outline_data.get("existing_url"),
        "content_annotations": outline_data.get("content_annotations", []),
        "improvement_plan": improvement_plan
    }

    # Save outline to database with full brief data
    outline = Outline(
        keyword_id=keyword_obj.id,
        name=f"Brief: {keyword}",
        content_type=request.content_type,
        target_url=request.existing_url if request.content_type == "existing" else None,
        target_intent=request.target_intent,
        brief_data=brief_data,
        intent_analysis=intent_analysis,
        outline_structure=outline_data,
        serp_patterns=outline_data.get("serp_patterns", {}),
        serp_features=serp_features,
        improvement_plan=improvement_plan
    )
    db.add(outline)
    db.commit()
    db.refresh(outline)

    # Return response using brief_data (already built above)
    return OutlineResponse(
        keyword=brief_data["keyword"],
        intent_analysis=brief_data["intent_analysis"],
        serp_patterns=brief_data["serp_patterns"],
        sections=brief_data["sections"],
        word_count_target=brief_data["word_count_target"],
        topics=brief_data["topics"],
        entities=brief_data["entities"],
        structure_type=brief_data["structure_type"],
        structure_reasoning=brief_data["structure_reasoning"],
        title_recommendation=brief_data["title_recommendation"],
        meta_description=brief_data["meta_description"],
        content_strategy=brief_data["content_strategy"],
        search_intent=brief_data["search_intent"],
        questions_to_answer=brief_data["questions_to_answer"],
        related_topics=brief_data["related_topics"],
        serp_optimization=brief_data["serp_optimization"],
        competitive_gaps=brief_data["competitive_gaps"],
        serp_features=brief_data["serp_features"],
        # Existing content optimization fields
        optimization_mode=brief_data.get("optimization_mode", False),
        existing_url=brief_data.get("existing_url"),
        content_annotations=brief_data.get("content_annotations", []),
        improvement_plan=improvement_plan
    )


@router.get("/improvement-plan/{keyword_id}", response_model=ImprovementPlanResponse)
def get_improvement_plan(
    keyword_id: int,
    existing_url: str = Query(..., description="URL of existing content"),
    db: Session = Depends(get_db)
):
    """Get improvement plan for existing content"""
    keyword_obj = db.query(Keyword).filter(Keyword.id == keyword_id).first()
    if not keyword_obj:
        raise HTTPException(status_code=404, detail="Keyword not found")
    
    keyword = keyword_obj.keyword
    
    # Get SERP analysis
    cached_analysis = db.query(KeywordAnalysis).filter(
        KeywordAnalysis.keyword == keyword
    ).order_by(KeywordAnalysis.analyzed_at.desc()).first()
    
    if not cached_analysis:
        raise HTTPException(status_code=404, detail="SERP analysis not found. Please score keywords first.")

    serp_medians = cached_analysis.serp_medians or {}
    enriched_results = cached_analysis.serp_data.get("enriched_results", [])
    # Fix for cached data with buggy flesch/word_count values
    if serp_medians.get("flesch_reading_ease_score", 0) < 10:
        serp_medians["flesch_reading_ease_score"] = 55.0
    if serp_medians.get("word_count", 0) < 100:
        serp_medians["word_count"] = 1500.0
    
    # Analyze existing content
    content_analyzer = get_content_analyzer()
    current_content = content_analyzer.analyze_existing_content(existing_url, keyword)
    
    # Generate improvement plan
    improvement_plan = content_analyzer.generate_improvement_plan(
        current_content=current_content,
        serp_analysis={
            "medians": serp_medians,
            "results": enriched_results
        },
        keyword=keyword
    )
    
    return ImprovementPlanResponse(**improvement_plan)


@router.get("/briefs", response_model=list)
def get_saved_briefs(
    list_id: Optional[int] = Query(None, description="Filter by keyword list ID"),
    db: Session = Depends(get_db)
):
    """
    Get all saved briefs, optionally filtered by project (keyword list)
    """
    query = db.query(Outline).join(Keyword)

    if list_id:
        query = query.filter(Keyword.keyword_list_id == list_id)

    briefs = query.order_by(Outline.created_at.desc()).all()

    return [
        {
            "id": b.id,
            "keyword_id": b.keyword_id,
            "keyword": b.keyword.keyword,
            "name": b.name or f"Brief: {b.keyword.keyword}",
            "content_type": b.content_type or "new",
            "target_intent": b.target_intent,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "updated_at": b.updated_at.isoformat() if b.updated_at else None,
            "has_brief_data": b.brief_data is not None
        }
        for b in briefs
    ]


@router.get("/briefs/{brief_id}", response_model=OutlineResponse)
def get_saved_brief(brief_id: int, db: Session = Depends(get_db)):
    """
    Get a specific saved brief by ID
    """
    outline = db.query(Outline).filter(Outline.id == brief_id).first()
    if not outline:
        raise HTTPException(status_code=404, detail="Brief not found")

    # Return from brief_data if available, otherwise reconstruct
    if outline.brief_data:
        brief = outline.brief_data
        return OutlineResponse(
            keyword=brief.get("keyword", outline.keyword.keyword),
            intent_analysis=brief.get("intent_analysis", outline.intent_analysis or {}),
            serp_patterns=brief.get("serp_patterns", outline.serp_patterns or {}),
            sections=brief.get("sections", []),
            word_count_target=brief.get("word_count_target", 0),
            topics=brief.get("topics", []),
            entities=brief.get("entities", []),
            structure_type=brief.get("structure_type", "article"),
            structure_reasoning=brief.get("structure_reasoning", ""),
            title_recommendation=brief.get("title_recommendation"),
            meta_description=brief.get("meta_description"),
            content_strategy=brief.get("content_strategy"),
            search_intent=brief.get("search_intent"),
            questions_to_answer=brief.get("questions_to_answer", []),
            related_topics=brief.get("related_topics", []),
            serp_optimization=brief.get("serp_optimization"),
            competitive_gaps=brief.get("competitive_gaps"),
            serp_features=brief.get("serp_features"),
            optimization_mode=brief.get("optimization_mode", False),
            existing_url=brief.get("existing_url"),
            content_annotations=brief.get("content_annotations", []),
            improvement_plan=brief.get("improvement_plan") or outline.improvement_plan
        )
    else:
        # Legacy brief without brief_data - reconstruct from outline_structure
        outline_data = outline.outline_structure or {}
        sections = outline_data.get("sections", [])

        return OutlineResponse(
            keyword=outline.keyword.keyword,
            intent_analysis=outline.intent_analysis or {},
            serp_patterns=outline.serp_patterns or {},
            sections=sections,
            word_count_target=outline_data.get("word_count_target", 0),
            topics=outline_data.get("topics", []),
            entities=outline_data.get("entities", []),
            structure_type=outline_data.get("structure_type", "article"),
            structure_reasoning=outline_data.get("structure_reasoning", ""),
            title_recommendation=outline_data.get("title_recommendation"),
            meta_description=outline_data.get("meta_description"),
            content_strategy=outline_data.get("content_strategy"),
            search_intent=outline_data.get("search_intent"),
            questions_to_answer=outline_data.get("questions_to_answer", []),
            related_topics=outline_data.get("related_topics", []),
            serp_optimization=outline_data.get("serp_optimization"),
            competitive_gaps=outline_data.get("competitive_gaps"),
            serp_features=None,
            improvement_plan=outline.improvement_plan
        )


@router.delete("/briefs/{brief_id}")
def delete_brief(brief_id: int, db: Session = Depends(get_db)):
    """Delete a saved brief"""
    outline = db.query(Outline).filter(Outline.id == brief_id).first()
    if not outline:
        raise HTTPException(status_code=404, detail="Brief not found")

    db.delete(outline)
    db.commit()
    return {"message": "Brief deleted successfully"}


@router.get("/briefs/{brief_id}/pdf")
def export_brief_pdf(brief_id: int, db: Session = Depends(get_db)):
    """
    Export a brief as PDF - includes complete report with all sections
    Returns PDF file for download
    """
    from fastapi.responses import Response
    from io import BytesIO

    outline = db.query(Outline).filter(Outline.id == brief_id).first()
    if not outline:
        raise HTTPException(status_code=404, detail="Brief not found")

    brief = outline.brief_data or {}
    keyword = brief.get("keyword", outline.keyword.keyword)

    # Generate PDF using reportlab
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="PDF generation requires reportlab. Install with: pip install reportlab"
        )

    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.75*inch, rightMargin=0.75*inch)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            spaceAfter=12,
            textColor=colors.HexColor('#223540')
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceBefore=16,
            spaceAfter=8,
            textColor=colors.HexColor('#00a99d')
        )
        subheading_style = ParagraphStyle(
            'CustomSubheading',
            parent=styles['Heading3'],
            fontSize=12,
            spaceBefore=10,
            spaceAfter=4,
            textColor=colors.HexColor('#223540')
        )
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6
        )
        bullet_style = ParagraphStyle(
            'CustomBullet',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=4,
            leftIndent=20
        )
        label_style = ParagraphStyle(
            'CustomLabel',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=2,
            textColor=colors.HexColor('#666666')
        )
        highlight_style = ParagraphStyle(
            'CustomHighlight',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            backColor=colors.HexColor('#f0f9ff'),
            borderPadding=4
        )

        elements = []

        # Helper to escape XML characters
        def safe_text(text):
            if text is None:
                return ""
            return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        # Title
        elements.append(Paragraph(f"Content Brief: {safe_text(keyword)}", title_style))
        elements.append(Spacer(1, 8))

        # Optimization Mode Banner
        if brief.get("optimization_mode"):
            elements.append(Paragraph(
                f"<b>Optimization Brief for Existing Content</b><br/>{safe_text(brief.get('existing_url', ''))}",
                highlight_style
            ))
            elements.append(Spacer(1, 8))

        # === TITLE & META SECTION ===
        if brief.get("title_recommendation") or brief.get("meta_description"):
            elements.append(Paragraph("Recommended Title &amp; Meta", heading_style))
            if brief.get("title_recommendation"):
                elements.append(Paragraph(f"<b>H1 Title:</b> {safe_text(brief['title_recommendation'])}", body_style))
            if brief.get("meta_description"):
                elements.append(Paragraph(f"<b>Meta Description:</b> {safe_text(brief['meta_description'])}", body_style))
            elements.append(Spacer(1, 8))

        # === CONTENT STRATEGY SECTION ===
        content_strategy = brief.get("content_strategy") or {}
        if content_strategy:
            elements.append(Paragraph("Content Strategy", heading_style))

            # Word count
            if brief.get("optimization_mode") and content_strategy.get("word_count_current"):
                try:
                    wc_current = int(content_strategy.get("word_count_current", 0))
                    wc_target = int(content_strategy.get("word_count_target", 0))
                    wc_action = content_strategy.get("word_count_action", "MAINTAIN")
                    elements.append(Paragraph(
                        f"<b>Word Count:</b> {wc_current:,} → {wc_target:,} words ({wc_action})",
                        body_style
                    ))
                except (ValueError, TypeError):
                    pass
            elif content_strategy.get("target_word_count") or brief.get("word_count_target"):
                try:
                    wc = int(content_strategy.get("target_word_count") or brief.get("word_count_target", 0))
                    elements.append(Paragraph(f"<b>Target Word Count:</b> {wc:,} words", body_style))
                except (ValueError, TypeError):
                    pass

            # Readability
            if brief.get("optimization_mode") and content_strategy.get("readability_current"):
                read_current = content_strategy.get("readability_current", 0)
                read_target = content_strategy.get("readability_target", "")
                read_action = content_strategy.get("readability_action", "MAINTAIN")
                elements.append(Paragraph(
                    f"<b>Readability (Flesch):</b> {read_current} → {read_target} ({read_action})",
                    body_style
                ))
            elif content_strategy.get("readability_target"):
                elements.append(Paragraph(
                    f"<b>Target Readability:</b> Flesch {content_strategy['readability_target']}",
                    body_style
                ))

            # Schema types
            schema_types = content_strategy.get("schema_types") or []
            if schema_types:
                elements.append(Paragraph(f"<b>Schema Markup:</b> {', '.join(schema_types)}", body_style))

            # Key differentiators
            key_diffs = content_strategy.get("key_differentiators") or []
            if key_diffs:
                elements.append(Paragraph("<b>Key Differentiators:</b>", body_style))
                for diff in key_diffs:
                    elements.append(Paragraph(f"• {safe_text(diff)}", bullet_style))

            elements.append(Spacer(1, 8))

        # === SERP FEATURES SECTION ===
        serp_features = brief.get("serp_features") or {}
        if serp_features:
            features_present = serp_features.get("serp_features_present") or []
            if features_present:
                elements.append(Paragraph("SERP Features Present", heading_style))
                features_text = ", ".join([f.replace("_", " ").title() for f in features_present])
                elements.append(Paragraph(features_text, body_style))

            # Featured snippet
            featured_snippet = serp_features.get("featured_snippet")
            if featured_snippet:
                elements.append(Paragraph("<b>Featured Snippet Opportunity:</b>", label_style))
                elements.append(Paragraph(
                    f"Type: {featured_snippet.get('type', 'paragraph')}",
                    body_style
                ))

            if features_present or featured_snippet:
                elements.append(Spacer(1, 8))

        # === PEOPLE ALSO ASK SECTION ===
        paa = serp_features.get("people_also_ask", []) if serp_features else []
        if paa:
            elements.append(Paragraph("People Also Ask (Must Answer)", heading_style))
            for item in paa:
                question = item.get("question", "") if isinstance(item, dict) else str(item)
                if question:
                    elements.append(Paragraph(f"• {safe_text(question)}", bullet_style))
            elements.append(Spacer(1, 8))

        # === RELATED SEARCHES SECTION ===
        related_searches = serp_features.get("related_searches", []) if serp_features else []
        if related_searches:
            elements.append(Paragraph("Related Searches", heading_style))
            elements.append(Paragraph(", ".join([safe_text(rs) for rs in related_searches[:12]]), body_style))
            elements.append(Spacer(1, 8))

        # === INTENT ANALYSIS SECTION ===
        intent = brief.get("intent_analysis", {})
        search_intent = brief.get("search_intent", {})
        if intent or search_intent:
            elements.append(Paragraph("Search Intent Analysis", heading_style))
            intent_type = intent.get("intent_type") or search_intent.get("primary_intent", "Unknown")
            elements.append(Paragraph(f"<b>Intent Type:</b> {safe_text(intent_type)}", body_style))

            if intent.get("content_format") or search_intent.get("content_format"):
                fmt = intent.get("content_format") or search_intent.get("content_format")
                elements.append(Paragraph(f"<b>Content Format:</b> {safe_text(fmt)}", body_style))

            if search_intent.get("user_expectation"):
                elements.append(Paragraph(f"<b>User Expectation:</b> {safe_text(search_intent['user_expectation'])}", body_style))

            if search_intent.get("user_journey_stage"):
                elements.append(Paragraph(f"<b>Journey Stage:</b> {safe_text(search_intent['user_journey_stage'])}", body_style))

            elements.append(Spacer(1, 8))

        # === CONTENT ANNOTATIONS (for optimization mode) ===
        annotations = brief.get("content_annotations") or []
        if annotations:
            elements.append(Paragraph("Content Improvements Needed", heading_style))
            for i, ann in enumerate(annotations, 1):
                if ann and isinstance(ann, dict):
                    priority = (ann.get("priority") or "medium").upper()
                    elements.append(Paragraph(f"<b>{i}. [{priority}]</b>", subheading_style))
                    elements.append(Paragraph(f"<b>Original:</b> {safe_text(ann.get('original_text', ''))}", body_style))
                    elements.append(Paragraph(f"<b>Improved:</b> {safe_text(ann.get('improved_text', ''))}", body_style))
                    elements.append(Paragraph(f"<i>Reason: {safe_text(ann.get('reason', ''))}</i>", body_style))
                    elements.append(Spacer(1, 4))
            elements.append(Spacer(1, 8))

        # === QUESTIONS TO ANSWER SECTION ===
        questions = brief.get("questions_to_answer") or []
        if questions:
            elements.append(Paragraph("Questions to Answer", heading_style))
            for q in questions:
                if q and isinstance(q, dict):
                    question = q.get("question") or str(q)
                    priority = q.get("priority") or ""
                    format_type = q.get("format") or ""
                    q_text = f"• {safe_text(question)}"
                    if priority or format_type:
                        q_text += f" <i>({priority}{', ' + format_type if format_type else ''})</i>"
                    elements.append(Paragraph(q_text, bullet_style))
                elif q:
                    elements.append(Paragraph(f"• {safe_text(str(q))}", bullet_style))
            elements.append(Spacer(1, 8))

        # === CONTENT OUTLINE SECTION ===
        sections = brief.get("sections") or []
        if sections:
            outline_title = "Optimized Content Structure" if brief.get("optimization_mode") else "Content Outline"
            elements.append(Paragraph(outline_title, heading_style))

            for i, section in enumerate(sections, 1):
                if not section or not isinstance(section, dict):
                    continue
                heading = section.get("heading") or f"Section {i}"
                status = section.get("status") or ""
                wc_target = section.get("word_count_target") or 0

                # Section heading with status
                heading_text = f"<b>{i}. {safe_text(heading)}</b>"
                if status:
                    heading_text += f" <i>[{status}]</i>"
                if wc_target:
                    try:
                        heading_text += f" ({int(wc_target):,} words)"
                    except (ValueError, TypeError):
                        pass
                elements.append(Paragraph(heading_text, subheading_style))

                # Semantic focus / description
                semantic_focus = section.get("semantic_focus") or ""
                if semantic_focus:
                    elements.append(Paragraph(f"<i>{safe_text(semantic_focus)}</i>", body_style))

                # Subsections (H3s)
                h3s = section.get("h3_subsections") or []
                if h3s:
                    for h3 in h3s:
                        if h3:
                            h3_text = h3.get("heading", str(h3)) if isinstance(h3, dict) else str(h3)
                            elements.append(Paragraph(f"  → {safe_text(h3_text)}", bullet_style))

                # Key points
                key_points = section.get("key_points") or []
                if key_points:
                    for point in key_points:
                        if point:
                            elements.append(Paragraph(f"    • {safe_text(point)}", bullet_style))

                elements.append(Spacer(1, 6))

            elements.append(Spacer(1, 8))

        # === SEMANTIC COVERAGE SECTION ===
        topics = brief.get("topics") or []
        related_topics = brief.get("related_topics") or []
        entities = brief.get("entities") or []

        if topics or related_topics or entities:
            elements.append(Paragraph("Semantic Coverage", heading_style))

            if topics:
                elements.append(Paragraph("<b>Must-Cover Topics:</b>", label_style))
                elements.append(Paragraph(", ".join([safe_text(t) for t in topics if t]), body_style))

            if related_topics:
                elements.append(Paragraph("<b>Related Topics:</b>", label_style))
                elements.append(Paragraph(", ".join([safe_text(t) for t in related_topics if t]), body_style))

            if entities:
                elements.append(Paragraph("<b>Entities to Mention:</b>", label_style))
                elements.append(Paragraph(", ".join([safe_text(e) for e in entities if e]), body_style))

            elements.append(Spacer(1, 8))

        # === SERP OPTIMIZATION SECTION ===
        serp_opt = brief.get("serp_optimization") or {}
        if serp_opt:
            elements.append(Paragraph("SERP Optimization Strategies", heading_style))

            if serp_opt.get("featured_snippet_strategy"):
                elements.append(Paragraph(f"<b>Featured Snippet Strategy:</b> {safe_text(serp_opt['featured_snippet_strategy'])}", body_style))

            faq_questions = serp_opt.get("faq_schema_questions") or []
            if faq_questions:
                elements.append(Paragraph("<b>FAQ Schema Questions:</b>", label_style))
                for faq in faq_questions:
                    if faq:
                        elements.append(Paragraph(f"• {safe_text(faq)}", bullet_style))

            other_opps = serp_opt.get("other_opportunities") or []
            if other_opps:
                elements.append(Paragraph("<b>Other Opportunities:</b>", label_style))
                for opp in other_opps:
                    if opp:
                        elements.append(Paragraph(f"• {safe_text(opp)}", bullet_style))

            elements.append(Spacer(1, 8))

        # === COMPETITIVE GAPS / ACTION SUMMARY SECTION ===
        comp_gaps = brief.get("competitive_gaps") or {}
        if comp_gaps:
            section_title = "Action Summary" if brief.get("optimization_mode") else "Competitive Analysis"
            elements.append(Paragraph(section_title, heading_style))

            # Quick wins
            quick_wins = comp_gaps.get("quick_wins") or []
            if quick_wins:
                elements.append(Paragraph("<b>Quick Wins:</b>", label_style))
                for i, win in enumerate(quick_wins, 1):
                    if win:
                        elements.append(Paragraph(f"{i}. {safe_text(win)}", bullet_style))

            # Missing from page (optimization) or competitors (new content)
            missing = (comp_gaps.get("missing_from_page") or []) or (comp_gaps.get("missing_from_competitors") or [])
            if missing:
                label = "Missing from Your Page:" if brief.get("optimization_mode") else "Missing from Competitors:"
                elements.append(Paragraph(f"<b>{label}</b>", label_style))
                for item in missing:
                    if item:
                        elements.append(Paragraph(f"• {safe_text(item)}", bullet_style))

            # Strengths to keep (optimization)
            strengths = comp_gaps.get("strengths_to_keep") or []
            if strengths:
                elements.append(Paragraph("<b>Strengths to Keep:</b>", label_style))
                for item in strengths:
                    if item:
                        elements.append(Paragraph(f"• {safe_text(item)}", bullet_style))

            # Unique angles
            unique_angles = comp_gaps.get("unique_angles") or []
            if unique_angles:
                elements.append(Paragraph("<b>Unique Angles:</b>", label_style))
                for angle in unique_angles:
                    if angle:
                        elements.append(Paragraph(f"• {safe_text(angle)}", bullet_style))

            # Comprehensiveness improvements
            comp_improvements = comp_gaps.get("comprehensiveness_improvements") or []
            if comp_improvements:
                elements.append(Paragraph("<b>Comprehensiveness Improvements:</b>", label_style))
                for imp in comp_improvements:
                    if imp:
                        elements.append(Paragraph(f"• {safe_text(imp)}", bullet_style))

        doc.build(elements)

        pdf_bytes = buffer.getvalue()
        buffer.close()

        # Return as downloadable file
        filename = f"brief_{keyword.replace(' ', '_')}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        import traceback
        import sys
        error_detail = f"Error generating PDF: {str(e)}"
        print(error_detail, file=sys.stderr)
        traceback.print_exc()
        # Include more detail in the response for debugging
        tb_str = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail=f"{error_detail}\n\nTraceback:\n{tb_str}"
        )

