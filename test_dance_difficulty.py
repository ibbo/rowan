"""Published-grade precedence, ungraded fallbacks and nightly replacement safety."""
import asyncio
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from database import DatabasePool
from dance_tools import find_dances, get_dance_detail, search_cribs, get_publication_dances
from dance_difficulty import with_difficulty
from lesson_tools import get_full_crib
import refresh_scddb


class DifficultyToolsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'test.sqlite'
        with sqlite3.connect(self.path) as db:
            db.executescript('''
                CREATE TABLE v_metaform(id INTEGER, name TEXT, kind TEXT, metaform TEXT,
                    bars INTEGER, progression TEXT, intensity INTEGER, rscds_grade INTEGER);
                INSERT INTO v_metaform VALUES
                    (1,'One','Reel','Longwise',32,'Normal',90,1),
                    (2,'Two','Reel','Longwise',32,'Normal',-1,2),
                    (3,'Three','Reel','Longwise',32,'Normal',10,3),
                    (4,'Four','Jig','Longwise',32,'Normal',80,4),
                    (5,'Unknown easy','Reel','Longwise',32,'Normal',30,NULL),
                    (6,'Unknown hard','Reel','Longwise',32,'Normal',80,NULL),
                    (7,'Unknown all','Reel','Longwise',32,'Normal',-1,NULL);
                CREATE TABLE dance AS SELECT id,name FROM v_metaform;
                CREATE TABLE v_dance_has_token(dance_id INTEGER, formation_tokens TEXT);
                INSERT INTO v_dance_has_token VALUES (1,'POUSS'),(2,'POUSS'),(5,'POUSS');
                CREATE TABLE v_dance_formations(dance_id INTEGER, formation_name TEXT, formation_tokens TEXT);
                CREATE TABLE v_crib_best(dance_id INTEGER, reliability INTEGER, last_modified TEXT, text TEXT);
                INSERT INTO v_crib_best VALUES (1,1,'2026-09-19','Dance a poussette');
                CREATE VIRTUAL TABLE fts_cribs USING fts5(text, content='');
                INSERT INTO fts_cribs(rowid,text) VALUES (1,'Dance a poussette');
                CREATE TABLE publication(id INTEGER, name TEXT, shortname TEXT, year INTEGER, rscds INTEGER);
                INSERT INTO publication VALUES (1,'Book','B',2026,1);
                CREATE TABLE dancespublicationsmap(dance_id INTEGER, publication_id INTEGER, number INTEGER, page INTEGER);
                INSERT INTO dancespublicationsmap VALUES (1,1,1,1),(2,1,2,2),(3,1,3,3),(7,1,4,4);
            ''')
        self.pool = DatabasePool(str(self.path))
        self.singleton = patch.object(DatabasePool, '_instance', self.pool)
        self.singleton.start()

    async def asyncTearDown(self):
        await self.pool.close_all()
        self.singleton.stop()
        self.tmp.cleanup()

    async def test_official_grade_wins_over_conflicting_intensity(self):
        rows = await find_dances.ainvoke({'max_rscds_grade': 1})
        self.assertEqual([r['id'] for r in rows], [1])
        self.assertEqual(rows[0]['intensity'], 90)
        self.assertIsNone(rows[0]['difficulty_estimate'])
        self.assertEqual(rows[0]['difficulty_source'], 'SCDDB rscds_grade')

    async def test_range_publication_kind_and_formation_filters_combine(self):
        rows = await find_dances.ainvoke({'min_rscds_grade': 1, 'max_rscds_grade': 2,
            'official_rscds_dances': True, 'kind': 'Reel', 'formation_token': 'POUSS',
            'sort_by_rscds_grade': 'desc'})
        self.assertEqual([r['id'] for r in rows], [2, 1])

    async def test_sort_excludes_unknown_and_supports_grade_four(self):
        rows = await find_dances.ainvoke({'sort_by_rscds_grade': 'asc'})
        self.assertEqual([r['rscds_grade'] for r in rows], [1, 2, 3, 4])

    async def test_non_rscds_legacy_fallback_excludes_graded_dances(self):
        rows = await find_dances.ainvoke({'has_rscds_grade': False,
            'official_rscds_dances': False, 'max_intensity': 40})
        self.assertEqual([r['id'] for r in rows], [5])
        self.assertIsNone(rows[0]['rscds_grade'])
        self.assertEqual(rows[0]['difficulty_estimate']['level'], 'easy')

    async def test_ungraded_rscds_dance_remains_unknown(self):
        rows = await find_dances.ainvoke({'has_rscds_grade': False, 'official_rscds_dances': True})
        self.assertEqual([r['id'] for r in rows], [7])
        self.assertEqual(rows[0]['difficulty_source'], 'unassessed')

    async def test_grade_reaches_detail_crib_search_and_publications(self):
        detail = await get_dance_detail.ainvoke({'dance_id': 1})
        crib = await get_full_crib.ainvoke({'dance_id': 1})
        matches = await search_cribs.ainvoke({'query_text': 'poussette'})
        publication = await get_publication_dances.ainvoke({'publication_id': 1})
        for row in [detail['dance'], crib, matches[0], publication['dances'][0]]:
            self.assertEqual(row['rscds_grade'], 1)
            self.assertIn('one ghillie', row['rscds_grade_label'])
            self.assertIsNone(row['difficulty_estimate'])

    async def test_invalid_grade_filters_rejected(self):
        for args in ({'max_rscds_grade': 0}, {'min_rscds_grade': 5},
                     {'min_rscds_grade': 3, 'max_rscds_grade': 1},
                     {'has_rscds_grade': False, 'max_rscds_grade': 1}):
            with self.assertRaises(ValueError):
                await find_dances.ainvoke(args)


class FallbackTests(unittest.TestCase):
    def test_legacy_boundaries_and_unknown_sentinels(self):
        for value, level in [(1,'easy'),(40,'easy'),(41,'medium'),(69,'medium'),(70,'hard')]:
            self.assertEqual(with_difficulty({'rscds_grade': -1, 'intensity': value})['difficulty_estimate']['level'], level)
        for grade in (None, -1, 0):
            for intensity in (None, -1, 0):
                result = with_difficulty({'rscds_grade': grade, 'intensity': intensity})
                self.assertIsNone(result['rscds_grade'])
                self.assertIsNone(result['difficulty_estimate'])


class RefreshSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_pool_reopens_after_atomic_refresh_and_discards_inflight_old_handle(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'live.sqlite'
            new = Path(directory) / 'new.sqlite'
            for target, grade in [(path, 1), (new, 3)]:
                with sqlite3.connect(target) as db:
                    db.execute('CREATE TABLE dance(grade INTEGER)')
                    db.execute('INSERT INTO dance VALUES (?)', (grade,))
            pool = DatabasePool(str(path))
            try:
                inflight = await pool.acquire()
                idle = await pool.acquire()
                await pool.release(idle)
                new.replace(path)
                fresh = await pool.acquire()
                self.assertEqual((await (await fresh.execute('SELECT grade FROM dance')).fetchone())[0], 3)
                await pool.release(inflight)
                self.assertNotIn(inflight, pool._pool)
                await pool.release(fresh)
                again = await pool.acquire()
                self.assertEqual((await (await again.execute('SELECT grade FROM dance')).fetchone())[0], 3)
                await pool.release(again)
            finally:
                await pool.close_all()

    async def test_failed_postprocess_keeps_live_database_intact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            live, staged, dump = root/'live.sqlite', root/'staged.sqlite', root/'dump.sql'
            live.write_bytes(b'previous valid database sentinel')
            dump.write_text('CREATE TABLE unrelated(id INTEGER);')
            with patch.multiple(refresh_scddb, DB_PATH=live, TMP_DB_PATH=staged, DUMP_PATH=dump), \
                 patch.object(refresh_scddb, 'download_latest_sql'):
                with self.assertRaises(SystemExit):
                    refresh_scddb.main()
            self.assertEqual(live.read_bytes(), b'previous valid database sentinel')


if __name__ == '__main__':
    unittest.main()
