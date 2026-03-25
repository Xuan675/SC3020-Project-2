from config import DB_CONFIG
import psycopg

PLANNER_OPTIONS = (
    "enable_hashjoin",
    "enable_mergejoin",
    "enable_nestloop",
)

def connect_db():
    return psycopg.connect(**DB_CONFIG)

def run_sql(conn, sql: str):
    with conn.cursor() as cur:
        cur.execute(sql)
        if cur.description is None:
            return None
        return cur.fetchall()

def _extract_plan(result):
    return result[0][0]

def get_qep(conn, query: str):
    try:
        result = run_sql(conn, f"EXPLAIN (FORMAT JSON) {query}")
        return _extract_plan(result)
    finally:
        conn.rollback()


def get_aqp(conn, query: str, disabled_option: str):
    try:
        run_sql(conn, f"SET LOCAL {disabled_option} = off;")
        result = run_sql(conn, f"EXPLAIN (FORMAT JSON) {query}")
        return _extract_plan(result)
    finally:
        # End the transaction so the SET LOCAL setting is discarded.
        conn.rollback()


def get_representative_aqps(conn, query: str):
    aqps = []
    for option in PLANNER_OPTIONS:
        try:
            plan = get_aqp(conn, query, option)
            aqps.append({
                "disabled_option": option,
                "plan": plan,
            })
        except Exception as exc:
            aqps.append({
                "disabled_option": option,
                "error": str(exc),
            })
    return aqps
