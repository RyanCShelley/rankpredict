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
from app.models.database import StrategyProject, StrategyKeyword, User, KeywordList, Keyword
from app.api.auth import get_current_user_from_token
from app.services import gsc_service, topic_service, buyer_journey_service
from app.services.keywords_everywhere_service import fetch_keyword_volumes
from app.config import TOPIC_SIMILARITY_THRESHOLD


router = APIRouter()


# Request/Response Models
class TopicInput(BaseModel):
    name: str
    keywords: List[str]


class CreateProjectRequest(BaseModel):
    name: str
    core_topics: Optional[List[TopicInput]] = None


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    core_topics: Optional[List[TopicInput]] = None
    gsc_property_url: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    gsc_property_url: Optional[str]
    gsc_connected: bool
    core_topics: Optional[List[dict]]
    keyword_count: int
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
    """List all strategy projects for the current user."""
    projects = db.query(StrategyProject).filter(
        StrategyProject.user_id == current_user.id
    ).order_by(StrategyProject.updated_at.desc()).all()

    return [
        ProjectResponse(
            id=p.id,
            name=p.name,
            gsc_property_url=p.gsc_property_url,
            gsc_connected=bool(p.gsc_refresh_token),
            core_topics=p.core_topics,
            keyword_count=len(p.keywords),
            sync_status=p.sync_status,
            sync_message=p.sync_message,
            created_at=p.created_at,
            updated_at=p.updated_at
        )
        for p in projects
    ]


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
            user_id=current_user.id,
            core_topics=topics_data
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        return {
            "id": project.id,
            "name": project.name,
            "gsc_property_url": project.gsc_property_url,
            "gsc_connected": bool(project.gsc_refresh_token),
            "core_topics": project.core_topics,
            "keyword_count": 0,
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
    """Get project details with keywords."""
    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id,
        StrategyProject.user_id == current_user.id
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
            gsc_property_url=project.gsc_property_url,
            gsc_connected=bool(project.gsc_refresh_token),
            core_topics=project.core_topics,
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
    """Update project settings."""
    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id,
        StrategyProject.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if request.name is not None:
        project.name = request.name

    if request.core_topics is not None:
        project.core_topics = [t.model_dump() for t in request.core_topics]

    if request.gsc_property_url is not None:
        project.gsc_property_url = request.gsc_property_url

    db.commit()
    db.refresh(project)

    return ProjectResponse(
        id=project.id,
        name=project.name,
        gsc_property_url=project.gsc_property_url,
        gsc_connected=bool(project.gsc_refresh_token),
        core_topics=project.core_topics,
        keyword_count=len(project.keywords),
        sync_status=project.sync_status,
        sync_message=project.sync_message,
        created_at=project.created_at,
        updated_at=project.updated_at
    )


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Delete a project and all its keywords."""
    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id,
        StrategyProject.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

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

        # Return HTML that closes the popup and notifies parent
        return """
        <html>
        <body>
        <script>
            if (window.opener) {
                window.opener.postMessage({type: 'GSC_AUTH_SUCCESS'}, '*');
                window.close();
            } else {
                document.body.innerHTML = '<h2>Connected! You can close this window.</h2>';
            }
        </script>
        </body>
        </html>
        """
    except Exception as e:
        return f"""
        <html>
        <body>
        <h2>Error connecting to Google Search Console</h2>
        <p>{str(e)}</p>
        </body>
        </html>
        """


@router.get("/gsc/sites", response_model=List[GscSiteResponse])
async def list_gsc_sites(
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """List available GSC sites for a connected project."""
    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id,
        StrategyProject.user_id == current_user.id
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

        # Limit total rows to prevent memory issues (max 5,000)
        MAX_KEYWORDS = 5000
        if len(rows) > MAX_KEYWORDS:
            rows = sorted(rows, key=lambda x: x.get("clicks", 0), reverse=True)[:MAX_KEYWORDS]
            print(f"[Background] Limited to top {MAX_KEYWORDS} keywords by clicks")

        # Clear existing keywords
        db.query(StrategyKeyword).filter(
            StrategyKeyword.project_id == project_id
        ).delete()
        db.commit()

        # Classify keywords by topic (only if topics defined)
        queries = [r["query"] for r in rows]
        topics = core_topics or []
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
        else:
            print("[Background] No topics defined, skipping topic classification")

        del queries

        # Update status
        project = db.query(StrategyProject).filter(StrategyProject.id == project_id).first()
        if project:
            project.sync_message = "Saving keywords to database..."
            db.commit()

        # Add keywords with classifications
        keywords_added = 0
        BATCH_SIZE = 200

        for i, row in enumerate(rows):
            query = row["query"]
            topic_data = topic_lookup.get(query, {})

            # Only add if passes topic threshold (if topics defined)
            if topics and topic_data.get("assigned_topic") is None:
                continue

            # Classify buyer journey
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

        # Update status to complete
        project = db.query(StrategyProject).filter(StrategyProject.id == project_id).first()
        if project:
            project.sync_status = "complete"
            project.sync_message = f"Sync complete. Added {keywords_added} keywords."
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
    Start a background sync of GSC data.
    Returns immediately while sync runs in background.
    Check project.sync_status to monitor progress.
    """
    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id,
        StrategyProject.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

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
    """Export selected keywords to CSV."""
    keywords = db.query(StrategyKeyword).filter(
        StrategyKeyword.id.in_(keyword_ids)
    ).all()

    if not keywords:
        raise HTTPException(status_code=404, detail="No keywords found")

    # Verify user owns the project
    project_ids = set(kw.project_id for kw in keywords)
    projects = db.query(StrategyProject).filter(
        StrategyProject.id.in_(project_ids),
        StrategyProject.user_id == current_user.id
    ).all()

    if len(projects) != len(project_ids):
        raise HTTPException(status_code=403, detail="Access denied")

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

    # Get or create list
    if request.list_id:
        keyword_list = db.query(KeywordList).filter(
            KeywordList.id == request.list_id
        ).first()
        if not keyword_list:
            raise HTTPException(status_code=404, detail="List not found")
    elif request.new_list_name:
        if not request.target_domain_url:
            raise HTTPException(status_code=400, detail="Target domain required for new list")
        keyword_list = KeywordList(
            name=request.new_list_name,
            target_domain_url=request.target_domain_url
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
                volume=sk.volume
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
    """Get graph visualization data for a topic."""
    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id,
        StrategyProject.user_id == current_user.id
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


# Funnel View Endpoints
@router.get("/projects/{project_id}/funnel")
async def get_funnel_data(
    project_id: int,
    topic: Optional[str] = None,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Get funnel visualization data for a topic or all topics."""
    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id,
        StrategyProject.user_id == current_user.id
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
    """Generate AI-powered fan-out queries for a specific stage."""
    from app.services import query_fanning_service

    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id,
        StrategyProject.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

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
            existing_queries=existing_queries
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
    """Export funnel data as CSV."""
    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id,
        StrategyProject.user_id == current_user.id
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
    """Export funnel data as PDF."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    project = db.query(StrategyProject).filter(
        StrategyProject.id == project_id,
        StrategyProject.user_id == current_user.id
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
