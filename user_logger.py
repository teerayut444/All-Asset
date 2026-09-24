"""
User Access Logger Module
=========================
Logs visitor IP address, session ID, user agent, and timestamps to SQLite database.
Designed for Streamlit-based All Asset NPA Dashboard.
"""

import os
import sqlite3
import hashlib
from datetime import datetime, timezone, timedelta

# Thailand timezone (GMT+7)
TH_TZ = timezone(timedelta(hours=7))

# Database path - stored in 'logs' directory relative to the app
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
DB_PATH = os.path.join(DB_DIR, "user_access.db")


def _ensure_db():
    """Create database directory and table if they don't exist."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            session_id TEXT NOT NULL,
            first_seen TIMESTAMP NOT NULL,
            last_seen TIMESTAMP NOT NULL,
            visit_count INTEGER DEFAULT 1,
            user_agent TEXT,
            page_views INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_session ON access_logs (session_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ip ON access_logs (ip)
    """)
    conn.commit()
    conn.close()


def get_client_ip():
    """
    Attempt to extract the client's real IP address from Streamlit request headers.
    Checks common proxy headers: X-Forwarded-For, X-Real-IP, CF-Connecting-IP.
    Falls back to 'Local/Unknown' if running locally without reverse proxy.
    """
    try:
        import streamlit as st
        headers = st.context.headers
        
        # Priority order for IP detection
        ip_headers = [
            "X-Forwarded-For",
            "X-Real-Ip",
            "Cf-Connecting-Ip",
            "X-Client-Ip",
            "Remote-Addr",
        ]
        
        for header in ip_headers:
            val = headers.get(header)
            if val:
                # X-Forwarded-For may contain multiple IPs: "client, proxy1, proxy2"
                ip = val.split(",")[0].strip()
                if ip and ip not in ("", "unknown", "::1"):
                    return ip
        
        return "127.0.0.1 (Local)"
    except Exception:
        return "Unknown"


def get_user_agent():
    """Extract the User-Agent string from Streamlit request headers."""
    try:
        import streamlit as st
        ua = st.context.headers.get("User-Agent", "Unknown")
        return ua[:500]  # Limit length
    except Exception:
        return "Unknown"


def _get_session_id():
    """Get the current Streamlit session ID."""
    try:
        import streamlit as st
        ctx = st.runtime.scriptrunner.get_script_run_ctx()
        if ctx:
            return ctx.session_id
    except Exception:
        pass
    # Fallback: generate a hash from timestamp
    return hashlib.md5(str(datetime.now()).encode()).hexdigest()[:16]


def log_visit(ip=None, session_id=None, user_agent=None):
    """
    Log a visitor's access. If the same session_id exists, update last_seen and visit_count.
    Otherwise, create a new log entry.
    
    Args:
        ip: Client IP address (auto-detected if None)
        session_id: Streamlit session ID (auto-detected if None)
        user_agent: Browser user agent string (auto-detected if None)
    """
    _ensure_db()
    
    if ip is None:
        ip = get_client_ip()
    if session_id is None:
        session_id = _get_session_id()
    if user_agent is None:
        user_agent = get_user_agent()
    
    now = datetime.now(TH_TZ).strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        cursor = conn.execute(
            "SELECT id, visit_count FROM access_logs WHERE session_id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        
        if row:
            # Update existing session
            conn.execute(
                "UPDATE access_logs SET last_seen = ?, visit_count = visit_count + 1, page_views = page_views + 1 WHERE id = ?",
                (now, row[0])
            )
        else:
            # New session
            conn.execute(
                "INSERT INTO access_logs (ip, session_id, first_seen, last_seen, visit_count, user_agent) VALUES (?, ?, ?, ?, 1, ?)",
                (ip, session_id, now, now, user_agent)
            )
        conn.commit()
    except Exception as e:
        print(f"[UserLogger] Error logging visit: {e}")
    finally:
        conn.close()


def get_all_logs(limit=500):
    """
    Retrieve all access logs, ordered by most recent first.
    
    Returns:
        list of dict: Log entries
    """
    _ensure_db()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT id, ip, session_id, first_seen, last_seen, visit_count, user_agent FROM access_logs ORDER BY last_seen DESC LIMIT ?",
            (limit,)
        )
        rows = [dict(r) for r in cursor.fetchall()]
        return rows
    except Exception:
        return []
    finally:
        conn.close()


def get_stats():
    """
    Get summary statistics.
    
    Returns:
        dict with keys: total_sessions, unique_ips, today_visitors
    """
    _ensure_db()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        today_str = datetime.now(TH_TZ).strftime("%Y-%m-%d")
        
        total = conn.execute("SELECT COUNT(*) FROM access_logs").fetchone()[0]
        unique_ips = conn.execute("SELECT COUNT(DISTINCT ip) FROM access_logs").fetchone()[0]
        today_visitors = conn.execute(
            "SELECT COUNT(*) FROM access_logs WHERE first_seen LIKE ?",
            (f"{today_str}%",)
        ).fetchone()[0]
        
        return {
            "total_sessions": total or 0,
            "unique_ips": unique_ips or 0,
            "today_visitors": today_visitors or 0,
        }
    except Exception:
        return {"total_sessions": 0, "unique_ips": 0, "today_visitors": 0}
    finally:
        conn.close()


def search_logs(query="", date_filter=None, limit=500):
    """
    Search logs by IP address or filter by date.
    
    Args:
        query: IP address substring to search for
        date_filter: Date string (YYYY-MM-DD) to filter logs
        limit: Maximum number of results
    
    Returns:
        list of dict: Matching log entries
    """
    _ensure_db()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conditions = []
        params = []
        
        if query:
            conditions.append("ip LIKE ?")
            params.append(f"%{query}%")
        
        if date_filter:
            conditions.append("(first_seen LIKE ? OR last_seen LIKE ?)")
            params.extend([f"{date_filter}%", f"{date_filter}%"])
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        cursor = conn.execute(
            f"SELECT id, ip, session_id, first_seen, last_seen, visit_count, user_agent FROM access_logs WHERE {where_clause} ORDER BY last_seen DESC LIMIT ?",
            params + [limit]
        )
        return [dict(r) for r in cursor.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def export_logs_csv():
    """
    Export all logs as CSV string.
    
    Returns:
        str: CSV formatted string of all log entries
    """
    import csv
    import io
    
    logs = get_all_logs(limit=99999)
    if not logs:
        return ""
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "ip", "session_id", "first_seen", "last_seen", "visit_count", "user_agent"])
    writer.writeheader()
    writer.writerows(logs)
    return output.getvalue()


def clear_old_logs(days=90):
    """Delete logs older than specified days."""
    _ensure_db()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        cutoff = (datetime.now(TH_TZ) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("DELETE FROM access_logs WHERE last_seen < ?", (cutoff,))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


# Alias for aggregated visitor logs
get_aggregated_visitor_logs = get_all_logs

