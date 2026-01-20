"""
Google Search Console Service

Handles OAuth2 authentication and data fetching from Google Search Console.
"""
import httpx
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode

from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI


# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GSC_API_BASE = "https://www.googleapis.com/webmasters/v3"

# Scopes needed
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def get_auth_url(state: str = "") -> str:
    """
    Generate OAuth2 authorization URL for Google Search Console.

    Args:
        state: Optional state parameter for CSRF protection

    Returns:
        URL to redirect user to for authentication
    """
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",  # Get refresh token
        "prompt": "consent",  # Force consent to get refresh token
        "state": state
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> Dict:
    """
    Exchange authorization code for access and refresh tokens.

    Args:
        code: Authorization code from OAuth callback

    Returns:
        Dict with access_token, refresh_token, expires_in
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": GOOGLE_REDIRECT_URI
            }
        )
        response.raise_for_status()
        return response.json()


async def refresh_access_token(refresh_token: str) -> Dict:
    """
    Get a new access token using a refresh token.

    Args:
        refresh_token: The stored refresh token

    Returns:
        Dict with access_token, expires_in
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }
        )
        response.raise_for_status()
        return response.json()


async def list_sites(access_token: str) -> List[Dict]:
    """
    List all sites the user has access to in Search Console.

    Args:
        access_token: Valid access token

    Returns:
        List of site entries with siteUrl and permissionLevel
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GSC_API_BASE}/sites",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        data = response.json()
        return data.get("siteEntry", [])


async def fetch_search_data(
    access_token: str,
    site_url: str,
    days: int = 90,
    row_limit: int = 25000
) -> List[Dict]:
    """
    Fetch search analytics data from GSC.

    Args:
        access_token: Valid access token
        site_url: The property URL (e.g., "sc-domain:example.com")
        days: Number of days to look back (default 90)
        row_limit: Maximum rows to return (default 25000)

    Returns:
        List of rows with query, page, clicks, impressions, position
    """
    end_date = datetime.now() - timedelta(days=3)  # GSC has 3-day delay
    start_date = end_date - timedelta(days=days)

    request_body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "dimensions": ["query", "page"],
        "rowLimit": row_limit,
        "startRow": 0
    }

    all_rows = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            response = await client.post(
                f"{GSC_API_BASE}/sites/{site_url}/searchAnalytics/query",
                headers={"Authorization": f"Bearer {access_token}"},
                json=request_body
            )
            response.raise_for_status()
            data = response.json()

            rows = data.get("rows", [])
            if not rows:
                break

            # Transform rows
            for row in rows:
                keys = row.get("keys", [])
                all_rows.append({
                    "query": keys[0] if len(keys) > 0 else "",
                    "page_url": keys[1] if len(keys) > 1 else "",
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "avg_position": row.get("position", 0)
                })

            # Check if there are more rows
            if len(rows) < row_limit:
                break

            request_body["startRow"] = request_body["startRow"] + row_limit

    return all_rows


async def fetch_with_refresh(
    refresh_token: str,
    site_url: str,
    days: int = 90
) -> Tuple[List[Dict], str]:
    """
    Fetch search data, refreshing the access token first.

    Args:
        refresh_token: Stored refresh token
        site_url: Property URL
        days: Days to look back

    Returns:
        Tuple of (data_rows, new_access_token)
    """
    # Get fresh access token
    token_data = await refresh_access_token(refresh_token)
    access_token = token_data["access_token"]

    # Fetch data
    rows = await fetch_search_data(access_token, site_url, days)

    return rows, access_token


def is_configured() -> bool:
    """Check if Google OAuth is configured."""
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
