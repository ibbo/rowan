#!/usr/bin/env python3
"""
Performance testing script for the Scottish Country Dance MCP server.
Tests various query patterns and scenarios to identify performance bottlenecks.
"""

import asyncio
import json
import os
import sys
import time
import statistics
import logging
from typing import Dict, List, Any
from mcp_scddb_server import q, q_one, DB_PATH

# Setup logging to capture performance data
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('performance_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class PerformanceTest:
    def __init__(self):
        self.results = {}
        
    def time_function(self, func, *args, **kwargs):
        """Time a function execution and return result + timing"""
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        duration = (end - start) * 1000  # Convert to ms
        return result, duration
    
    def run_multiple_times(self, test_name: str, func, *args, runs=5, **kwargs):
        """Run a test multiple times and collect statistics"""
        logger.info(f"Running {test_name} ({runs} times)")
        times = []
        results = []
        
        for i in range(runs):
            result, duration = self.time_function(func, *args, **kwargs)
            times.append(duration)
            results.append(result)
            logger.info(f"  Run {i+1}: {duration:.2f}ms")
        
        stats = {
            'min': min(times),
            'max': max(times),
            'mean': statistics.mean(times),
            'median': statistics.median(times),
            'stdev': statistics.stdev(times) if len(times) > 1 else 0,
            'runs': runs,
            'sample_result_size': len(results[0]) if results and isinstance(results[0], list) else 1
        }
        
        self.results[test_name] = stats
        logger.info(f"  Stats - Mean: {stats['mean']:.2f}ms, Min: {stats['min']:.2f}ms, Max: {stats['max']:.2f}ms, StdDev: {stats['stdev']:.2f}ms")
        return results[0], stats

    def test_basic_queries(self):
        """Test basic database operations"""
        logger.info("\n=== BASIC QUERY TESTS ===")
        
        # Test simple count query
        self.run_multiple_times(
            "total_dance_count",
            q,
            "SELECT COUNT(*) as count FROM v_metaform"
        )
        
        # Test single dance lookup
        self.run_multiple_times(
            "single_dance_by_id", 
            q_one,
            "SELECT * FROM v_metaform WHERE id = ?", 
            (1,)
        )
        
        # Test small result set
        self.run_multiple_times(
            "first_10_dances",
            q,
            "SELECT * FROM v_metaform ORDER BY name LIMIT 10"
        )

    def test_find_dances_scenarios(self):
        """Test various find_dances query patterns"""
        logger.info("\n=== FIND_DANCES QUERY TESTS ===")
        
        # Test simple name search
        self.run_multiple_times(
            "name_search_simple",
            q,
            "SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression FROM v_metaform m WHERE m.name LIKE ? COLLATE NOCASE ORDER BY m.name LIMIT ?",
            ("%reel%", 25)
        )
        
        # Test complex query with RSCDS filter (expensive join)
        rscds_sql = """
        SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression
        FROM v_metaform m
        INNER JOIN dancespublicationsmap dpm ON m.id = dpm.dance_id
        INNER JOIN publication p ON dpm.publication_id = p.id AND p.rscds = 1
        WHERE m.name LIKE ? COLLATE NOCASE
        ORDER BY m.name LIMIT ?
        """
        self.run_multiple_times(
            "rscds_filter_with_name_search",
            q,
            rscds_sql,
            ("%reel%", 25)
        )
        
        # Test non-RSCDS filter (expensive subquery)
        non_rscds_sql = """
        SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression
        FROM v_metaform m
        WHERE m.id NOT IN (
            SELECT DISTINCT dpm2.dance_id 
            FROM dancespublicationsmap dpm2
            INNER JOIN publication p2 ON dpm2.publication_id = p2.id AND p2.rscds = 1
        )
        AND m.name LIKE ? COLLATE NOCASE
        ORDER BY m.name LIMIT ?
        """
        self.run_multiple_times(
            "non_rscds_filter_with_name_search",
            q,
            non_rscds_sql,
            ("%reel%", 25)
        )
        
        # Test formation token search (involves join)
        formation_sql = """
        SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression
        FROM v_metaform m
        LEFT JOIN v_dance_has_token t ON t.dance_id = m.id
        WHERE t.formation_tokens LIKE ?
        ORDER BY m.name LIMIT ?
        """
        self.run_multiple_times(
            "formation_token_search",
            q,
            formation_sql,
            ("%REEL;3P;%", 25)
        )
        
        # Test large result set
        self.run_multiple_times(
            "large_result_set_100",
            q,
            "SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression FROM v_metaform m ORDER BY m.name LIMIT ?",
            (100,)
        )
        
        # Test random ordering (no index benefit)
        self.run_multiple_times(
            "random_ordering_25",
            q,
            "SELECT DISTINCT m.id, m.name, m.kind, m.metaform, m.bars, m.progression FROM v_metaform m ORDER BY RANDOM() LIMIT ?",
            (25,)
        )

    def test_dance_detail_queries(self):
        """Test dance_detail component queries"""
        logger.info("\n=== DANCE_DETAIL QUERY TESTS ===")
        
        dance_id = 1  # Use first dance for testing
        
        # Main dance query
        self.run_multiple_times(
            "dance_detail_main",
            q_one,
            "SELECT * FROM v_metaform WHERE id=?",
            (dance_id,)
        )
        
        # Formations query
        self.run_multiple_times(
            "dance_detail_formations",
            q,
            "SELECT formation_name, formation_tokens FROM v_dance_formations WHERE dance_id=? ORDER BY formation_name",
            (dance_id,)
        )
        
        # Crib query
        self.run_multiple_times(
            "dance_detail_crib",
            q_one,
            "SELECT reliability, last_modified, text FROM v_crib_best WHERE dance_id=?",
            (dance_id,)
        )
        
        # Publications query (complex join)
        self.run_multiple_times(
            "dance_detail_publications",
            q,
            """
            SELECT p.name, p.shortname, p.rscds, dpm.number, dpm.page
            FROM publication p
            JOIN dancespublicationsmap dpm ON p.id = dpm.publication_id
            WHERE dpm.dance_id = ?
            ORDER BY p.rscds DESC, p.name
            """,
            (dance_id,)
        )

    def test_search_cribs_queries(self):
        """Test full-text search queries"""
        logger.info("\n=== SEARCH_CRIBS QUERY TESTS ===")
        
        # Simple FTS query
        self.run_multiple_times(
            "fts_simple_term",
            q,
            """
            SELECT d.id, d.name, d.kind, d.metaform, d.bars
            FROM fts_cribs f
            JOIN v_metaform d ON d.id = f.dance_id
            WHERE fts_cribs MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            ("reel", 20)
        )
        
        # Complex FTS query with OR
        self.run_multiple_times(
            "fts_complex_or",
            q,
            """
            SELECT d.id, d.name, d.kind, d.metaform, d.bars
            FROM fts_cribs f
            JOIN v_metaform d ON d.id = f.dance_id
            WHERE fts_cribs MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            ("poussette OR allemande", 20)
        )

    def test_database_size_info(self):
        """Get information about database size and structure"""
        logger.info("\n=== DATABASE SIZE ANALYSIS ===")
        
        # Table sizes
        tables = ['v_metaform', 'v_dance_formations', 'v_dance_has_token', 'fts_cribs', 'publication', 'dancespublicationsmap']
        
        for table in tables:
            try:
                result = q(f"SELECT COUNT(*) as count FROM {table}")
                logger.info(f"Table {table}: {result[0]['count']} rows")
            except Exception as e:
                logger.warning(f"Could not count table {table}: {e}")
        
        # Database file size
        if os.path.exists(DB_PATH):
            size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
            logger.info(f"Database file size: {size_mb:.2f} MB")

    def run_all_tests(self):
        """Run all performance tests"""
        logger.info("Starting comprehensive database performance tests")
        logger.info(f"Database path: {DB_PATH}")
        
        if not os.path.exists(DB_PATH):
            logger.error(f"Database not found at {DB_PATH}")
            return
        
        try:
            self.test_database_size_info()
            self.test_basic_queries()
            self.test_find_dances_scenarios()
            self.test_dance_detail_queries()
            self.test_search_cribs_queries()
            
            # Generate summary report
            self.generate_report()
            
        except Exception as e:
            logger.exception("Error during performance testing")

    def generate_report(self):
        """Generate a summary performance report"""
        logger.info("\n" + "="*60)
        logger.info("PERFORMANCE SUMMARY REPORT")
        logger.info("="*60)
        
        # Sort by mean time (slowest first)
        sorted_results = sorted(self.results.items(), key=lambda x: x[1]['mean'], reverse=True)
        
        logger.info("\nSLOWEST QUERIES (by mean time):")
        logger.info("-" * 60)
        for name, stats in sorted_results[:10]:  # Top 10 slowest
            logger.info(f"{name:30s}: {stats['mean']:8.2f}ms (±{stats['stdev']:6.2f}) [{stats['min']:6.2f}-{stats['max']:6.2f}]")
        
        # Identify potential issues
        logger.info("\nPOTENTIAL PERFORMANCE ISSUES:")
        logger.info("-" * 40)
        
        slow_threshold = 100  # ms
        variable_threshold = 50  # ms standard deviation
        
        issues = []
        for name, stats in self.results.items():
            if stats['mean'] > slow_threshold:
                issues.append(f"SLOW: {name} averages {stats['mean']:.1f}ms")
            if stats['stdev'] > variable_threshold:
                issues.append(f"VARIABLE: {name} has high variance (σ={stats['stdev']:.1f}ms)")
        
        if issues:
            for issue in issues:
                logger.info(f"  • {issue}")
        else:
            logger.info("  No major performance issues detected!")
        
        # Save detailed results to JSON
        with open('performance_results.json', 'w') as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"\nDetailed results saved to: performance_results.json")

def main():
    """Run performance tests"""
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage: python test_query_performance.py")
        print("Tests database query performance and generates a report.")
        return
    
    tester = PerformanceTest()
    tester.run_all_tests()

if __name__ == "__main__":
    main()
