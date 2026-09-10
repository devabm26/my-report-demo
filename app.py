from flask import Flask, render_template
import psycopg2
import psycopg2.extras

app = Flask(__name__)

DB_CONFIG = {
    "host": "postgresql.thoughts-app.svc.cluster.local",
    "database": "thoughts",
    "user": "thoughts",
    "password": "thoughts123",
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def get_summary():
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = 'APPROVED') AS approved,
                    COUNT(*) FILTER (WHERE status = 'REJECTED') AS rejected,
                    COUNT(*) FILTER (WHERE status = 'IN_REVIEW') AS in_review,
                    COUNT(*) FILTER (WHERE status = 'REMOVED') AS removed
                FROM thoughts
            """)
            return dict(cur.fetchone())


def get_thoughts():
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT
                    t.content,
                    t.author,
                    t.status,
                    t.thumbs_up,
                    t.thumbs_down,
                    (t.thumbs_up - t.thumbs_down) AS net_rating,
                    te.similarity_score
                FROM thoughts t
                LEFT JOIN LATERAL (
                    SELECT similarity_score
                    FROM thought_evaluations
                    WHERE thought_id = t.id
                    ORDER BY evaluated_at DESC
                    LIMIT 1
                ) te ON true
                ORDER BY net_rating DESC, t.thumbs_up DESC
            """)
            return [dict(row) for row in cur.fetchall()]


@app.route("/")
def index():
    error = None
    thoughts = []
    summary = {}
    try:
        summary = get_summary()
        thoughts = get_thoughts()
    except Exception as e:
        error = str(e)
    return render_template("index.html", thoughts=thoughts, summary=summary, error=error)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
