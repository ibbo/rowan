#!/usr/bin/env python3
import os
import sys
import io
import shutil
import gzip
import zipfile
import sqlite3
import urllib.request
import datetime
from pathlib import Path

# -----------------------------
# Config
# -----------------------------
DATA_DIR = Path("data/scddb")
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "scddb.sqlite"
TMP_DB_PATH = DATA_DIR / "scddb.sqlite.tmp"

# Prefer the canonical "latest" URLs; script falls back automatically
BASE_URL = "https://media.strathspey.org/scddata"
SQL_URLS = [
    f"{BASE_URL}/scddata-2.0.sql",      # uncompressed
    f"{BASE_URL}/scddata-2.0.zip",      # zip
]
DUMP_PATH = DATA_DIR / "scddata.sql"    # we normalize everything to a .sql here

# -----------------------------
# Helpers
# -----------------------------
def log(msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

def _download(url: str) -> bytes:
    log(f"Downloading: {url}")
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()

def download_latest_sql():
    """Download latest dump and normalize to plain .sql at DUMP_PATH."""
    for url in SQL_URLS:
        try:
            blob = _download(url)
            if url.endswith(".sql"):
                DUMP_PATH.write_bytes(blob)
                log(f"Wrote SQL dump: {DUMP_PATH}")
                return
            if url.endswith(".gz"):
                sql = gzip.decompress(blob)
                DUMP_PATH.write_bytes(sql)
                log(f"Wrote SQL dump (from .gz): {DUMP_PATH}")
                return
            if url.endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                    # pick the first .sql inside
                    sql_names = [n for n in zf.namelist() if n.lower().endswith(".sql")]
                    if not sql_names:
                        raise RuntimeError("ZIP file contains no .sql")
                    with zf.open(sql_names[0], "r") as f:
                        DUMP_PATH.write_bytes(f.read())
                log(f"Wrote SQL dump (from .zip): {DUMP_PATH}")
                return
        except Exception as e:
            log(f"  ...failed ({e})")
    raise RuntimeError("Could not download any dump variant.")

def rebuild_db_from_dump():
    """Executes the .sql into a fresh tmp db, then swaps atomically."""
    if not DUMP_PATH.exists():
        raise FileNotFoundError(f"Missing dump: {DUMP_PATH}")
    if TMP_DB_PATH.exists():
        TMP_DB_PATH.unlink()

    sql_text = DUMP_PATH.read_text(encoding="utf-8", errors="replace")
    log("Creating temporary database...")
    con = sqlite3.connect(TMP_DB_PATH)
    try:
        con.executescript("PRAGMA journal_mode=WAL;")
        con.executescript(sql_text)
        con.commit()
    finally:
        con.close()
    # Atomic replace
    log("Swapping new database into place...")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    TMP_DB_PATH.replace(DB_PATH)

def exec_sql(sql: str):
    con = sqlite3.connect(DB_PATH)
    try:
        con.executescript(sql)
        con.commit()
    finally:
        con.close()

def query_one(sql: str, args=()):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(sql, args).fetchone()
        return dict(row) if row else None
    finally:
        con.close()

def postprocess_views_indexes_fts():
    """Create views, indexes, and FTS table. Safe to re-run."""
    log("Creating views and indexes...")
    post_sql = r"""
    -- Views
    DROP VIEW IF EXISTS v_dances;
    CREATE VIEW v_dances AS
      SELECT
        d.id,
        d.name,
        d.barsperrepeat AS bars,
        dt.name AS kind,
        s.name  AS shape,
        c.name  AS couples,
        p.name  AS progression,
        d.type_id, d.shape_id, d.couples_id, d.progression_id
      FROM dance d
      LEFT JOIN dancetype  dt ON dt.id = d.type_id
      LEFT JOIN shape       s ON s.id  = d.shape_id
      LEFT JOIN couples     c ON c.id  = d.couples_id
      LEFT JOIN progression p ON p.id  = d.progression_id;

    DROP VIEW IF EXISTS v_dance_formations;
    CREATE VIEW v_dance_formations AS
      SELECT
        m.dance_id,
        f.id           AS formation_id,
        f.name         AS formation_name,
        f.searchid     AS formation_tokens
      FROM dancesformationsmap m
      JOIN formation f ON f.id = m.formation_id;

    DROP VIEW IF EXISTS v_crib_best;
    CREATE VIEW v_crib_best AS
    WITH ranked AS (
      SELECT
        dc.dance_id,
        dc.text,
        dc.format,
        dc.reliability,
        dc.last_modified,
        ROW_NUMBER() OVER (
          PARTITION BY dc.dance_id
          ORDER BY dc.reliability DESC, dc.last_modified DESC
        ) AS rn
      FROM dancecrib dc
    )
    SELECT dance_id, text, format, reliability, last_modified
    FROM ranked WHERE rn = 1;

    -- Human-friendly metaform
    DROP VIEW IF EXISTS v_metaform;
    CREATE VIEW v_metaform AS
    SELECT
      d.id,
      d.name,
      d.kind,
      d.bars,
      TRIM(REPLACE(d.shape, ' - ', ' ')) AS shape_label,
      REPLACE(d.couples, ' couples', 'C') AS couples_label,
      printf('%s %s',
             TRIM(REPLACE(d.shape, ' - ', ' ')),
             REPLACE(d.couples, ' couples', 'C')) AS metaform,
      d.progression,
      d.type_id, d.shape_id, d.couples_id, d.progression_id
    FROM v_dances d;

    DROP VIEW IF EXISTS v_dance_has_token;
    CREATE VIEW v_dance_has_token AS
    SELECT DISTINCT
      vf.dance_id,
      vf.formation_tokens
    FROM v_dance_formations vf;

    -- Helpful indexes (no-ops if already exist)
    CREATE INDEX IF NOT EXISTS idx_dance_type     ON dance(type_id);
    CREATE INDEX IF NOT EXISTS idx_dance_shape    ON dance(shape_id);
    CREATE INDEX IF NOT EXISTS idx_dance_couples  ON dance(couples_id);
    CREATE INDEX IF NOT EXISTS idx_dance_prog     ON dance(progression_id);
    CREATE INDEX IF NOT EXISTS idx_map_dance      ON dancesformationsmap(dance_id);
    CREATE INDEX IF NOT EXISTS idx_map_formation  ON dancesformationsmap(formation_id);
    """
    exec_sql(post_sql)

    # FTS (rebuild each refresh)
    log("Building FTS index over best cribs...")
    con = sqlite3.connect(DB_PATH)
    try:
        con.executescript("""
            DROP TABLE IF EXISTS fts_cribs;
            CREATE VIRTUAL TABLE fts_cribs USING fts5(
              dance_id UNINDEXED,
              text,
              content=''
            );
            INSERT INTO fts_cribs(dance_id, text)
            SELECT dance_id, text FROM v_crib_best;
        """)
        con.commit()
    finally:
        con.close()

def sanity_print():
    one = query_one("SELECT COUNT(*) AS n FROM dance;")
    two = query_one("SELECT kind, COUNT(*) AS n FROM v_dances GROUP BY kind ORDER BY n DESC LIMIT 1;")
    three = query_one("SELECT metaform, COUNT(*) AS n FROM v_metaform GROUP BY metaform ORDER BY n DESC LIMIT 1;")
    log(f"Total dances: {one['n'] if one else '?'}")
    if two:  log(f"Most-common kind: {two['kind']} ({two['n']})")
    if three:log(f"Most-common metaform: {three['metaform']} ({three['n']})")

def vacuum_analyze():
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute("PRAGMA optimize;")
        con.execute("VACUUM;")
        con.execute("ANALYZE;")
        con.commit()
    finally:
        con.close()

def main():
    try:
        download_latest_sql()
        rebuild_db_from_dump()
        postprocess_views_indexes_fts()
        sanity_print()
        vacuum_analyze()
        log("OK: database refreshed.")
        log("Attribution: Scottish Country Dance Database (SCDDB), CC BY 3.0 DE.")
    except Exception as e:
        log(f"ERROR: {e}")
        # Keep previous DB intact if something failed.
        sys.exit(1)

if __name__ == "__main__":
    main()
