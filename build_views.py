import sqlite3, pathlib

DB = pathlib.Path("data/scddb/scddb.sqlite")

def name_col(db, table, candidates=("name","title","short_name","key")):
    cols = {r[1].lower() for r in db.execute(f"PRAGMA table_info({table})")}
    for c in candidates:
        if c in cols: return c
    # fallback to first text-ish column
    for cid,name,ctype,_,_,_ in db.execute(f"PRAGMA table_info({table})"):
        if "char" in (ctype or "").lower() or "text" in (ctype or "").lower():
            return name
    # last resort
    return "id"

with sqlite3.connect(DB) as db:
    db.executescript("""
    DROP VIEW IF EXISTS v_dances;
    DROP VIEW IF EXISTS v_dance_formations;
    DROP VIEW IF EXISTS v_crib_best;
    """)
    db.commit()

    # figure out actual column names we’ll join to
    dctype_name = name_col(sqlite3.connect(DB), "dancetype")
    shape_name  = name_col(sqlite3.connect(DB), "shape")
    couples_name= name_col(sqlite3.connect(DB), "couples")
    prog_name   = name_col(sqlite3.connect(DB), "progression")
    form_name   = name_col(sqlite3.connect(DB), "formation")

    # v_dances: one row per dance with joined labels you’ll filter on
    sql_v_dances = f"""
    CREATE VIEW v_dances AS
    SELECT
      d.id,
      d.name,
      d.barsperrepeat          AS bars,
      dt.{dctype_name}         AS kind,
      s.{shape_name}           AS shape,
      c.{couples_name}         AS couples,
      p.{prog_name}            AS progression,
      d.type_id,
      d.shape_id,
      d.couples_id,
      d.progression_id
    FROM dance d
    LEFT JOIN dancetype   dt ON dt.id = d.type_id
    LEFT JOIN shape        s ON s.id  = d.shape_id
    LEFT JOIN couples      c ON c.id  = d.couples_id
    LEFT JOIN progression  p ON p.id  = d.progression_id;
    """

    # v_dance_formations: dance -> formation names
    sql_v_dance_formations = f"""
    CREATE VIEW v_dance_formations AS
    SELECT
      m.dance_id,
      f.id           AS formation_id,
      f.{form_name}  AS formation_name,
      f.searchid     AS formation_tokens
    FROM dancesformationsmap m
    JOIN formation f ON f.id = m.formation_id;
    """

    # v_crib_best: pick the latest “best” crib per dance (highest reliability, then newest)
    sql_v_crib_best = """
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
    """

    for sql in (sql_v_dances, sql_v_dance_formations, sql_v_crib_best):
        db.executescript(sql)

    # helpful indexes on base tables (no-ops if exist)
    db.executescript("""
    CREATE INDEX IF NOT EXISTS idx_dance_type     ON dance(type_id);
    CREATE INDEX IF NOT EXISTS idx_dance_shape    ON dance(shape_id);
    CREATE INDEX IF NOT EXISTS idx_dance_couples  ON dance(couples_id);
    CREATE INDEX IF NOT EXISTS idx_dance_prog     ON dance(progression_id);
    CREATE INDEX IF NOT EXISTS idx_map_dance      ON dancesformationsmap(dance_id);
    CREATE INDEX IF NOT EXISTS idx_map_formation  ON dancesformationsmap(formation_id);
    """)
    db.commit()
    print("Views created: v_dances, v_dance_formations, v_crib_best")

