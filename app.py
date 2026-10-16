import os
from flask import Flask, render_template, request, redirect, url_for, flash
import psycopg2
import psycopg2.extras

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "thoughts-dashboard-secret")

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "postgresql.thoughts-app.svc.cluster.local"),
    "database": os.environ.get("DB_NAME", "thoughts"),
    "user": os.environ.get("DB_USER", "thoughts"),
    "password": os.environ.get("DB_PASSWORD", "thoughts123"),
}

STATUSES = ["APPROVED", "REJECTED", "IN_REVIEW", "REMOVED"]


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


# ── Dashboard ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    status_filter = request.args.get("status", "")
    author_filter = request.args.get("author", "").strip()
    sort = request.args.get("sort", "created_at")
    order = request.args.get("order", "desc")

    allowed_sorts = {
        "created_at", "author", "status",
        "thumbs_up", "thumbs_down", "net_rating", "similarity_score"
    }
    if sort not in allowed_sorts:
        sort = "created_at"
    order_sql = "DESC" if order == "desc" else "ASC"

    conn = None
    error = None
    thoughts = []
    summary = {}
    authors = []

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Summary stats
        cur.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status = 'APPROVED')  AS approved,
                COUNT(*) FILTER (WHERE status = 'REJECTED')  AS rejected,
                COUNT(*) FILTER (WHERE status = 'IN_REVIEW') AS in_review,
                COUNT(*) FILTER (WHERE status = 'REMOVED')   AS removed
            FROM thoughts
        """)
        summary = dict(cur.fetchone())

        # Distinct authors for filter dropdown
        cur.execute("SELECT DISTINCT author FROM thoughts ORDER BY author")
        authors = [r["author"] for r in cur.fetchall()]

        # Build WHERE clause
        conditions = []
        params = []
        if status_filter and status_filter in STATUSES:
            conditions.append("t.status = %s")
            params.append(status_filter)
        if author_filter:
            conditions.append("t.author ILIKE %s")
            params.append(f"%{author_filter}%")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cur.execute(f"""
            SELECT
                t.id,
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
            {where}
            ORDER BY {sort} {order_sql} NULLS LAST
        """, params)
        thoughts = [dict(row) for row in cur.fetchall()]
        cur.close()
    except Exception as e:
        error = str(e)
    finally:
        if conn:
            conn.close()

    return render_template(
        "index.html",
        thoughts=thoughts,
        summary=summary,
        error=error,
        authors=authors,
        status_filter=status_filter,
        author_filter=author_filter,
        sort=sort,
        order=order,
        statuses=STATUSES,
    )


# ── Admin ──────────────────────────────────────────────────────────────────────

@app.route("/admin")
def admin():
    conn = None
    error = None
    thoughts = []
    summary = {}
    status_filter = request.args.get("status", "")
    search = request.args.get("search", "").strip()

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status = 'APPROVED')  AS approved,
                COUNT(*) FILTER (WHERE status = 'REJECTED')  AS rejected,
                COUNT(*) FILTER (WHERE status = 'IN_REVIEW') AS in_review,
                COUNT(*) FILTER (WHERE status = 'REMOVED')   AS removed
            FROM thoughts
        """)
        summary = dict(cur.fetchone())

        conditions = []
        params = []
        if status_filter and status_filter in STATUSES:
            conditions.append("t.status = %s")
            params.append(status_filter)
        if search:
            conditions.append("(t.content ILIKE %s OR t.author ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cur.execute(f"""
            SELECT
                t.id,
                t.content,
                t.author,
                t.author_bio,
                t.status,
                t.thumbs_up,
                t.thumbs_down,
                (t.thumbs_up - t.thumbs_down) AS net_rating,
                te.similarity_score,
                t.created_at,
                t.updated_at
            FROM thoughts t
            LEFT JOIN LATERAL (
                SELECT similarity_score
                FROM thought_evaluations
                WHERE thought_id = t.id
                ORDER BY evaluated_at DESC
                LIMIT 1
            ) te ON true
            {where}
            ORDER BY t.updated_at DESC NULLS LAST
        """, params)
        thoughts = [dict(row) for row in cur.fetchall()]
        cur.close()
    except Exception as e:
        error = str(e)
    finally:
        if conn:
            conn.close()

    return render_template(
        "admin.html",
        thoughts=thoughts,
        summary=summary,
        error=error,
        status_filter=status_filter,
        search=search,
        statuses=STATUSES,
    )


@app.route("/admin/update_status", methods=["POST"])
def update_status():
    thought_id = request.form.get("thought_id")
    new_status = request.form.get("status")

    if not thought_id or new_status not in STATUSES:
        flash("Invalid request.", "error")
        return redirect(url_for("admin"))

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE thoughts SET status = %s, updated_at = NOW() WHERE id = %s",
            (new_status, thought_id),
        )
        conn.commit()
        cur.close()
        flash(f"Status updated to {new_status}.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    finally:
        if conn:
            conn.close()

    return redirect(url_for("admin") + f"?status={request.form.get('status_filter','')}&search={request.form.get('search','')}")


@app.route("/admin/delete", methods=["POST"])
def delete_thought():
    thought_id = request.form.get("thought_id")
    if not thought_id:
        flash("Invalid request.", "error")
        return redirect(url_for("admin"))

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM thought_evaluations WHERE thought_id = %s", (thought_id,))
        cur.execute("DELETE FROM thoughts WHERE id = %s", (thought_id,))
        conn.commit()
        cur.close()
        flash("Thought deleted.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    finally:
        if conn:
            conn.close()

    return redirect(url_for("admin"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
