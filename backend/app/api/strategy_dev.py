"""
Strategy Development API Routes

Handles projects, GSC integration, topic classification, and buyer journey analysis.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import csv
import io
from datetime import datetime
import asyncio

from app.database import get_db, SessionLocal
from app.models.database import StrategyProject, StrategyKeyword, User, KeywordList, Keyword, Outline
from app.api.auth import get_current_user_from_token
from app.api.strategy import _normalize_domain
from app.services import gsc_service, topic_service, buyer_journey_service
from app.services.keywords_everywhere_service import fetch_keyword_volumes
from app.config import TOPIC_SIMILARITY_THRESHOLD


def get_project_for_write(db: Session, project_id: int, user: User) -> StrategyProject:
    """Get a project for write operations - allows owner OR admin/master roles."""
    project = db.query(StrategyProject).filter(StrategyProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id != user.id and user.role not in ("admin", "master"):
        raise HTTPException(status_code=403, detail="Access denied")
    return project


router = APIRouter()


# Request/Response Models
class TopicInput(BaseModel):
    name: str
    keywords: List[str]


class CreateProjectRequest(BaseModel):
    name: str
    domain: Optional[str] = None
    core_topics: Optional[List[TopicInput]] = None


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    core_topics: Optional[List[TopicInput]] = None
    gsc_property_url: Optional[str] = None
    persona: Optional[dict] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    domain: Optional[str] = None
    gsc_property_url: Optional[str]
    gsc_connected: bool
    core_topics: Optional[List[dict]]
    persona: Optional[dict] = None
    keyword_count: int
    num_funnels: Optional[int] = None
    num_terms: Optional[int] = None
    num_briefs: Optional[int] = None
    sync_status: Optional[str]
    sync_message: Optional[str]
    created_at: datetime
    updated_at: datetime


class StrategyKeywordResponse(BaseModel):
    id: int
    query: str
    page_url: Optional[str]
    clicks: int
    impressions: int
    avg_position: Optional[float]
    assigned_topic: Optional[str]
    topic_similarity: Optional[float]
    buyer_journey_stage: Optional[str]
    journey_confidence: Optional[float]
    volume: Optional[int]


class ProjectDetailResponse(BaseModel):
    project: ProjectResponse
    keywords: List[StrategyKeywordResponse]


class GscAuthUrlResponse(BaseModel):
    auth_url: str
    configured: bool


class GscSiteResponse(BaseModel):
    site_url: str
    permission_level: str


class ExportToListRequest(BaseModel):
    keyword_ids: List[int]
    list_id: Optional[int] = None
    new_list_name: Optional[str] = None
    target_domain_url: Optional[str] = None


# Project CRUD Endpoints
@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """List all strategy projects (team-wide access)."""
    projects = db.query(StrategyProject).order_by(StrategyProject.updated_at.desc()).all()

    result = []
    for p in projects:
        # Compute inline stats from linked keyword lists
        linked_lists = db.query(KeywordList).filter(KeywordList.project_id == p.id).all()
        num_funnels = len(p.core_topics) if p.core_topics else 0
        num_terms = sum(
            db.query(Keyword).filter(Keyword.keyword_list_id == kl.id).count()
            for kl in linked_lists
        )
        num_briefs = sum(
            db.query(Outline).join(Keyword).filter(Keyword.keyword_list_id == kl.id).count()
            for kl in linked_lists
        )

        result.append(ProjectResponse(
            id=p.id,
            name=p.name,
            domain=p.domain,
            gsc_property_url=p.gsc_property_url,
            gsc_connected=bool(p.gsc_refresh_token),
            core_topics=p.core_topics,
            persona=p.persona,
            keyword_count=len(p.keywords),
            num_funnels=num_funnels,
            num_terms=num_terms,
            num_briefs=num_briefs,
            sync_status=p.sync_status,
            sync_message=p.sync_message,
            created_at=p.created_at,
            updated_at=p.updated_at
        ))

    return result


@router.post("/projects")
async def create_project(
    request: CreateProjectRequest,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Create a new strategy project."""
    try:
        # Convert topics to dict using model_dump (Pydantic v2)
        topics_data = None
        if request.core_topics:
            topics_data = [t.model_dump() for t in request.core_topics]

        project = StrategyProject(
            name=request.name,
            domain=request.domain,
            user_id=current_user.id,
            core_topics=topics_data
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        # Auto-link any orphan keyword lists with matching domain
        if project.domain:
            normalized = _normalize_domain(project.domain)
            orphan_lists = db.query(KeywordList).filter(KeywordList.project_id.is_(None)).all()
            for kl in orphan_lists:
                if kl.target_domain_url and _normalize_domain(kl.target_domain_url) == normalized:
                    kl.project_id = project.id
                    # Populate client profile from core_topics if list has none
                    if not kl.client_vertical_keywords and topics_data:
                        vertical_keywords = []
                        for topic in topics_data:
                            if topic.get("name"):
                                vertical_keywords.append(topic["name"])
                            for kw in topic.get("keywords", []):
                                if kw:
                                    vertical_keywords.append(kw)
                        if vertical_keywords:
                            kl.client_vertical = "custom"
                            kl.client_vertical_keywords = vertical_keywords
            db.commit()

        return {
            "id": project.id,
            "name": project.name,
            "domain": project.domain,
            "gsc_property_url": project.gsc_property_url,
            "gsc_connected": bool(project.gsc_refresh_token),
            "core_topics": project.core_topics,
            "persona": project.persona,
            "keyword_count": 0,
            "num_funnels": 0,
            "num_terms": 0,
            "num_briefs": 0,
            "sync_status": project.sync_status,
            "sync_message": project.sync_message,
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "updated_at": project.updated_at.isoformat() if project.updated_at else None
        }
    except Exception as e:
        import traceback
        print(f"Error creating project: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: int,
    topic_filter: Optional[str] = None,
    stage_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Get project details with keywords (team-wide access)."""
    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Build keyword query with filters
    query = db.query(StrategyKeyword).filter(
        StrategyKeyword.project_id == project_id
    )

    if topic_filter:
        query = query.filter(StrategyKeyword.assigned_topic == topic_filter)

    if stage_filter:
        query = query.filter(StrategyKeyword.buyer_journey_stage == stage_filter)

    keywords = query.order_by(StrategyKeyword.clicks.desc()).all()

    return ProjectDetailResponse(
        project=ProjectResponse(
            id=project.id,
            name=project.name,
            domain=project.domain,
            gsc_property_url=project.gsc_property_url,
            gsc_connected=bool(project.gsc_refresh_token),
            core_topics=project.core_topics,
            persona=project.persona,
            keyword_count=len(project.keywords),
            sync_status=project.sync_status,
            sync_message=project.sync_message,
            created_at=project.created_at,
            updated_at=project.updated_at
        ),
        keywords=[
            StrategyKeywordResponse(
                id=kw.id,
                query=kw.query,
                page_url=kw.page_url,
                clicks=kw.clicks,
                impressions=kw.impressions,
                avg_position=kw.avg_position,
                assigned_topic=kw.assigned_topic,
                topic_similarity=kw.topic_similarity,
                buyer_journey_stage=kw.buyer_journey_stage,
                journey_confidence=kw.journey_confidence,
                volume=kw.volume
            )
            for kw in keywords
        ]
    )


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    request: UpdateProjectRequest,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Update project settings (owner or admin/master only)."""
    project = get_project_for_write(db, project_id, current_user)

    if request.name is not None:
        project.name = request.name

    if request.domain is not None:
        project.domain = request.domain

    if request.core_topics is not None:
        project.core_topics = [t.model_dump() for t in request.core_topics]

    if request.gsc_property_url is not None:
        project.gsc_property_url = request.gsc_property_url

    if request.persona is not None:
        project.persona = request.persona

    db.commit()
    db.refresh(project)

    return ProjectResponse(
        id=project.id,
        name=project.name,
        domain=project.domain,
        gsc_property_url=project.gsc_property_url,
        gsc_connected=bool(project.gsc_refresh_token),
        core_topics=project.core_topics,
        persona=project.persona,
        keyword_count=len(project.keywords),
        sync_status=project.sync_status,
        sync_message=project.sync_message,
        created_at=project.created_at,
        updated_at=project.updated_at
    )


class GeneratePersonaRequest(BaseModel):
    description: str


@router.post("/projects/{project_id}/generate-persona")
async def generate_persona(
    project_id: int,
    request: GeneratePersonaRequest,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Generate an expanded persona profile from a brief description."""
    from app.services.query_fanning_service import get_active_provider, _call_claude, _call_openai

    project = get_project_for_write(db, project_id, current_user)

    provider = get_active_provider()
    if not provider:
        raise HTTPException(status_code=500, detail="No LLM API key configured.")

    prompt = f"""You are an expert SEO strategist and audience researcher.
Given a brief persona description, expand it into a detailed persona profile for SEO content strategy.

Brief description: {request.description}

Create a comprehensive persona profile covering:
1. **Demographics & Psychographics**: Age range, income level, lifestyle, values, and motivations
2. **Pain Points & Needs**: What problems they're trying to solve, what frustrations they experience
3. **Search Behavior**: How they search, what devices they use, what types of queries they make
4. **Decision Factors**: What influences their purchasing decisions, what they prioritize
5. **Language & Terminology**: Specific words, phrases, and jargon this persona uses

Write the profile in a natural, detailed paragraph format (not bullet points). Keep it to 150-200 words.
Return ONLY the persona profile text, no headers or formatting."""

    try:
        if provider == "claude":
            expanded = _call_claude(prompt)
        else:
            expanded = _call_openai(prompt)

        persona = {"description": request.description, "expanded": expanded.strip()}
        project.persona = persona
        db.commit()

        return {"persona": persona}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate persona: {str(e)}")


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Delete a project and all its keywords (owner or admin/master only)."""
    project = get_project_for_write(db, project_id, current_user)

    db.delete(project)
    db.commit()

    return {"message": "Project deleted"}


# GSC OAuth Endpoints
@router.get("/gsc/auth-url", response_model=GscAuthUrlResponse)
async def get_gsc_auth_url(
    project_id: int,
    current_user: User = Depends(get_current_user_from_token)
):
    """Get OAuth URL for Google Search Console authorization."""
    if not gsc_service.is_configured():
        return GscAuthUrlResponse(
            auth_url="",
            configured=False
        )

    auth_url = gsc_service.get_auth_url(state=str(project_id))
    return GscAuthUrlResponse(
        auth_url=auth_url,
        configured=True
    )


@router.get("/gsc/callback")
async def gsc_callback(
    code: str,
    state: str = "",
    db: Session = Depends(get_db)
):
    """Handle OAuth callback from Google."""
    try:
        # Exchange code for tokens
        tokens = await gsc_service.exchange_code(code)

        if state:
            project_id = int(state)
            project = db.query(StrategyProject).filter(
                StrategyProject.id == project_id
            ).first()

            if project:
                project.gsc_refresh_token = tokens.get("refresh_token", "")
                db.commit()

        # Return styled HTML that closes the popup and notifies parent
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content="""
        <html>
        <head><style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: #f8fafc; }
            .card { text-align: center; padding: 40px; background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
            .check { width: 64px; height: 64px; border-radius: 50%; background: #22c55e; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 16px; }
            .check svg { width: 32px; height: 32px; fill: none; stroke: white; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }
            h2 { color: #1e293b; margin: 0 0 8px; }
            p { color: #64748b; margin: 0; }
        </style></head>
        <body>
            <div class="card">
                <div class="check"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></div>
                <h2>GSC Connected!</h2>
                <p>This window will close automatically...</p>
            </div>
            <script>
                if (window.opener) {
                    window.opener.postMessage({type: 'GSC_AUTH_SUCCESS'}, '*');
                    setTimeout(() => window.close(), 2000);
                }
            </script>
        </body>
        </html>
        """)
    except Exception as e:
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=f"""
        <html>
        <head><style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: #f8fafc; }}
            .card {{ text-align: center; padding: 40px; background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); max-width: 400px; }}
            .icon {{ width: 64px; height: 64px; border-radius: 50%; background: #ef4444; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 16px; }}
            .icon svg {{ width: 32px; height: 32px; fill: none; stroke: white; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }}
            h2 {{ color: #1e293b; margin: 0 0 8px; }}
            p {{ color: #64748b; margin: 0; word-break: break-word; }}
        </style></head>
        <body>
            <div class="card">
                <div class="icon"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></div>
                <h2>Connection Failed</h2>
                <p>{str(e)}</p>
            </div>
        </body>
        </html>
        """, status_code=400)


@router.get("/gsc/sites", response_model=List[GscSiteResponse])
async def list_gsc_sites(
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """List available GSC sites for a connected project (team-wide access)."""
    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.gsc_refresh_token:
        raise HTTPException(status_code=400, detail="GSC not connected")

    try:
        # Get fresh access token
        token_data = await gsc_service.refresh_access_token(project.gsc_refresh_token)
        access_token = token_data["access_token"]

        # List sites
        sites = await gsc_service.list_sites(access_token)

        return [
            GscSiteResponse(
                site_url=site.get("siteUrl", ""),
                permission_level=site.get("permissionLevel", "")
            )
            for site in sites
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to list sites: {str(e)}")


# Background sync task
def run_sync_in_background(
    project_id: int,
    max_position: Optional[float],
    gsc_refresh_token: str,
    gsc_property_url: str,
    core_topics: Optional[List[dict]]
):
    """Background task that performs the actual sync work."""
    import asyncio

    # Create new event loop for background task
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _do_sync(project_id, max_position, gsc_refresh_token, gsc_property_url, core_topics)
        )
    finally:
        loop.close()


async def _do_sync(
    project_id: int,
    max_position: Optional[float],
    gsc_refresh_token: str,
    gsc_property_url: str,
    core_topics: Optional[List[dict]]
):
    """Actual sync logic that runs in background."""
    # Create new DB session for background task
    db = SessionLocal()

    try:
        print(f"[Background] Starting sync for project {project_id}...")

        # Update status to syncing
        project = db.query(StrategyProject).filter(StrategyProject.id == project_id).first()
        if project:
            project.sync_status = "syncing"
            project.sync_message = "Fetching data from Google Search Console..."
            db.commit()

        # Fetch GSC data
        print("[Background] Fetching GSC data...")
        rows, _ = await gsc_service.fetch_with_refresh(
            gsc_refresh_token,
            gsc_property_url,
            days=90
        )
        print(f"[Background] Fetched {len(rows)} rows from GSC")

        if not rows:
            project = db.query(StrategyProject).filter(StrategyProject.id == project_id).first()
            if project:
                project.sync_status = "complete"
                project.sync_message = "No data found in GSC"
                db.commit()
            return

        # Update status
        project = db.query(StrategyProject).filter(StrategyProject.id == project_id).first()
        if project:
            project.sync_message = f"Processing {len(rows)} queries..."
            db.commit()

        # Filter by position if specified
        if max_position is not None:
            original_count = len(rows)
            rows = [r for r in rows if r.get("avg_position") and r["avg_position"] <= max_position]
            print(f"[Background] Filtered to {len(rows)} rows with position <= {max_position} (was {original_count})")

        # Deduplicate by query - keep the row with highest clicks per unique query
        seen_queries = {}
        for r in rows:
            q = r["query"]
            if q not in seen_queries or r.get("clicks", 0) > seen_queries[q].get("clicks", 0):
                seen_queries[q] = r
        deduped_count = len(rows)
        rows = list(seen_queries.values())
        print(f"[Background] Deduplicated from {deduped_count} to {len(rows)} unique queries")

        # Sort by clicks for priority-based processing
        rows = sorted(rows, key=lambda x: x.get("clicks", 0), reverse=True)

        topics = core_topics or []

        # Limit rows before expensive classification
        # Only need ~300 per topic since we cap at 100 (buffer for threshold filtering)
        if topics:
            MAX_KEYWORDS = max(len(topics) * 300, 500)
        else:
            MAX_KEYWORDS = 5000
        if len(rows) > MAX_KEYWORDS:
            rows = rows[:MAX_KEYWORDS]
            print(f"[Background] Limited to top {MAX_KEYWORDS} keywords by clicks")

        # Clear existing keywords
        db.query(StrategyKeyword).filter(
            StrategyKeyword.project_id == project_id
        ).delete()
        db.commit()

        # Classify keywords by topic (only if topics defined)
        queries = [r["query"] for r in rows]
        topic_lookup = {}

        if topics:
            # Update status
            project = db.query(StrategyProject).filter(StrategyProject.id == project_id).first()
            if project:
                project.sync_message = f"Classifying {len(queries)} keywords by topic..."
                db.commit()

            print(f"[Background] Classifying {len(queries)} keywords by topic...")
            topic_results = topic_service.classify_keywords_batch(
                queries, topics, threshold=TOPIC_SIMILARITY_THRESHOLD
            )
            topic_lookup = {r["keyword"]: r for r in topic_results}
            del topic_results
            print("[Background] Topic classification complete")

            # Build a row lookup for fast clicks access
            row_clicks = {r["query"]: r.get("clicks", 0) for r in rows}

            # Cap at 100 terms per topic - keep top 100 by clicks
            topic_groups = {}
            for keyword, data in topic_lookup.items():
                t = data.get("assigned_topic")
                if t:
                    if t not in topic_groups:
                        topic_groups[t] = []
                    topic_groups[t].append((keyword, row_clicks.get(keyword, 0)))

            for t, items in topic_groups.items():
                items.sort(key=lambda x: x[1], reverse=True)
                kept = items[:100]
                removed = items[100:]
                for kw, _ in removed:
                    del topic_lookup[kw]
                if removed:
                    print(f"[Background] Capped topic '{t}' to 100 terms (removed {len(removed)})")
                else:
                    print(f"[Background] Topic '{t}': {len(kept)} terms")
        else:
            print("[Background] No topics defined, skipping topic classification")

        del queries

        # Build final list of rows to save (apply topic filter first)
        rows_to_save = []
        for row in rows:
            topic_data = topic_lookup.get(row["query"], {})
            if topics and topic_data.get("assigned_topic") is None:
                continue
            rows_to_save.append((row, topic_data))

        # Update status
        project = db.query(StrategyProject).filter(StrategyProject.id == project_id).first()
        if project:
            project.sync_message = f"Classifying {len(rows_to_save)} keywords by buyer journey..."
            db.commit()

        # Classify buyer journey and save ONLY kept keywords
        keywords_added = 0
        BATCH_SIZE = 200

        for row, topic_data in rows_to_save:
            query = row["query"]
            stage, confidence = buyer_journey_service.classify_buyer_journey(query)

            kw = StrategyKeyword(
                project_id=project_id,
                query=query,
                page_url=row.get("page_url"),
                clicks=row.get("clicks", 0),
                impressions=row.get("impressions", 0),
                avg_position=row.get("avg_position"),
                assigned_topic=topic_data.get("assigned_topic"),
                topic_similarity=topic_data.get("topic_similarity"),
                buyer_journey_stage=stage,
                journey_confidence=confidence
            )
            db.add(kw)
            keywords_added += 1

            if keywords_added % BATCH_SIZE == 0:
                db.commit()
                print(f"[Background] Committed {keywords_added} keywords...")

        db.commit()
        print(f"[Background] Added {keywords_added} keywords to database")

        # Count classified vs unclassified
        classified = sum(1 for r in rows if topic_lookup.get(r["query"], {}).get("assigned_topic")) if topics else 0

        # Update status to complete
        project = db.query(StrategyProject).filter(StrategyProject.id == project_id).first()
        if project:
            project.sync_status = "complete"
            msg = f"Sync complete. Added {keywords_added} keywords."
            if topics and classified > 0:
                msg += f" ({classified} classified by topic, {keywords_added - classified} unclassified)"
            project.sync_message = msg
            db.commit()

        print(f"[Background] Sync complete for project {project_id}")

    except Exception as e:
        import traceback
        print(f"[Background] Sync error: {e}")
        print(traceback.format_exc())

        # Update status to error
        try:
            project = db.query(StrategyProject).filter(StrategyProject.id == project_id).first()
            if project:
                project.sync_status = "error"
                project.sync_message = f"Sync failed: {str(e)}"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


# Sync Endpoint
@router.post("/projects/{project_id}/sync")
async def sync_project(
    project_id: int,
    max_position: Optional[float] = Query(default=None, description="Only include queries with avg position <= this value"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Start a background sync of GSC data (owner or admin/master only).
    Returns immediately while sync runs in background.
    Check project.sync_status to monitor progress.
    """
    project = get_project_for_write(db, project_id, current_user)

    if not project.gsc_refresh_token:
        raise HTTPException(status_code=400, detail="GSC not connected")

    if not project.gsc_property_url:
        raise HTTPException(status_code=400, detail="No GSC property selected")

    # Check if already syncing
    if project.sync_status == "syncing":
        return {
            "message": "Sync already in progress",
            "sync_status": "syncing",
            "sync_message": project.sync_message
        }

    # Set initial status
    project.sync_status = "syncing"
    project.sync_message = "Starting sync..."
    db.commit()

    # Start background task
    background_tasks.add_task(
        run_sync_in_background,
        project_id,
        max_position,
        project.gsc_refresh_token,
        project.gsc_property_url,
        project.core_topics
    )

    return {
        "message": "Sync started",
        "sync_status": "syncing",
        "sync_message": "Starting sync..."
    }


# Export Endpoints
@router.post("/keywords/export-csv")
async def export_keywords_csv(
    keyword_ids: List[int] = Query(...),
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Export selected keywords to CSV (team-wide access)."""
    keywords = db.query(StrategyKeyword).filter(
        StrategyKeyword.id.in_(keyword_ids)
    ).all()

    if not keywords:
        raise HTTPException(status_code=404, detail="No keywords found")

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Query", "Page URL", "Topic", "Topic Similarity",
        "Journey Stage", "Clicks", "Impressions", "Avg Position", "Volume"
    ])

    for kw in keywords:
        writer.writerow([
            kw.query,
            kw.page_url or "",
            kw.assigned_topic or "",
            kw.topic_similarity or "",
            kw.buyer_journey_stage or "",
            kw.clicks,
            kw.impressions,
            round(kw.avg_position, 1) if kw.avg_position else "",
            kw.volume or ""
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=keywords_export.csv"}
    )


@router.post("/keywords/add-to-list")
async def add_keywords_to_list(
    request: ExportToListRequest,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Add selected keywords to an existing or new Rank Predict list."""
    # Get strategy keywords
    strategy_keywords = db.query(StrategyKeyword).filter(
        StrategyKeyword.id.in_(request.keyword_ids)
    ).all()

    if not strategy_keywords:
        raise HTTPException(status_code=404, detail="No keywords found")

    # Verify user owns the projects
    project_ids = set(kw.project_id for kw in strategy_keywords)
    projects = db.query(StrategyProject).filter(
        StrategyProject.id.in_(project_ids),
        StrategyProject.user_id == current_user.id
    ).all()

    if len(projects) != len(project_ids):
        raise HTTPException(status_code=403, detail="Access denied")

    # Resolve the source project for auto-populating list settings
    source_project = None
    if project_ids:
        source_project = db.query(StrategyProject).filter(
            StrategyProject.id == list(project_ids)[0]
        ).first()

    # Get or create list
    if request.list_id:
        keyword_list = db.query(KeywordList).filter(
            KeywordList.id == request.list_id
        ).first()
        if not keyword_list:
            raise HTTPException(status_code=404, detail="List not found")
        # Link to project if not already linked
        if not keyword_list.project_id and source_project:
            keyword_list.project_id = source_project.id
    elif request.new_list_name:
        # Use project domain as fallback target_domain_url
        target_url = request.target_domain_url
        if not target_url and source_project and source_project.domain:
            target_url = source_project.domain if source_project.domain.startswith("http") else f"https://{source_project.domain}"
        if not target_url:
            raise HTTPException(status_code=400, detail="Target domain required for new list")

        # Auto-populate client profile from project core_topics
        vertical_keywords = None
        if source_project and source_project.core_topics:
            vertical_keywords = []
            for topic in source_project.core_topics:
                if topic.get("name"):
                    vertical_keywords.append(topic["name"])
                for kw in topic.get("keywords", []):
                    if kw:
                        vertical_keywords.append(kw)

        keyword_list = KeywordList(
            name=request.new_list_name,
            target_domain_url=target_url,
            project_id=source_project.id if source_project else None,
            client_vertical="custom" if vertical_keywords else None,
            client_vertical_keywords=vertical_keywords
        )
        db.add(keyword_list)
        db.commit()
        db.refresh(keyword_list)
    else:
        raise HTTPException(status_code=400, detail="Provide list_id or new_list_name")

    # Add keywords to list
    added = 0
    for sk in strategy_keywords:
        # Check if already exists
        exists = db.query(Keyword).filter(
            Keyword.keyword_list_id == keyword_list.id,
            Keyword.keyword == sk.query
        ).first()

        if not exists:
            kw = Keyword(
                keyword_list_id=keyword_list.id,
                keyword=sk.query,
                volume=sk.volume,
                target_url=sk.page_url
            )
            db.add(kw)
            added += 1

    db.commit()

    return {
        "message": f"Added {added} keywords to list",
        "list_id": keyword_list.id,
        "list_name": keyword_list.name
    }


# Topic Graph Data Endpoint
@router.get("/projects/{project_id}/topic-graph")
async def get_topic_graph_data(
    project_id: int,
    topic: str,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Get graph visualization data for a topic (team-wide access)."""
    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    keywords = db.query(StrategyKeyword).filter(
        StrategyKeyword.project_id == project_id,
        StrategyKeyword.assigned_topic == topic
    ).order_by(StrategyKeyword.clicks.desc()).limit(50).all()

    # Build nodes and edges for visualization
    nodes = []
    edges = []

    # Topic center node
    nodes.append({
        "id": "topic",
        "type": "topic",
        "label": topic,
        "x": 400,
        "y": 300
    })

    # Keyword nodes arranged in a circle
    import math
    for i, kw in enumerate(keywords):
        angle = (2 * math.pi * i) / len(keywords)
        radius = 250
        x = 400 + radius * math.cos(angle)
        y = 300 + radius * math.sin(angle)

        nodes.append({
            "id": f"kw-{kw.id}",
            "type": "keyword",
            "label": kw.query,
            "stage": kw.buyer_journey_stage,
            "color": buyer_journey_service.get_stage_color(kw.buyer_journey_stage),
            "clicks": kw.clicks,
            "x": x,
            "y": y
        })

        edges.append({
            "id": f"edge-{kw.id}",
            "source": "topic",
            "target": f"kw-{kw.id}",
            "weight": kw.topic_similarity or 0.5
        })

    return {
        "nodes": nodes,
        "edges": edges
    }


# Fetch Volumes Endpoint
@router.post("/projects/{project_id}/fetch-volumes")
async def fetch_project_volumes(
    project_id: int,
    keyword_ids: Optional[List[int]] = Query(default=None),
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Fetch search volumes for project keywords using Keywords Everywhere (team-wide access)."""
    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get keywords to update
    query = db.query(StrategyKeyword).filter(
        StrategyKeyword.project_id == project_id
    )

    if keyword_ids:
        query = query.filter(StrategyKeyword.id.in_(keyword_ids))
    else:
        # Only fetch for keywords without volume
        query = query.filter(StrategyKeyword.volume.is_(None))

    keywords = query.all()

    if not keywords:
        return {"message": "No keywords to update", "updated": 0}

    # Fetch volumes in batches
    keyword_texts = [kw.query for kw in keywords]
    print(f"Fetching volumes for {len(keyword_texts)} keywords...")

    try:
        volumes = await fetch_keyword_volumes(keyword_texts)
        print(f"Got volumes for {len(volumes)} keywords")

        # Update keywords with volumes
        updated = 0
        for kw in keywords:
            vol = volumes.get(kw.query.lower())
            if vol:
                kw.volume = vol
                updated += 1

        db.commit()

        return {
            "message": f"Updated {updated} keywords with volumes",
            "updated": updated,
            "total": len(keywords)
        }

    except Exception as e:
        print(f"Error fetching volumes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch volumes: {str(e)}")


# Delete Multiple Keywords
@router.post("/keywords/delete-bulk")
async def delete_keywords_bulk(
    keyword_ids: List[int] = Query(...),
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Delete multiple strategy keywords."""
    keywords = db.query(StrategyKeyword).filter(
        StrategyKeyword.id.in_(keyword_ids)
    ).all()

    if not keywords:
        raise HTTPException(status_code=404, detail="No keywords found")

    # Verify user owns all projects
    project_ids = set(kw.project_id for kw in keywords)
    projects = db.query(StrategyProject).filter(
        StrategyProject.id.in_(project_ids),
        StrategyProject.user_id == current_user.id
    ).all()

    if len(projects) != len(project_ids):
        raise HTTPException(status_code=403, detail="Access denied")

    # Delete keywords
    deleted = 0
    for kw in keywords:
        db.delete(kw)
        deleted += 1

    db.commit()

    return {"message": f"Deleted {deleted} keywords", "deleted": deleted}


# Funnel View Endpoints
@router.get("/projects/{project_id}/funnel")
async def get_funnel_data(
    project_id: int,
    topic: Optional[str] = None,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Get funnel visualization data for a topic or all topics (team-wide access)."""
    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Build query
    query = db.query(StrategyKeyword).filter(
        StrategyKeyword.project_id == project_id
    )

    if topic:
        query = query.filter(StrategyKeyword.assigned_topic == topic)

    keywords = query.order_by(StrategyKeyword.clicks.desc()).all()

    # Define stage order (top to bottom of funnel)
    stages = [
        "Trigger / Awareness",
        "Exploration / Consideration",
        "Narrowing / Evaluation",
        "Validation / Trust",
        "Decision / Action"
    ]

    # Group keywords by stage
    funnel_data = {}
    for stage in stages:
        stage_keywords = [kw for kw in keywords if kw.buyer_journey_stage == stage]

        total_volume = sum(kw.volume or 0 for kw in stage_keywords)
        total_clicks = sum(kw.clicks or 0 for kw in stage_keywords)
        avg_position = None
        if stage_keywords:
            positions = [kw.avg_position for kw in stage_keywords if kw.avg_position]
            if positions:
                avg_position = round(sum(positions) / len(positions), 1)

        funnel_data[stage] = {
            "stage": stage,
            "total_volume": total_volume,
            "total_clicks": total_clicks,
            "avg_position": avg_position,
            "keyword_count": len(stage_keywords),
            "keywords": [
                {
                    "id": kw.id,
                    "query": kw.query,
                    "page_url": kw.page_url,
                    "clicks": kw.clicks,
                    "impressions": kw.impressions,
                    "avg_position": kw.avg_position,
                    "volume": kw.volume,
                    "topic": kw.assigned_topic,
                    "is_ai_generated": kw.is_ai_generated if hasattr(kw, 'is_ai_generated') else False
                }
                for kw in stage_keywords
            ]
        }

    return {
        "project_id": project_id,
        "topic": topic,
        "stages": funnel_data
    }


class UpdateKeywordStageRequest(BaseModel):
    stage: str


@router.patch("/keywords/{keyword_id}/stage")
async def update_keyword_stage(
    keyword_id: int,
    request: UpdateKeywordStageRequest,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Move a keyword to a different buyer journey stage."""
    keyword = db.query(StrategyKeyword).filter(
        StrategyKeyword.id == keyword_id
    ).first()

    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")

    # Verify user owns the project
    project = db.query(StrategyProject).filter(
        StrategyProject.id == keyword.project_id,
        StrategyProject.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate stage
    valid_stages = [
        "Trigger / Awareness",
        "Exploration / Consideration",
        "Narrowing / Evaluation",
        "Validation / Trust",
        "Decision / Action"
    ]

    if request.stage not in valid_stages:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {valid_stages}")

    keyword.buyer_journey_stage = request.stage
    db.commit()

    return {"message": "Stage updated", "keyword_id": keyword_id, "new_stage": request.stage}


@router.delete("/keywords/{keyword_id}")
async def delete_strategy_keyword(
    keyword_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Delete a strategy keyword."""
    keyword = db.query(StrategyKeyword).filter(
        StrategyKeyword.id == keyword_id
    ).first()

    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")

    # Verify user owns the project
    project = db.query(StrategyProject).filter(
        StrategyProject.id == keyword.project_id,
        StrategyProject.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    db.delete(keyword)
    db.commit()

    return {"message": "Keyword deleted"}


class QueryFanningRequest(BaseModel):
    stage: str
    topic: str


@router.post("/projects/{project_id}/generate-queries")
async def generate_queries(
    project_id: int,
    request: QueryFanningRequest,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Generate AI-powered fan-out queries for a specific stage (owner or admin/master only)."""
    from app.services import query_fanning_service

    project = get_project_for_write(db, project_id, current_user)

    # Get existing queries in this stage for the topic
    existing = db.query(StrategyKeyword).filter(
        StrategyKeyword.project_id == project_id,
        StrategyKeyword.assigned_topic == request.topic,
        StrategyKeyword.buyer_journey_stage == request.stage
    ).all()

    existing_queries = [kw.query for kw in existing]

    try:
        # Generate new queries
        new_queries, reasoning = await query_fanning_service.generate_stage_queries(
            stage=request.stage,
            topic=request.topic,
            existing_queries=existing_queries,
            persona=project.persona
        )

        # Add new queries to the database
        added_keywords = []
        for query in new_queries:
            kw = StrategyKeyword(
                project_id=project_id,
                query=query,
                assigned_topic=request.topic,
                buyer_journey_stage=request.stage,
                is_ai_generated=True,
                clicks=0,
                impressions=0
            )
            db.add(kw)
            db.flush()
            added_keywords.append({
                "id": kw.id,
                "query": kw.query,
                "stage": kw.buyer_journey_stage,
                "topic": kw.assigned_topic,
                "is_ai_generated": True
            })

        db.commit()

        return {
            "message": f"Generated {len(added_keywords)} new queries",
            "reasoning": reasoning,
            "keywords": added_keywords
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate queries: {str(e)}")


@router.get("/projects/{project_id}/funnel/export-csv")
async def export_funnel_csv(
    project_id: int,
    topic: Optional[str] = None,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Export funnel data as CSV (team-wide access)."""
    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Build query
    query = db.query(StrategyKeyword).filter(
        StrategyKeyword.project_id == project_id
    )

    if topic:
        query = query.filter(StrategyKeyword.assigned_topic == topic)

    keywords = query.order_by(
        StrategyKeyword.buyer_journey_stage,
        StrategyKeyword.clicks.desc()
    ).all()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Journey Stage", "Query", "Page URL", "Topic",
        "Clicks", "Impressions", "Avg Position", "Volume", "AI Generated"
    ])

    for kw in keywords:
        writer.writerow([
            kw.buyer_journey_stage or "",
            kw.query,
            kw.page_url or "",
            kw.assigned_topic or "",
            kw.clicks,
            kw.impressions,
            round(kw.avg_position, 1) if kw.avg_position else "",
            kw.volume or "",
            "Yes" if getattr(kw, 'is_ai_generated', False) else "No"
        ])

    output.seek(0)
    filename = f"funnel_export_{topic or 'all'}.csv".replace(" ", "_").replace("/", "-")
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/projects/{project_id}/funnel/export-pdf")
async def export_funnel_pdf(
    project_id: int,
    topic: Optional[str] = None,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Export funnel data as PDF (team-wide access)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Build query
    query = db.query(StrategyKeyword).filter(
        StrategyKeyword.project_id == project_id
    )

    if topic:
        query = query.filter(StrategyKeyword.assigned_topic == topic)

    keywords = query.all()

    # Define stages
    stages = [
        "Trigger / Awareness",
        "Exploration / Consideration",
        "Narrowing / Evaluation",
        "Validation / Trust",
        "Decision / Action"
    ]

    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=20,
        alignment=TA_CENTER
    )
    elements.append(Paragraph(f"Buyer Journey Funnel: {topic or 'All Topics'}", title_style))
    elements.append(Paragraph(f"Project: {project.name}", styles['Normal']))
    elements.append(Spacer(1, 20))

    # Stage colors for funnel
    stage_colors = {
        "Trigger / Awareness": colors.Color(0.42, 0.45, 0.50),  # Gray
        "Exploration / Consideration": colors.Color(0.98, 0.45, 0.09),  # Orange
        "Narrowing / Evaluation": colors.Color(0.66, 0.33, 0.97),  # Purple
        "Validation / Trust": colors.Color(0.23, 0.51, 0.96),  # Blue
        "Decision / Action": colors.Color(0.13, 0.77, 0.37),  # Green
    }

    # Summary table
    summary_data = [["Stage", "Keywords", "Total Clicks", "Total Volume", "Avg Position"]]

    for stage in stages:
        stage_keywords = [kw for kw in keywords if kw.buyer_journey_stage == stage]
        total_clicks = sum(kw.clicks or 0 for kw in stage_keywords)
        total_volume = sum(kw.volume or 0 for kw in stage_keywords)
        positions = [kw.avg_position for kw in stage_keywords if kw.avg_position]
        avg_pos = round(sum(positions) / len(positions), 1) if positions else "-"

        summary_data.append([
            stage,
            len(stage_keywords),
            f"{total_clicks:,}",
            f"{total_volume:,}",
            avg_pos
        ])

    summary_table = Table(summary_data, colWidths=[2.5*inch, 1*inch, 1.2*inch, 1.2*inch, 1*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.13, 0.21, 0.25)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    # Add colored backgrounds for each stage row
    for i, stage in enumerate(stages):
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, i+1), (0, i+1), stage_colors.get(stage, colors.white)),
            ('TEXTCOLOR', (0, i+1), (0, i+1), colors.white),
        ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 30))

    # Detail tables for each stage
    for stage in stages:
        stage_keywords = [kw for kw in keywords if kw.buyer_journey_stage == stage]
        if not stage_keywords:
            continue

        # Stage header
        stage_style = ParagraphStyle(
            'StageHeader',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=10,
            textColor=colors.white,
            backColor=stage_colors.get(stage, colors.gray)
        )
        elements.append(Paragraph(f"  {stage} ({len(stage_keywords)} keywords)", stage_style))

        # Keywords table (top 15 by clicks)
        detail_data = [["Query", "Page URL", "Clicks", "Volume", "Avg Pos"]]
        for kw in sorted(stage_keywords, key=lambda x: x.clicks or 0, reverse=True)[:15]:
            query_text = kw.query[:50] + "..." if len(kw.query) > 50 else kw.query
            page_text = (kw.page_url or "")[:40] + "..." if kw.page_url and len(kw.page_url) > 40 else (kw.page_url or "-")
            ai_marker = " *" if getattr(kw, 'is_ai_generated', False) else ""
            detail_data.append([
                query_text + ai_marker,
                page_text,
                f"{kw.clicks:,}" if kw.clicks else "0",
                f"{kw.volume:,}" if kw.volume else "-",
                f"{kw.avg_position:.1f}" if kw.avg_position else "-"
            ])

        detail_table = Table(detail_data, colWidths=[3*inch, 3*inch, 0.8*inch, 0.8*inch, 0.7*inch])
        detail_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.9, 0.9, 0.9)),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(detail_table)
        elements.append(Spacer(1, 15))

    # Footer note
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("* AI-generated queries", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)

    filename = f"funnel_report_{topic or 'all'}.pdf".replace(" ", "_").replace("/", "-")
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/projects/{project_id}/stats")
async def get_project_stats(
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Get project stats: num_funnels, num_terms, num_briefs."""
    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    linked_lists = db.query(KeywordList).filter(KeywordList.project_id == project_id).all()
    num_funnels = len(project.core_topics) if project.core_topics else 0
    num_terms = sum(
        db.query(Keyword).filter(Keyword.keyword_list_id == kl.id).count()
        for kl in linked_lists
    )
    num_briefs = sum(
        db.query(Outline).join(Keyword).filter(Keyword.keyword_list_id == kl.id).count()
        for kl in linked_lists
    )

    return {
        "num_funnels": num_funnels,
        "num_terms": num_terms,
        "num_briefs": num_briefs
    }
