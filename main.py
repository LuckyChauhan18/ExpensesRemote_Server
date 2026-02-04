from fastmcp import FastMCP
import os
import aiosqlite
import tempfile
import sqlite3
import json

# -------------------------
# Paths (Render-safe)
# -------------------------
TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

print(f"[MCP] Database path: {DB_PATH}")

mcp = FastMCP("ExpenseTracker")

# -------------------------
# DB Initialization (sync)
# -------------------------
def init_db():
    try:
        with sqlite3.connect(DB_PATH) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""
                CREATE TABLE IF NOT EXISTS expenses(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                )
            """)
            # write test
            c.execute(
                "INSERT OR IGNORE INTO expenses(date, amount, category) VALUES ('2000-01-01', 0, 'test')"
            )
            c.execute("DELETE FROM expenses WHERE category='test'")
        print("[MCP] Database initialized")
    except Exception as e:
        print("[MCP] DB init failed:", e)
        raise



# -------------------------
# MCP Tools
# -------------------------
@mcp.tool()
async def add_expense(date, amount, category, subcategory="", note=""):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO expenses(date, amount, category, subcategory, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (date, amount, category, subcategory, note),
        )
        await db.commit()
        return {
            "status": "success",
            "id": cur.lastrowid
        }

@mcp.tool()
async def list_expenses(start_date, end_date):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT id, date, amount, category, subcategory, note
            FROM expenses
            WHERE date BETWEEN ? AND ?
            ORDER BY date DESC, id DESC
            """,
            (start_date, end_date),
        )
        cols = [c[0] for c in cur.description]
        rows = await cur.fetchall()
        return [dict(zip(cols, r)) for r in rows]

@mcp.tool()
async def summarize(start_date, end_date, category=None):
    query = """
        SELECT category, SUM(amount) as total, COUNT(*) as count
        FROM expenses
        WHERE date BETWEEN ? AND ?
    """
    params = [start_date, end_date]

    if category:
        query += " AND category = ?"
        params.append(category)

    query += " GROUP BY category ORDER BY total DESC"

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(query, params)
        cols = [c[0] for c in cur.description]
        rows = await cur.fetchall()
        return [dict(zip(cols, r)) for r in rows]

# -------------------------
# MCP Resource
# -------------------------
@mcp.resource("expense:///categories", mime_type="application/json")
def categories():
    try:
        with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return json.dumps({
            "categories": [
                "Food & Dining",
                "Transportation",
                "Shopping",
                "Entertainment",
                "Bills & Utilities",
                "Healthcare",
                "Travel",
                "Education",
                "Business",
                "Other"
            ]
        }, indent=2)

# -------------------------
# HTTP Server (Render)
# -------------------------
if __name__ == "__main__":
    print(f"[MCP] Database path: {DB_PATH}")
    init_db()  # move here

    port = int(os.environ.get("PORT", 8000))
    mcp.run(host="0.0.0.0", port=port)

