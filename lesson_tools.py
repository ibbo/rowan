#!/usr/bin/env python3
"""
Lesson planning tools for the Scottish Country Dance teaching assistant.

Provides tools for:
- Full crib extraction (untruncated)
- Teaching points lookup for dance formations
- Lesson plan assembly and export
- Lesson plan persistence
"""

import json
import re
import sqlite3
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

# Import shared components from dance_tools
from dance_tools import mcp_client, _get_manual_kb

# Lesson plan database path
LESSON_DB_PATH = "data/lesson_plans.db"


def init_lesson_db():
    """Initialize the lesson plans database."""
    Path("data").mkdir(exist_ok=True)
    conn = sqlite3.connect(LESSON_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lesson_plans (
            id TEXT PRIMARY KEY,
            browser_id TEXT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'draft',
            plan_data TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_lesson_plans_browser_id 
        ON lesson_plans(browser_id)
    """)
    
    conn.commit()
    conn.close()


# Initialize database on module load
init_lesson_db()


@tool
async def get_full_crib(dance_id: int) -> Dict[str, Any]:
    """
    Get the complete, untruncated crib for a dance.
    
    Unlike get_dance_detail which may truncate content, this returns
    the full crib text suitable for lesson planning and printing.
    
    Args:
        dance_id: The ID of the dance to get the crib for
    
    Returns:
        Dictionary with dance name, type, bars, and complete crib text
    """
    func_start = time.perf_counter()
    print(f"DEBUG: get_full_crib tool called for dance_id: {dance_id}", file=sys.stderr)
    
    await mcp_client.setup()
    
    result = await mcp_client.call_tool("dance_detail", {"dance_id": dance_id})
    
    if not result:
        return {"error": f"Dance with ID {dance_id} not found"}
    
    dance_data = result[0] if result else {}
    
    # Extract full crib - no truncation
    crib = dance_data.get("crib", "")
    
    func_end = time.perf_counter()
    total_time = (func_end - func_start) * 1000
    print(f"DEBUG: get_full_crib completed - {total_time:.2f}ms", file=sys.stderr)
    
    return {
        "dance_id": dance_id,
        "name": dance_data.get("name", "Unknown"),
        "kind": dance_data.get("kind", "Unknown"),
        "bars": dance_data.get("bars", 0),
        "couples": dance_data.get("couples", 0),
        "formation": dance_data.get("formation", "Unknown"),
        "crib": crib,
        "strathspey_link": f"https://my.strathspey.org/dd/dance/{dance_id}/"
    }


@tool
async def get_teaching_points_for_dance(dance_id: int) -> Dict[str, Any]:
    """
    Get teaching points from the RSCDS manual for formations used in a dance.
    
    Analyzes the dance's crib to identify formations (e.g., "allemande", 
    "poussette", "reel of three") and looks up the corresponding teaching 
    guidance from the RSCDS manual.
    
    Args:
        dance_id: The ID of the dance to analyze
    
    Returns:
        Dictionary with dance info and teaching points for each identified formation
    """
    func_start = time.perf_counter()
    print(f"DEBUG: get_teaching_points_for_dance called for dance_id: {dance_id}", file=sys.stderr)
    
    # First get the dance details
    await mcp_client.setup()
    result = await mcp_client.call_tool("dance_detail", {"dance_id": dance_id})
    
    if not result:
        return {"error": f"Dance with ID {dance_id} not found"}
    
    dance_data = result[0] if result else {}
    crib = dance_data.get("crib", "")
    
    # Get the manual knowledge base
    kb = _get_manual_kb()
    if kb is None or not kb._loaded:
        return {
            "dance_id": dance_id,
            "name": dance_data.get("name", "Unknown"),
            "error": "RSCDS manual knowledge base not available"
        }
    
    # Common formations to look for in cribs
    formation_patterns = [
        # Progression formations
        "allemande", "poussette", "promenade", "lead down", "cast off",
        # Chain formations
        "grand chain", "ladies' chain", "men's chain", "chain progression",
        # Setting/turning
        "set and turn", "turn corners", "set to corners",
        # Reels
        "reel of three", "reel of four", "mirror reel",
        # Circle formations
        "hands round", "hands across", "rights and lefts",
        # Other common formations
        "figure of eight", "double triangles", "petronella",
        "advance and retire", "back to back", "bourrel", "knot"
    ]
    
    # Find formations mentioned in the crib
    crib_lower = (crib or "").lower()
    found_formations = []
    teaching_points = []
    
    for formation in formation_patterns:
        if formation in crib_lower:
            found_formations.append(formation)
            
            # Look up in manual
            section = kb.lookup(formation)
            if section:
                teaching_points.append({
                    "formation": formation,
                    "section": section.get("section", ""),
                    "title": section.get("title", formation.title()),
                    "page": section.get("page", "N/A"),
                    "content": section.get("content", "")[:500],  # Preview for now
                    "has_teaching_points": "teaching_points" in section
                })
    
    func_end = time.perf_counter()
    total_time = (func_end - func_start) * 1000
    print(f"DEBUG: get_teaching_points_for_dance completed - {total_time:.2f}ms, found {len(found_formations)} formations", file=sys.stderr)
    
    return {
        "dance_id": dance_id,
        "name": dance_data.get("name", "Unknown"),
        "kind": dance_data.get("kind", "Unknown"),
        "bars": dance_data.get("bars", 0),
        "formations_found": found_formations,
        "teaching_points": teaching_points
    }


def format_lesson_plan_markdown(plan_data: Dict[str, Any]) -> str:
    """
    Format a lesson plan as Markdown for export.
    
    Args:
        plan_data: The lesson plan data dictionary
    
    Returns:
        Formatted Markdown string
    """
    lines = []
    
    # Header
    lines.append(f"# {plan_data.get('name', 'Lesson Plan')}")
    lines.append("")
    
    # Metadata
    if plan_data.get("date"):
        lines.append(f"**Date:** {plan_data['date']}")
    if plan_data.get("duration"):
        lines.append(f"**Duration:** {plan_data['duration']} minutes")
    if plan_data.get("level"):
        lines.append(f"**Level:** {plan_data['level']}")
    if plan_data.get("focus"):
        lines.append(f"**Focus:** {plan_data['focus']}")
    lines.append("")
    
    # Overview
    if plan_data.get("overview"):
        lines.append("## Overview")
        lines.append(plan_data["overview"])
        lines.append("")
    
    # Dances
    dances = plan_data.get("dances", [])
    if dances:
        lines.append("## Dance Programme")
        lines.append("")
        
        for i, dance in enumerate(dances, 1):
            lines.append(f"### {i}. {dance.get('name', 'Unknown Dance')}")
            lines.append("")
            
            # Dance metadata
            meta = []
            if dance.get("kind"):
                meta.append(dance["kind"])
            if dance.get("bars"):
                meta.append(f"{dance['bars']} bars")
            if dance.get("couples"):
                meta.append(f"{dance['couples']} couples")
            if dance.get("formation"):
                meta.append(dance["formation"])
            
            if meta:
                lines.append(f"*{' | '.join(meta)}*")
                lines.append("")
            
            # Link
            if dance.get("strathspey_link"):
                lines.append(f"[View on Strathspey Server]({dance['strathspey_link']})")
                lines.append("")
            
            # Crib
            if dance.get("crib"):
                lines.append("#### Crib")
                lines.append("")
                lines.append(dance["crib"])
                lines.append("")
            
            # Teaching points
            if dance.get("teaching_points"):
                lines.append("#### Teaching Points")
                lines.append("")
                for tp in dance["teaching_points"]:
                    lines.append(f"**{tp.get('title', tp.get('formation', ''))}** (p. {tp.get('page', 'N/A')})")
                    if tp.get("content"):
                        lines.append(f"> {tp['content'][:300]}...")
                    lines.append("")
            
            lines.append("---")
            lines.append("")
    
    # Notes
    if plan_data.get("notes"):
        lines.append("## Notes")
        lines.append(plan_data["notes"])
        lines.append("")
    
    # Footer
    lines.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    
    return "\n".join(lines)


@tool
def export_lesson_plan(plan_id: str, format: str = "markdown") -> Dict[str, Any]:
    """
    Export a lesson plan to a downloadable format.
    
    Args:
        plan_id: ID of the lesson plan to export
        format: Export format - currently only "markdown" is supported
    
    Returns:
        Dictionary with export status and content/file path
    """
    print(f"DEBUG: export_lesson_plan called for plan_id: {plan_id}", file=sys.stderr)
    
    if format.lower() != "markdown":
        return {"error": f"Unsupported format: {format}. Only 'markdown' is currently supported."}
    
    conn = sqlite3.connect(LESSON_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT plan_data, name FROM lesson_plans WHERE id = ?", (plan_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return {"error": f"Lesson plan {plan_id} not found"}
    
    plan_data = json.loads(row[0])
    plan_name = row[1]
    
    # Generate markdown content
    markdown_content = format_lesson_plan_markdown(plan_data)
    
    # Create export filename
    safe_name = re.sub(r'[^\w\s-]', '', plan_name).strip().replace(' ', '_')
    filename = f"lesson_plan_{safe_name}_{datetime.now().strftime('%Y%m%d')}.md"
    
    return {
        "success": True,
        "format": "markdown",
        "filename": filename,
        "content": markdown_content
    }


@tool
def save_lesson_plan(
    name: str,
    plan_data: Dict[str, Any],
    browser_id: Optional[str] = None,
    plan_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Save a lesson plan to the database.
    
    Args:
        name: Name for the lesson plan
        plan_data: The lesson plan data (dances, teaching points, etc.)
        browser_id: Optional browser session ID for session-based access
        plan_id: Optional existing plan ID to update (creates new if not provided)
    
    Returns:
        Dictionary with saved plan ID and status
    """
    print(f"DEBUG: save_lesson_plan called for name: {name}", file=sys.stderr)
    
    conn = sqlite3.connect(LESSON_DB_PATH)
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    plan_data_json = json.dumps(plan_data)
    
    if plan_id:
        # Update existing plan
        cursor.execute("""
            UPDATE lesson_plans 
            SET name = ?, plan_data = ?, updated_at = ?, status = 'draft'
            WHERE id = ?
        """, (name, plan_data_json, now, plan_id))
        
        if cursor.rowcount == 0:
            conn.close()
            return {"error": f"Plan {plan_id} not found"}
    else:
        # Create new plan
        plan_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO lesson_plans (id, browser_id, name, plan_data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (plan_id, browser_id, name, plan_data_json, now, now))
    
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "plan_id": plan_id,
        "name": name,
        "saved_at": now
    }


@tool
def load_lesson_plan(plan_id: str) -> Dict[str, Any]:
    """
    Load a previously saved lesson plan.
    
    Args:
        plan_id: ID of the lesson plan to load
    
    Returns:
        Dictionary with the lesson plan data
    """
    print(f"DEBUG: load_lesson_plan called for plan_id: {plan_id}", file=sys.stderr)
    
    conn = sqlite3.connect(LESSON_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, browser_id, name, created_at, updated_at, status, plan_data
        FROM lesson_plans WHERE id = ?
    """, (plan_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return {"error": f"Lesson plan {plan_id} not found"}
    
    return {
        "id": row[0],
        "browser_id": row[1],
        "name": row[2],
        "created_at": row[3],
        "updated_at": row[4],
        "status": row[5],
        "plan_data": json.loads(row[6])
    }


@tool
def list_lesson_plans(browser_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """
    List saved lesson plans, optionally filtered by browser session.
    
    Args:
        browser_id: Optional browser session ID to filter by
        limit: Maximum number of plans to return (default 20)
    
    Returns:
        List of lesson plan summaries
    """
    print(f"DEBUG: list_lesson_plans called, browser_id: {browser_id}", file=sys.stderr)
    
    conn = sqlite3.connect(LESSON_DB_PATH)
    cursor = conn.cursor()
    
    if browser_id:
        cursor.execute("""
            SELECT id, name, created_at, updated_at, status
            FROM lesson_plans 
            WHERE browser_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
        """, (browser_id, limit))
    else:
        cursor.execute("""
            SELECT id, name, created_at, updated_at, status
            FROM lesson_plans 
            ORDER BY updated_at DESC
            LIMIT ?
        """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": row[0],
            "name": row[1],
            "created_at": row[2],
            "updated_at": row[3],
            "status": row[4]
        }
        for row in rows
    ]


@tool
def delete_lesson_plan(plan_id: str) -> Dict[str, Any]:
    """
    Delete a lesson plan.
    
    Args:
        plan_id: ID of the lesson plan to delete
    
    Returns:
        Dictionary with deletion status
    """
    print(f"DEBUG: delete_lesson_plan called for plan_id: {plan_id}", file=sys.stderr)
    
    conn = sqlite3.connect(LESSON_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM lesson_plans WHERE id = ?", (plan_id,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    if deleted:
        return {"success": True, "message": f"Lesson plan {plan_id} deleted"}
    else:
        return {"error": f"Lesson plan {plan_id} not found"}


# Export all tools for use by the lesson planner agent
lesson_planning_tools = [
    get_full_crib,
    get_teaching_points_for_dance,
    export_lesson_plan,
    save_lesson_plan,
    load_lesson_plan,
    list_lesson_plans,
    delete_lesson_plan,
]
