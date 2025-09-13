#!/usr/bin/env python3
"""
Database optimization script for Scottish Country Dance database.
Analyzes current indexes and suggests/creates optimizations.
"""

import sqlite3
import os
import sys
import time
from mcp_scddb_server import DB_PATH, q, q_one

def analyze_database():
    """Analyze current database structure and identify optimization opportunities"""
    print("=== DATABASE ANALYSIS ===")
    
    # Check existing indexes
    indexes = q("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY tbl_name, name")
    print(f"\nCurrent indexes ({len(indexes)} total):")
    current_tables = set()
    for idx in indexes:
        print(f"  {idx['tbl_name']}.{idx['name']}: {idx['sql']}")
        current_tables.add(idx['tbl_name'])
    
    # Check table structures for key tables
    key_tables = ['v_metaform', 'v_dance_has_token', 'v_dance_formations', 'dancespublicationsmap', 'publication']
    print(f"\nKey table structures:")
    for table in key_tables:
        try:
            schema = q(f"PRAGMA table_info({table})")
            print(f"\n{table}:")
            for col in schema:
                print(f"  {col['name']} ({col['type']}) {'PRIMARY KEY' if col['pk'] else ''}")
        except Exception as e:
            print(f"  Could not analyze {table}: {e}")

def create_optimizations():
    """Create database indexes and optimizations"""
    print("\n=== APPLYING OPTIMIZATIONS ===")
    
    optimizations = [
        # Index for formation token searches (biggest performance issue)
        {
            'name': 'idx_dance_has_token_dance_id',
            'sql': 'CREATE INDEX IF NOT EXISTS idx_dance_has_token_dance_id ON v_dance_has_token(dance_id)',
            'purpose': 'Speed up formation token JOIN operations'
        },
        {
            'name': 'idx_dance_has_token_formation_tokens', 
            'sql': 'CREATE INDEX IF NOT EXISTS idx_dance_has_token_formation_tokens ON v_dance_has_token(formation_tokens)',
            'purpose': 'Speed up formation token LIKE searches'
        },
        
        # Indexes for RSCDS filtering (second biggest issue)
        {
            'name': 'idx_dancespublicationsmap_dance_id',
            'sql': 'CREATE INDEX IF NOT EXISTS idx_dancespublicationsmap_dance_id ON dancespublicationsmap(dance_id)',
            'purpose': 'Speed up RSCDS publication lookups'
        },
        {
            'name': 'idx_dancespublicationsmap_publication_id',
            'sql': 'CREATE INDEX IF NOT EXISTS idx_dancespublicationsmap_publication_id ON dancespublicationsmap(publication_id)',
            'purpose': 'Speed up publication joins'
        },
        {
            'name': 'idx_publication_rscds',
            'sql': 'CREATE INDEX IF NOT EXISTS idx_publication_rscds ON publication(rscds)',
            'purpose': 'Speed up RSCDS filtering'
        },
        
        # Indexes for common search patterns
        {
            'name': 'idx_metaform_name',
            'sql': 'CREATE INDEX IF NOT EXISTS idx_metaform_name ON v_metaform(name COLLATE NOCASE)',
            'purpose': 'Speed up name searches (case-insensitive)'
        },
        {
            'name': 'idx_metaform_kind',
            'sql': 'CREATE INDEX IF NOT EXISTS idx_metaform_kind ON v_metaform(kind)',
            'purpose': 'Speed up dance type filtering'
        },
        {
            'name': 'idx_metaform_bars',
            'sql': 'CREATE INDEX IF NOT EXISTS idx_metaform_bars ON v_metaform(bars)',
            'purpose': 'Speed up bar count filtering'
        },
        
        # Composite indexes for common combined searches
        {
            'name': 'idx_metaform_kind_name',
            'sql': 'CREATE INDEX IF NOT EXISTS idx_metaform_kind_name ON v_metaform(kind, name COLLATE NOCASE)',
            'purpose': 'Speed up kind+name combined searches'
        },
        
        # Dance detail optimizations
        {
            'name': 'idx_dance_formations_dance_id',
            'sql': 'CREATE INDEX IF NOT EXISTS idx_dance_formations_dance_id ON v_dance_formations(dance_id)',
            'purpose': 'Speed up dance formations lookup'
        }
    ]
    
    con = sqlite3.connect(DB_PATH)
    try:
        successful_optimizations = []
        failed_optimizations = []
        
        for opt in optimizations:
            try:
                start_time = time.perf_counter()
                con.execute(opt['sql'])
                end_time = time.perf_counter()
                duration = (end_time - start_time) * 1000
                
                print(f"✓ Created {opt['name']} ({duration:.1f}ms)")
                print(f"  Purpose: {opt['purpose']}")
                successful_optimizations.append(opt)
                
            except Exception as e:
                print(f"✗ Failed to create {opt['name']}: {e}")
                failed_optimizations.append((opt, str(e)))
        
        con.commit()
        print(f"\nOptimization Summary:")
        print(f"  Successful: {len(successful_optimizations)}")
        print(f"  Failed: {len(failed_optimizations)}")
        
        if failed_optimizations:
            print("\nFailed optimizations:")
            for opt, error in failed_optimizations:
                print(f"  {opt['name']}: {error}")
        
    finally:
        con.close()

def run_performance_comparison():
    """Run a quick performance comparison of key queries"""
    print("\n=== PERFORMANCE COMPARISON ===")
    
    # Test the slowest queries from our benchmark
    test_queries = [
        {
            'name': 'formation_token_search',
            'sql': """
                SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression
                FROM v_metaform m
                LEFT JOIN v_dance_has_token t ON t.dance_id = m.id
                WHERE t.formation_tokens LIKE ?
                ORDER BY m.name LIMIT ?
            """,
            'args': ("%REEL;3P;%", 25)
        },
        {
            'name': 'rscds_filter_search',
            'sql': """
                SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression
                FROM v_metaform m
                INNER JOIN dancespublicationsmap dpm ON m.id = dpm.dance_id
                INNER JOIN publication p ON dpm.publication_id = p.id AND p.rscds = 1
                WHERE m.name LIKE ? COLLATE NOCASE
                ORDER BY m.name LIMIT ?
            """,
            'args': ("%reel%", 25)
        },
        {
            'name': 'basic_name_search',
            'sql': """
                SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression 
                FROM v_metaform m 
                WHERE m.name LIKE ? COLLATE NOCASE 
                ORDER BY m.name LIMIT ?
            """,
            'args': ("%reel%", 25)
        }
    ]
    
    for query in test_queries:
        try:
            # Run query 3 times and average
            times = []
            for _ in range(3):
                start = time.perf_counter()
                results = q(query['sql'], query['args'])
                end = time.perf_counter()
                times.append((end - start) * 1000)
            
            avg_time = sum(times) / len(times)
            print(f"{query['name']:25s}: {avg_time:7.2f}ms (was 491ms, 40ms, 25ms respectively)")
            
        except Exception as e:
            print(f"{query['name']:25s}: ERROR - {e}")

def analyze_query_plans():
    """Analyze query execution plans for key queries"""
    print("\n=== QUERY EXECUTION PLANS ===")
    
    queries_to_analyze = [
        {
            'name': 'Formation Token Search',
            'sql': """
                EXPLAIN QUERY PLAN
                SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression
                FROM v_metaform m
                LEFT JOIN v_dance_has_token t ON t.dance_id = m.id
                WHERE t.formation_tokens LIKE '%REEL;3P;%'
                ORDER BY m.name LIMIT 25
            """
        },
        {
            'name': 'RSCDS Filter Search', 
            'sql': """
                EXPLAIN QUERY PLAN
                SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression
                FROM v_metaform m
                INNER JOIN dancespublicationsmap dpm ON m.id = dpm.dance_id
                INNER JOIN publication p ON dpm.publication_id = p.id AND p.rscds = 1
                WHERE m.name LIKE '%reel%' COLLATE NOCASE
                ORDER BY m.name LIMIT 25
            """
        }
    ]
    
    for query in queries_to_analyze:
        print(f"\n{query['name']}:")
        try:
            plan = q(query['sql'])
            for step in plan:
                print(f"  {step}")
        except Exception as e:
            print(f"  ERROR: {e}")

def main():
    """Main optimization workflow"""
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        sys.exit(1)
    
    print(f"Optimizing database at: {DB_PATH}")
    
    # Backup recommendation
    backup_path = f"{DB_PATH}.backup"
    if not os.path.exists(backup_path):
        print(f"\n⚠️  RECOMMENDATION: Create a backup first:")
        print(f"   cp {DB_PATH} {backup_path}")
        
        if len(sys.argv) > 1 and sys.argv[1] != "--force":
            print("\nUse --force to skip this warning and proceed with optimizations.")
            sys.exit(1)
    
    analyze_database()
    create_optimizations()
    analyze_query_plans()
    run_performance_comparison()
    
    print(f"\n🎉 Database optimization complete!")
    print(f"   Run the performance test again to see improvements:")
    print(f"   uv run python test_query_performance.py")

if __name__ == "__main__":
    main()
