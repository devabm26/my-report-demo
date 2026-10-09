from flask import Flask, render_template
import psycopg2
import psycopg2.extras

app = Flask(__name__)

DB_CONFIG = {
    "host": "postgresql.thoughts-app.svc.cluster.local",
    "port": 5432,
    "database": "thoughts",
    "user": "thoughts",
    "password": "thoughts123",
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def get_thoughts():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
        LEFT JOIN (
            SELECT DISTINCT ON (thought_id)
                thought_id,
                similarity_score
            FROM thought_evaluations
            ORDER BY thought_id, evaluated_at DESC
        ) te ON te.thought_id = t.id
        ORDER BY t.created_at DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_summary():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'APPROVED') AS approved,
            COUNT(*) FILTER (WHERE status = 'REJECTED') AS rejected,
            COUNT(*) FILTER (WHERE status = 'IN_REVIEW') AS in_review,
            COUNT(*) FILTER (WHERE status = 'REMOVED') AS removed
        FROM thoughts
    """)
    summary = cur.fetchone()
    cur.close()
    conn.close()
    return summary


@app.route("/")
def index():
    error = None
    thoughts = []
    summary = {}
    try:
        thoughts = get_thoughts()
        summary = get_summary()
    except Exception as e:
        error = str(e)
    return render_template("index.html", thoughts=thoughts, summary=summary, error=error)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
