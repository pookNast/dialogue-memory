#!/usr/bin/env python3
"""Health check for dialogue-memory system."""

import json
import os
import sqlite3
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import DB_PATH, QDRANT_COLLECTION, QDRANT_URL


def check_db() -> dict:
    """Check SQLite database health."""
    result = {"name": "database", "status": "unknown", "details": {}}

    db_path = str(DB_PATH)

    if not os.path.exists(db_path):
        result["status"] = "not_initialized"
        result["details"]["path"] = db_path
        return result

    result["details"]["path"] = db_path
    result["details"]["size_bytes"] = os.path.getsize(db_path)

    try:
        conn = sqlite3.connect(db_path, timeout=5)
        cur = conn.cursor()

        # PRAGMA quick_check
        check = cur.execute("PRAGMA quick_check").fetchone()
        if check[0] != "ok":
            result["status"] = "corrupt"
            result["details"]["integrity"] = check[0]
            conn.close()
            return result

        result["details"]["integrity"] = "ok"

        # Row count
        count = cur.execute("SELECT COUNT(*) FROM dialogue_turns").fetchone()[0]
        result["details"]["row_count"] = count

        # Embedding backlog
        backlog = cur.execute(
            "SELECT COUNT(*) FROM dialogue_turns WHERE embedding_done = 0"
        ).fetchone()[0]
        result["details"]["embedding_backlog"] = backlog

        # FTS5 integrity
        try:
            cur.execute("SELECT count(*) FROM dialogue_fts LIMIT 1")
            result["details"]["fts5"] = "ok"
        except sqlite3.OperationalError:
            result["details"]["fts5"] = "table_not_found"

        conn.close()
        result["status"] = "healthy"

    except sqlite3.Error as e:
        result["status"] = "error"
        result["details"]["error"] = str(e)

    return result


def check_qdrant() -> dict:
    """Check Qdrant reachability and collection info."""
    result = {"name": "qdrant", "status": "unknown", "details": {"url": QDRANT_URL}}

    try:
        resp = urllib.request.urlopen(f"{QDRANT_URL}/healthz", timeout=3)
        if resp.status == 200:
            result["status"] = "healthy"
        else:
            result["status"] = "degraded"
            result["details"]["http_status"] = resp.status

        # Collection point count
        coll_resp = urllib.request.urlopen(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}", timeout=3
        )
        if coll_resp.status == 200:
            info = json.loads(coll_resp.read()).get("result", {})
            count = info.get("points_count", 0)
            result["details"]["points_count"] = count

    except urllib.error.HTTPError as e:
        if e.code == 404:
            result["details"]["collection"] = "not_found"
            result["status"] = "healthy"  # Qdrant up, collection just not created yet
        else:
            result["status"] = "degraded"
            result["details"]["http_status"] = e.code
    except urllib.error.URLError:
        result["status"] = "unreachable"
    except Exception as e:
        result["status"] = "error"
        result["details"]["error"] = str(e)

    return result


def run_checks(json_output: bool = False) -> int:
    """Run all health checks. Returns 0 if healthy, 1 otherwise."""
    checks = [check_db(), check_qdrant()]

    healthy = all(c["status"] in ("healthy", "not_initialized") for c in checks)

    if json_output:
        output = {
            "healthy": healthy,
            "checks": checks,
        }
        print(json.dumps(output, indent=2))
    else:
        for c in checks:
            status = c["status"].upper()
            name = c["name"]
            details = c.get("details", {})

            parts = [f"[{status}] {name}"]

            if name == "database":
                if status == "NOT_INITIALIZED":
                    parts.append(f"(path: {details.get('path', '?')})")
                else:
                    parts.append(
                        f"(rows: {details.get('row_count', '?')}, "
                        f"backlog: {details.get('embedding_backlog', '?')}, "
                        f"fts5: {details.get('fts5', '?')}, "
                        f"size: {details.get('size_bytes', 0)} bytes)"
                    )

            elif name == "qdrant":
                parts.append(
                    f"(url: {details.get('url', '?')}, "
                    f"points: {details.get('points_count', '?')})"
                )

            print(" ".join(parts))

    return 0 if healthy else 1


def main():
    json_mode = "--json" in sys.argv
    sys.exit(run_checks(json_output=json_mode))


if __name__ == "__main__":
    main()
