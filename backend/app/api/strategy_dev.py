"""
Strategy Development API Routes

Handles projects, GSC integration, topic classification, and buyer journey analysis.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import csv
import io
from datetime import datetime

from app.database import get_db
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


# Sync Endpoint
@router.post("/projects/{project_id}/sync")
async def sync_project(
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Sync GSC data, classify keywords, and fetch volumes.
    This is the main action that pulls everything together.
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

    try:
        print(f"Starting sync for project {project_id}...")

        # Fetch GSC data
        print("Fetching GSC data...")
        rows, _ = await gsc_service.fetch_with_refresh(
            project.gsc_refresh_token,
            project.gsc_property_url,
            days=90
        )
        print(f"Fetched {len(rows)} rows from GSC")

        if not rows:
            return {"message": "No data found in GSC", "keywords_added": 0}

        # Clear existing keywords
        db.query(StrategyKeyword).filter(
            StrategyKeyword.project_id == project_id
        ).delete()

        # Classify keywords by topic
        queries = [r["query"] for r in rows]
        topics = project.core_topics or []

        print(f"Classifying {len(queries)} keywords...")
        topic_results = topic_service.classify_keywords_batch(
            queries, topics, threshold=TOPIC_SIMILARITY_THRESHOLD
        )
        print("Topic classification complete")

        # Create lookup for topic assignments
        topic_lookup = {r["keyword"]: r for r in topic_results}

        # Add keywords with classifications
        keywords_added = 0
        queries_for_volume = []

        for row in rows:
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
            queries_for_volume.append(query)

        db.commit()

        # Fetch volumes from Keywords Everywhere
        volume_data = {}
        if queries_for_volume:
            try:
                volume_data = await fetch_keyword_volumes(queries_for_volume)
            except Exception as e:
                print(f"Volume fetch error: {e}")

        # Update volumes
        if volume_data:
            keywords = db.query(StrategyKeyword).filter(
                StrategyKeyword.project_id == project_id
            ).all()

            for kw in keywords:
                if kw.query in volume_data:
                    kw.volume = volume_data[kw.query]

            db.commit()

        return {
            "message": "Sync complete",
            "keywords_added": keywords_added,
            "volumes_fetched": len(volume_data)
        }

    except Exception as e:
        import traceback
        print(f"Sync error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


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
