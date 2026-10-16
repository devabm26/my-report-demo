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


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


@app.route("/")
def index():
    conn = None
    error = None
    thoughts = []
    summary = {}

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Summary stats
        cur.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status = 'APPROVED') AS approved,
                COUNT(*) FILTER (WHERE status = 'REJECTED') AS rejected,
                COUNT(*) FILTER (WHERE status = 'IN_REVIEW') AS in_review,
                COUNT(*) FILTER (WHERE status = 'REMOVED') AS removed
            FROM thoughts
        """)
        summary = dict(cur.fetchone())

        # All thoughts with latest evaluation similarity score
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
        thoughts = [dict(row) for row in cur.fetchall()]
        cur.close()
    except Exception as e:
        error = str(e)
    finally:
        if conn:
            conn.close()

    return render_template("index.html", thoughts=thoughts, summary=summary, error=error)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
