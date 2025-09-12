#!/usr/bin/env python3
"""
Test script to verify RSCDS filtering functionality
"""
import sqlite3
import os
import json
from typing import Dict, Any, List

# Database helper functions (copied from mcp_scddb_server.py)
DB_PATH = os.environ.get("SCDDB_SQLITE", "data/scddb/scddb.sqlite")

def q(sql: str, args: tuple = ()) -> List[Dict[str, Any]]:
    con = sqlite3.connect(DB_PATH)
    try:
        con.row_factory = sqlite3.Row
        cur = con.execute(sql, args)
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()

def test_rscds_queries():
    """Test the SQL queries that will be used in the MCP server"""
    
    print("=== Testing RSCDS Filter Queries ===\n")
    
    # Test 1: Get dances that are ONLY published by RSCDS
    print("1. Testing RSCDS-only dances (rscds_only=True):")
    sql_rscds_only = """
    SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression
    FROM v_metaform m
    LEFT JOIN v_dance_has_token t ON t.dance_id = m.id
    INNER JOIN dancespublicationsmap dpm ON m.id = dpm.dance_id
    INNER JOIN publication p ON dpm.publication_id = p.id AND p.rscds = 1
    WHERE m.name LIKE '%Reel%' COLLATE NOCASE
    ORDER BY m.name LIMIT 5
    """
    
    rscds_dances = q(sql_rscds_only)
    for dance in rscds_dances:
        print(f"  - {dance['name']} (ID: {dance['id']}, {dance['kind']}, {dance['bars']} bars)")
    print(f"Found {len(rscds_dances)} RSCDS dances with 'Reel' in name\n")
    
    # Test 2: Get dances that are NOT published by RSCDS
    print("2. Testing non-RSCDS dances (rscds_only=False):")
    sql_non_rscds = """
    SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression
    FROM v_metaform m
    LEFT JOIN v_dance_has_token t ON t.dance_id = m.id
    WHERE m.id NOT IN (
        SELECT DISTINCT dpm2.dance_id 
        FROM dancespublicationsmap dpm2
        INNER JOIN publication p2 ON dpm2.publication_id = p2.id AND p2.rscds = 1
    )
    AND m.name LIKE '%Reel%' COLLATE NOCASE
    ORDER BY m.name LIMIT 5
    """
    
    non_rscds_dances = q(sql_non_rscds)
    for dance in non_rscds_dances:
        print(f"  - {dance['name']} (ID: {dance['id']}, {dance['kind']}, {dance['bars']} bars)")
    print(f"Found {len(non_rscds_dances)} non-RSCDS dances with 'Reel' in name\n")
    
    # Test 3: Verify publication details for a specific dance
    if rscds_dances:
        dance_id = rscds_dances[0]['id']
        print(f"3. Testing publication details for '{rscds_dances[0]['name']}' (ID: {dance_id}):")
        
        publications = q("""
            SELECT p.name, p.shortname, p.rscds, dpm.number, dpm.page
            FROM publication p
            JOIN dancespublicationsmap dpm ON p.id = dpm.publication_id
            WHERE dpm.dance_id = ?
            ORDER BY p.rscds DESC, p.name
        """, (dance_id,))
        
        for pub in publications:
            rscds_flag = "✓ RSCDS" if pub['rscds'] else "✗ Non-RSCDS"
            print(f"  - {pub['shortname']}: {pub['name']} ({rscds_flag}) - ##{pub['number']}, p.{pub['page']}")
    
    # Test 4: Count totals
    print(f"\n4. Summary counts:")
    
    total_dances = q("SELECT COUNT(*) as count FROM dance")[0]['count']
    print(f"Total dances in database: {total_dances}")
    
    rscds_count = q("""
        SELECT COUNT(DISTINCT dpm.dance_id) as count
        FROM dancespublicationsmap dpm
        INNER JOIN publication p ON dpm.publication_id = p.id AND p.rscds = 1
    """)[0]['count']
    print(f"Dances with RSCDS publications: {rscds_count}")
    
    non_rscds_count = q("""
        SELECT COUNT(*) as count FROM dance d
        WHERE d.id NOT IN (
            SELECT DISTINCT dpm2.dance_id 
            FROM dancespublicationsmap dpm2
            INNER JOIN publication p2 ON dpm2.publication_id = p2.id AND p2.rscds = 1
        )
    """)[0]['count']
    print(f"Dances with only non-RSCDS publications: {non_rscds_count}")
    
    print(f"Dances with both RSCDS and non-RSCDS publications: {rscds_count + non_rscds_count - total_dances}")

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        print("Make sure to run refresh_scddb.py first or set SCDDB_SQLITE environment variable")
        exit(1)
    
    test_rscds_queries()
