"""
Lyfta MCP Server
-----------------
Wraps the Lyfta workout-tracker REST API (https://my.lyfta.app/community/api)
as an MCP server so Claude can read and write your Lyfta data.

Run locally (stdio, for testing with the MCP inspector):
    python server.py

Run as a remote HTTP server (for Claude custom connectors):
    python server.py --http

Environment variables:
    LYFTA_API_KEY   Required. Your Lyfta API key (Community > API Access > Generate API Key).
    PORT            Optional. Port for HTTP mode (default 8000, Railway sets this automatically).
"""

import os
import sys
import json
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

BASE_URL = "https://my.lyfta.app"
API_KEY = os.environ.get("LYFTA_API_KEY")

# Your Render deployment's public hostname. Render's RENDER_EXTERNAL_HOSTNAME
# env var isn't reliably available on all plans, so this is set explicitly
# here (and overridable via ALLOWED_HOST if you ever change domains/redeploy
# under a different service name).
ALLOWED_HOST = os.environ.get("ALLOWED_HOST", "lyfta-mcp-9vtt.onrender.com")

if not API_KEY:
    print("ERROR: LYFTA_API_KEY environment variable is not set.", file=sys.stderr)
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {API_KEY}"}

allowed_hosts = ["localhost:*", "127.0.0.1:*", ALLOWED_HOST, f"{ALLOWED_HOST}:*"]
allowed_origins = [
    "http://localhost:*",
    "http://127.0.0.1:*",
    f"https://{ALLOWED_HOST}",
    f"https://{ALLOWED_HOST}:*",
]

print(f"[startup] ALLOWED_HOST={ALLOWED_HOST!r}", file=sys.stderr)
print(f"[startup] allowed_hosts={allowed_hosts}", file=sys.stderr)

mcp = FastMCP(
    "lyfta",
    host="0.0.0.0",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    ),
)

mcp = FastMCP(
    "lyfta",
    host="0.0.0.0",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    ),
)


async def _get(path: str, params: Optional[dict] = None) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{BASE_URL}{path}", headers=HEADERS, params=params or {})
        resp.raise_for_status()
        return resp.json()


async def _post(path: str, payload: dict) -> dict:
    headers = {**HEADERS, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{BASE_URL}{path}", headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_workouts(limit: int = 10, page: int = 1) -> str:
    """Get a list of your logged workouts with full exercise/set detail.

    Args:
        limit: Max workouts per page (capped at 100 by the API).
        page: Page number, starting at 1.
    """
    data = await _get("/api/v1/workouts", {"limit": limit, "page": page})
    return json.dumps(data, indent=2)


@mcp.tool()
async def get_workouts_summary(limit: int = 50, page: int = 1) -> str:
    """Get a lightweight list of workout summaries (title, duration, volume,
    date) without exercise/set detail. Good for quick history scans, up to
    1000 records per call.

    Args:
        limit: Max summaries to return (up to 1000).
        page: Page number, starting at 1.
    """
    data = await _get("/api/v1/workouts/summary", {"limit": limit, "page": page})
    return json.dumps(data, indent=2)


@mcp.tool()
async def get_exercises(limit: int = 10, page: int = 1) -> str:
    """Get a list of exercises you have actually performed (from your logged
    workouts), including muscle/equipment IDs.

    Args:
        limit: Max exercises to return.
        page: Page number, starting at 1.
    """
    data = await _get("/api/v1/exercises", {"limit": limit, "page": page})
    return json.dumps(data, indent=2)


@mcp.tool()
async def search_exercise_library(search: str = "", limit: int = 10, offset: int = 0) -> str:
    """Search Lyfta's full exercise catalog (not just what you've performed)
    by name, e.g. to find an exercise's catalog ID before adding it to a
    new template.

    Args:
        search: Search text, e.g. "bench press". Leave blank to browse.
        limit: Max results to return.
        offset: Zero-based offset for pagination.
    """
    data = await _get(
        "/api/v1/exercises/library",
        {"search": search, "limit": limit, "offset": offset},
    )
    return json.dumps(data, indent=2)


@mcp.tool()
async def get_exercise_progress(exercise_id: int, duration: int = 365) -> str:
    """Get progress history (best weight, reps, volume, estimated 1RM) for a
    specific exercise over time.

    Args:
        exercise_id: The exercise's ID (from get_exercises or search_exercise_library).
        duration: Number of days of history to include (e.g. 365 for one year).
    """
    data = await _get(
        "/api/v1/exercises/progress",
        {"exercise_id": exercise_id, "duration": duration},
    )
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def create_collection(title: str, description: str = "", goal: str = "") -> str:
    """Create a new program/collection in your Lyfta library. This is a
    WRITE action -- confirm with the user before calling.

    Args:
        title: Program title (required, non-empty).
        description: Optional program description.
        goal: Optional goal, e.g. "strength" or "hypertrophy".
    """
    payload = {
        "collection": {
            "title": title,
            "description": description,
            "goal": goal,
        }
    }
    data = await _post("/api/v1/collections", payload)
    return json.dumps(data, indent=2)


@mcp.tool()
async def create_template(
    collection_id: int,
    title: str = "",
    description: str = "",
    exercises_json: str = "[]",
) -> str:
    """Create a workout template and append it to an existing collection.
    This is a WRITE action -- confirm with the user before calling.

    Args:
        collection_id: ID of an existing collection (from create_collection
            or by asking the user).
        title: Template name, e.g. "Push day".
        description: Optional template description.
        exercises_json: JSON-encoded list of exercise objects. Each item
            needs exercise_id, excercise_name, exercise_type, and a sets
            list, all matching values from get_exercises or
            search_exercise_library. Example:
            '[{"exercise_id": 123, "excercise_name": "Bench Press",
            "exercise_type": "weight_reps", "sets": [{"reps": "10",
            "weight": "60"}]}]'
    """
    try:
        exercises = json.loads(exercises_json)
    except json.JSONDecodeError as e:
        return json.dumps({"status": False, "message": f"Invalid exercises_json: {e}"})

    payload = {
        "collectionId": collection_id,
        "workout": {
            "title": title,
            "description": description,
            "exercises": exercises,
        },
    }
    data = await _post("/api/v1/templates", payload)
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--http" in sys.argv:
        # Remote/HTTP mode for Claude custom connectors (e.g. deployed on Railway).
        port = int(os.environ.get("PORT", 8000))
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = port
        mcp.run(transport="streamable-http")
    else:
        # Local stdio mode, e.g. for testing with `npx @modelcontextprotocol/inspector`.
        mcp.run(transport="stdio")
