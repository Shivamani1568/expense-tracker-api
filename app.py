"""
Expense Tracker API — Flask Backend
====================================
Endpoints:
    POST   /expenses          — add a new expense
    GET    /expenses          — list all (optional filters: category, start_date, end_date)
    GET    /expenses/summary  — totals by category
    GET    /expenses/<id>     — single expense
    DELETE /expenses/<id>     — delete an expense
    GET    /categories        — list all categories

Run:
    python app.py
    → http://localhost:5000
"""

from flask import Flask, request, jsonify
from db import get_connection, init_db

app = Flask(__name__)


# ---------------------------------------------------------------------------
# CORS — allow the frontend (opened from a file or another port) to call API
# ---------------------------------------------------------------------------
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
    return response


# ---------------------------------------------------------------------------
# Helper: turn a sqlite3.Row into a plain dict
# ---------------------------------------------------------------------------
def row_to_dict(row):
    return dict(row) if row else None


# ===========================================================================
#  CATEGORIES
# ===========================================================================
@app.route("/categories", methods=["GET"])
def list_categories():
    """GET /categories — return every category."""
    conn = get_connection()
    rows = conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
    conn.close()
    return jsonify([row_to_dict(r) for r in rows])


# ===========================================================================
#  CREATE / LIST EXPENSES
# ===========================================================================
@app.route("/expenses", methods=["GET", "POST"])
def handle_expenses():
    if request.method == "POST":
        return _create_expense()
    return _list_expenses()


def _create_expense():
    """
    POST /expenses
    Body (JSON): { amount, category, description?, date }
    'category' can be the name (string) or the id (int).
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    # --- validate required fields ---
    amount = data.get("amount")
    category = data.get("category")
    date = data.get("date")

    errors = []
    if amount is None:
        errors.append("'amount' is required")
    elif not isinstance(amount, (int, float)) or amount <= 0:
        errors.append("'amount' must be a positive number")

    if category is None:
        errors.append("'category' is required")

    if not date:
        errors.append("'date' is required (YYYY-MM-DD)")

    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    description = data.get("description", "")

    # --- resolve category to an id ---
    conn = get_connection()

    if isinstance(category, int):
        cat_row = conn.execute(
            "SELECT id FROM categories WHERE id = ?", (category,)
        ).fetchone()
    else:
        cat_row = conn.execute(
            "SELECT id FROM categories WHERE name = ? COLLATE NOCASE", (category,)
        ).fetchone()

    if not cat_row:
        # Auto-create the category if it doesn't exist yet
        cur = conn.execute("INSERT INTO categories (name) VALUES (?)", (str(category),))
        category_id = cur.lastrowid
    else:
        category_id = cat_row["id"]

    # --- insert the expense ---
    cur = conn.execute(
        """INSERT INTO expenses (amount, category_id, description, date)
           VALUES (?, ?, ?, ?)""",
        (amount, category_id, description, date),
    )
    conn.commit()

    # fetch the newly created row to return it
    expense = conn.execute(
        """SELECT e.id, e.amount, c.name AS category, e.description,
                  e.date, e.created_at
           FROM expenses e
           JOIN categories c ON e.category_id = c.id
           WHERE e.id = ?""",
        (cur.lastrowid,),
    ).fetchone()
    conn.close()

    return jsonify(row_to_dict(expense)), 201


def _list_expenses():
    """
    GET /expenses
    Query params (all optional):
        category   — filter by category name
        start_date — inclusive lower bound (YYYY-MM-DD)
        end_date   — inclusive upper bound (YYYY-MM-DD)
    """
    category = request.args.get("category")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    query = """
        SELECT e.id, e.amount, c.name AS category, e.description,
               e.date, e.created_at
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE 1=1
    """
    params = []

    if category:
        query += " AND c.name = ? COLLATE NOCASE"
        params.append(category)
    if start_date:
        query += " AND e.date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND e.date <= ?"
        params.append(end_date)

    query += " ORDER BY e.date DESC, e.id DESC"

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()

    return jsonify([row_to_dict(r) for r in rows])


# ===========================================================================
#  EXPENSE SUMMARY  (totals by category)
# ===========================================================================
@app.route("/expenses/summary", methods=["GET"])
def expense_summary():
    """
    GET /expenses/summary
    Returns total amount and count per category.
    Optional query params: start_date, end_date
    """
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    query = """
        SELECT c.name            AS category,
               COUNT(e.id)       AS count,
               ROUND(SUM(e.amount), 2) AS total
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE 1=1
    """
    params = []

    if start_date:
        query += " AND e.date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND e.date <= ?"
        params.append(end_date)

    query += " GROUP BY c.name ORDER BY total DESC"

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()

    # Also compute grand total
    grand = conn.execute(
        "SELECT ROUND(SUM(amount), 2) AS grand_total, COUNT(*) AS total_count FROM expenses"
    ).fetchone()
    conn.close()

    return jsonify({
        "by_category": [row_to_dict(r) for r in rows],
        "grand_total": grand["grand_total"] or 0,
        "total_count": grand["total_count"] or 0,
    })


# ===========================================================================
#  GET SINGLE EXPENSE
# ===========================================================================
@app.route("/expenses/<int:expense_id>", methods=["GET"])
def get_expense(expense_id):
    """GET /expenses/:id"""
    conn = get_connection()
    row = conn.execute(
        """SELECT e.id, e.amount, c.name AS category, e.description,
                  e.date, e.created_at
           FROM expenses e
           JOIN categories c ON e.category_id = c.id
           WHERE e.id = ?""",
        (expense_id,),
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": f"Expense {expense_id} not found"}), 404

    return jsonify(row_to_dict(row))


# ===========================================================================
#  DELETE EXPENSE
# ===========================================================================
@app.route("/expenses/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    """DELETE /expenses/:id"""
    conn = get_connection()

    # check it exists first
    row = conn.execute("SELECT id FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": f"Expense {expense_id} not found"}), 404

    conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": f"Expense {expense_id} deleted"}), 200


# ===========================================================================
#  BOOT
# ===========================================================================
if __name__ == "__main__":
    init_db()
    print("\n🚀  Expense Tracker API running on http://localhost:5000\n")
    app.run(debug=True, port=8080)
