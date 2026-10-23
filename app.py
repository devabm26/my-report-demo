from flask import Flask, render_template_string
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

def get_thoughts():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
        LEFT JOIN (
            SELECT DISTINCT ON (thought_id)
                thought_id,
                similarity_score
            FROM thought_evaluations
            ORDER BY thought_id, evaluated_at DESC
        ) te ON t.id = te.thought_id
        ORDER BY t.status, net_rating DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_summary():
    conn = get_db_connection()
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

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Thoughts Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f0f2f5; color: #333; }
  header { background: #1a1a2e; color: white; padding: 20px 32px; }
  header h1 { font-size: 1.6rem; font-weight: 600; }
  header p { font-size: 0.85rem; color: #aaa; margin-top: 4px; }
  .container { max-width: 1400px; margin: 0 auto; padding: 24px 32px; }

  .summary { display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }
  .card { background: white; border-radius: 8px; padding: 18px 24px; flex: 1; min-width: 140px;
          box-shadow: 0 1px 4px rgba(0,0,0,0.08); border-left: 4px solid #ccc; }
  .card.total  { border-color: #4a90e2; }
  .card.approved { border-color: #27ae60; }
  .card.rejected { border-color: #e74c3c; }
  .card.in_review { border-color: #f39c12; }
  .card.removed { border-color: #95a5a6; }
  .card-value { font-size: 2rem; font-weight: 700; }
  .card-label { font-size: 0.78rem; color: #777; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 4px; }

  .table-wrap { background: white; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); overflow: hidden; }
  .table-header { padding: 16px 20px; border-bottom: 1px solid #eee; font-weight: 600; font-size: 1rem; }
  table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
  th { background: #f8f9fa; text-align: left; padding: 10px 14px; font-size: 0.78rem;
       text-transform: uppercase; letter-spacing: 0.05em; color: #666; border-bottom: 1px solid #e8e8e8; }
  td { padding: 10px 14px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #fafbfc; }

  .content-cell { max-width: 360px; }
  .content-text { overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; line-height: 1.45; }

  .badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 0.72rem;
           font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
  .badge-APPROVED  { background: #d4edda; color: #155724; }
  .badge-REJECTED  { background: #f8d7da; color: #721c24; }
  .badge-IN_REVIEW { background: #fff3cd; color: #856404; }
  .badge-REMOVED   { background: #e2e3e5; color: #383d41; }

  .net-pos { color: #27ae60; font-weight: 600; }
  .net-neg { color: #e74c3c; font-weight: 600; }
  .net-zero { color: #888; }

  .error-box { background: #f8d7da; color: #721c24; border-radius: 8px; padding: 20px 24px; margin: 24px 0; }
  .error-box h3 { margin-bottom: 8px; }

  tfoot td { background: #f8f9fa; font-weight: 600; color: #555; border-top: 2px solid #e0e0e0; }
</style>
</head>
<body>
<header>
  <h1>Thoughts Dashboard</h1>
  <p>Reporting on thoughts database &mdash; {{ thoughts|length }} records loaded</p>
</header>
<div class="container">

  {% if error %}
  <div class="error-box">
    <h3>Database Connection Error</h3>
    <p>{{ error }}</p>
  </div>
  {% else %}

  <div class="summary">
    <div class="card total">
      <div class="card-value">{{ summary.total }}</div>
      <div class="card-label">Total Thoughts</div>
    </div>
    <div class="card approved">
      <div class="card-value">{{ summary.approved }}</div>
      <div class="card-label">Approved</div>
    </div>
    <div class="card rejected">
      <div class="card-value">{{ summary.rejected }}</div>
      <div class="card-label">Rejected</div>
    </div>
    <div class="card in_review">
      <div class="card-value">{{ summary.in_review }}</div>
      <div class="card-label">In Review</div>
    </div>
    <div class="card removed">
      <div class="card-value">{{ summary.removed }}</div>
      <div class="card-label">Removed</div>
    </div>
  </div>

  <div class="table-wrap">
    <div class="table-header">All Thoughts</div>
    <table>
      <thead>
        <tr>
          <th>Content</th>
          <th>Author</th>
          <th>Status</th>
          <th>&#128077; Up</th>
          <th>&#128078; Down</th>
          <th>Net Rating</th>
          <th>Similarity Score</th>
        </tr>
      </thead>
      <tbody>
        {% for t in thoughts %}
        <tr>
          <td class="content-cell"><div class="content-text" title="{{ t.content }}">{{ t.content }}</div></td>
          <td>{{ t.author }}</td>
          <td><span class="badge badge-{{ t.status }}">{{ t.status }}</span></td>
          <td>{{ t.thumbs_up }}</td>
          <td>{{ t.thumbs_down }}</td>
          <td>
            {% if t.net_rating > 0 %}
              <span class="net-pos">+{{ t.net_rating }}</span>
            {% elif t.net_rating < 0 %}
              <span class="net-neg">{{ t.net_rating }}</span>
            {% else %}
              <span class="net-zero">0</span>
            {% endif %}
          </td>
          <td>
            {% if t.similarity_score is not none %}
              {{ "%.4f"|format(t.similarity_score|float) }}
            {% else %}
              <span style="color:#bbb;">—</span>
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

</div>
</body>
</html>
"""

@app.route("/")
def index():
    try:
        thoughts = get_thoughts()
        summary = get_summary()
        return render_template_string(TEMPLATE, thoughts=thoughts, summary=summary, error=None)
    except Exception as e:
        return render_template_string(TEMPLATE, thoughts=[], summary={}, error=str(e))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
