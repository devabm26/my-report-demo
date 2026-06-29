import os
import psycopg2
import psycopg2.extras
from flask import Flask, render_template

app = Flask(__name__)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "postgresql.thoughts-app.svc.cluster.local"),
    "database": os.environ.get("DB_NAME", "thoughts"),
    "user": os.environ.get("DB_USER", "thoughts"),
    "password": os.environ.get("DB_PASSWORD", "thoughts123"),
    "connect_timeout": 5,
}


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def fetch_thoughts():
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    t.content,
                    t.author,
                    t.status,
                    t.thumbs_up,
                    t.thumbs_down,
                    (t.thumbs_up - t.thumbs_down) AS net_rating,
                    te.similarity_score,
                    te.evaluated_at
                FROM thoughts t
                LEFT JOIN LATERAL (
                    SELECT similarity_score, evaluated_at
                    FROM thought_evaluations
                    WHERE thought_id = t.id
                    ORDER BY evaluated_at DESC
                    LIMIT 1
                ) te ON true
                ORDER BY t.status, net_rating DESC
            """)
            return cur.fetchall(), None
    except Exception as e:
        return [], str(e)
    finally:
        conn.close()


def fetch_summary():
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = 'APPROVED') AS approved,
                    COUNT(*) FILTER (WHERE status = 'REJECTED') AS rejected,
                    COUNT(*) FILTER (WHERE status = 'IN_REVIEW') AS in_review,
                    COUNT(*) FILTER (WHERE status = 'REMOVED') AS removed
                FROM thoughts
            """)
            return cur.fetchone(), None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()


@app.route("/")
def index():
    thoughts, error = fetch_thoughts()
    summary, summary_error = fetch_summary()
    return render_template(
        "index.html",
        thoughts=thoughts,
        summary=summary,
        error=error or summary_error,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
