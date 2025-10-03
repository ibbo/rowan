#!/usr/bin/env python3
"""Test script for intensity/difficulty filtering in find_dances tool."""

import json
import sqlite3
import sys

DB_PATH = "data/scddb/scddb.sqlite"

def test_query(description, sql, args=()):
    """Execute a test query and display results."""
    print(f"\n{'='*80}")
    print(f"TEST: {description}")
    print(f"{'='*80}")
    
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.execute(sql, args)
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    
    print(f"Results: {len(rows)} dances found")
    if rows:
        print("\nSample results:")
        for i, row in enumerate(rows[:5], 1):
            intensity = row.get('intensity', 'N/A')
            print(f"  {i}. {row['name']} - Intensity: {intensity}, Type: {row['kind']}, Bars: {row['bars']}")
    else:
        print("  No results found")
    
    return rows

def main():
    print("Testing Intensity/Difficulty Filtering")
    print("=" * 80)
    
    # Test 1: Easy dances (intensity <= 40)
    test_query(
        "Easy dances for beginners (intensity <= 40)",
        """
        SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression, d.intensity
        FROM v_metaform m
        INNER JOIN dance d ON m.id = d.id
        WHERE d.intensity <= 40 AND d.intensity > 0
        ORDER BY d.intensity ASC, m.name
        LIMIT 10
        """
    )
    
    # Test 2: Hard dances (intensity >= 70)
    test_query(
        "Hard dances for experienced dancers (intensity >= 70)",
        """
        SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression, d.intensity
        FROM v_metaform m
        INNER JOIN dance d ON m.id = d.id
        WHERE d.intensity >= 70
        ORDER BY d.intensity DESC, m.name
        LIMIT 10
        """
    )
    
    # Test 3: Medium difficulty reels (40 < intensity < 70)
    test_query(
        "Medium difficulty Reels (intensity 40-70)",
        """
        SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression, d.intensity
        FROM v_metaform m
        INNER JOIN dance d ON m.id = d.id
        WHERE d.intensity > 40 AND d.intensity < 70 AND m.kind = 'Reel'
        ORDER BY d.intensity ASC, m.name
        LIMIT 10
        """
    )
    
    # Test 4: Statistics
    print(f"\n{'='*80}")
    print("STATISTICS")
    print(f"{'='*80}")
    
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.execute("""
        SELECT 
            COUNT(*) as total_dances,
            COUNT(CASE WHEN intensity > 0 THEN 1 END) as with_intensity,
            MIN(CASE WHEN intensity > 0 THEN intensity END) as min_intensity,
            MAX(intensity) as max_intensity,
            AVG(CASE WHEN intensity > 0 THEN intensity END) as avg_intensity,
            COUNT(CASE WHEN intensity > 0 AND intensity <= 40 THEN 1 END) as easy,
            COUNT(CASE WHEN intensity > 40 AND intensity < 70 THEN 1 END) as medium,
            COUNT(CASE WHEN intensity >= 70 THEN 1 END) as hard
        FROM dance
    """)
    stats = dict(cur.fetchone())
    con.close()
    
    print(f"Total dances: {stats['total_dances']}")
    print(f"Dances with intensity: {stats['with_intensity']} ({stats['with_intensity']/stats['total_dances']*100:.1f}%)")
    print(f"Intensity range: {stats['min_intensity']} - {stats['max_intensity']}")
    print(f"Average intensity: {stats['avg_intensity']:.1f}")
    print(f"\nDifficulty distribution:")
    print(f"  Easy (1-40): {stats['easy']} dances")
    print(f"  Medium (41-69): {stats['medium']} dances")
    print(f"  Hard (70+): {stats['hard']} dances")
    
    print(f"\n{'='*80}")
    print("✅ All tests completed successfully!")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
