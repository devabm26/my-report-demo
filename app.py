from flask import Flask, render_template
import os

import psycopg2
import psycopg2.extras

app = Flask(__name__)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "postgresql.thoughts-app.svc.cluster.local"),
    "database": "thoughts",
    "user": "thoughts",
    "password": "thoughts123",
}


def get_db():
    return psycopg2.connect(**DB_CONFIG)


def get_summary_stats(cur):
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'APPROVED') AS approved,
            COUNT(*) FILTER (WHERE status = 'REJECTED') AS rejected,
            COUNT(*) FILTER (WHERE status = 'IN_REVIEW') AS in_review,
            COUNT(*) FILTER (WHERE status = 'REMOVED') AS removed
        FROM thoughts
    """)
    return cur.fetchone()


def get_thoughts(cur):
    cur.execute("""
        SELECT
            t.content,
            t.author,
            t.status,
            t.thumbs_up,
            t.thumbs_down,
            (t.thumbs_up - t.thumbs_down) AS net_rating,
            te.similarity_score,
            t.created_at
        FROM thoughts t
        LEFT JOIN LATERAL (
            SELECT similarity_score
            FROM thought_evaluations
            WHERE thought_id = t.id
            ORDER BY evaluated_at DESC
            LIMIT 1
        ) te ON true
        ORDER BY t.created_at DESC
    """)
    return cur.fetchall()


@app.route("/")
def index():
    error = None
    thoughts = []
    stats = None

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        stats = get_summary_stats(cur)
        thoughts = get_thoughts(cur)
        cur.close()
        conn.close()
    except Exception as e:
        error = str(e)

    return render_template("index.html", thoughts=thoughts, stats=stats, error=error)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
