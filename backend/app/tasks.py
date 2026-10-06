"""
Tasks API. Every query is scoped with `WHERE user_id = %s`, so one user can
never read or modify another user's tasks. Requests for someone else's task
return 404 (not 403), so the API doesn't reveal that the task exists.
"""

import math
from datetime import date

from flask import Blueprint, g, jsonify, request

from .auth import require_auth
from .db import get_conn
from .errors import ApiError

bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")

STATUSES = ("todo", "in_progress", "done")
PRIORITIES = ("low", "medium", "high")

# Whitelisted sort keys -> SQL fragments. User input never reaches SQL text.
SORTS = {
    "position": "status, position, id",
    "created_at": "created_at, id",
    "updated_at": "updated_at, id",
    "due_date": "due_date NULLS LAST, id",
    "priority": "CASE priority WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END, id",
    "title": "lower(title), id",
}

COLUMNS = "id, title, description, status, priority, due_date, position, created_at, updated_at"


def serialize(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "priority": row["priority"],
        "due_date": row["due_date"].isoformat() if row["due_date"] else None,
        "position": row["position"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


def validate(data, *, partial: bool) -> dict:
    """Validate a task body. Returns only the fields that were provided."""
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object.")
    clean, fields = {}, {}

    if "title" in data or not partial:
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            fields["title"] = "Title is required."
        elif len(title.strip()) > 200:
            fields["title"] = "Title must be at most 200 characters."
        else:
            clean["title"] = title.strip()

    if "description" in data:
        desc = data["description"]
        if desc is not None and not isinstance(desc, str):
            fields["description"] = "Description must be text."
        elif desc and len(desc) > 5000:
            fields["description"] = "Description must be at most 5000 characters."
        else:
            clean["description"] = desc or ""

    if "status" in data:
        if data["status"] not in STATUSES:
            fields["status"] = f"Status must be one of {', '.join(STATUSES)}."
        else:
            clean["status"] = data["status"]

    if "priority" in data:
        if data["priority"] not in PRIORITIES:
            fields["priority"] = f"Priority must be one of {', '.join(PRIORITIES)}."
        else:
            clean["priority"] = data["priority"]

    if "due_date" in data:
        due = data["due_date"]
        if due in (None, ""):
            clean["due_date"] = None
        else:
            try:
                clean["due_date"] = date.fromisoformat(due)
            except (TypeError, ValueError):
                fields["due_date"] = "Due date must be YYYY-MM-DD."

    if "position" in data:
        pos = data["position"]
        if isinstance(pos, bool) or not isinstance(pos, (int, float)) or not math.isfinite(pos):
            fields["position"] = "Position must be a finite number."
        else:
            clean["position"] = float(pos)

    if fields:
        raise ApiError("Please fix the highlighted fields.", 422, fields)
    return clean


def _body():
    data = request.get_json(silent=True)
    if data is None:
        raise ApiError("Request body must be valid JSON.")
    return data


def _with_rate_headers(response):
    response.headers["X-RateLimit-Remaining"] = str(getattr(g, "rate_remaining", ""))
    return response


# ---------------------------------------------------------------- list

@bp.get("")
@require_auth
def list_tasks():
    args = request.args
    try:
        page = int(args.get("page", 1))
        per_page = int(args.get("per_page", 50))
    except ValueError:
        raise ApiError("page and per_page must be integers.")
    if not 1 <= page <= 100_000 or not 1 <= per_page <= 500:
        raise ApiError("page must be 1-100000 and per_page 1-500.")

    where, params = ["user_id = %s"], [g.user_id]
    if status := args.get("status"):
        if status not in STATUSES:
            raise ApiError(f"Invalid status filter. Use one of {', '.join(STATUSES)}.")
        where.append("status = %s")
        params.append(status)
    if priority := args.get("priority"):
        if priority not in PRIORITIES:
            raise ApiError(f"Invalid priority filter. Use one of {', '.join(PRIORITIES)}.")
        where.append("priority = %s")
        params.append(priority)
    if q := args.get("q", "").strip():
        # Same expression as the trigram index, so Postgres can use it.
        # Escape LIKE wildcards so a search for "50%" means a literal "50%".
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("(title || ' ' || description) ILIKE %s")
        params.append(f"%{escaped}%")
    if args.get("overdue") == "true":
        where.append("due_date < CURRENT_DATE AND status <> 'done'")

    sort = args.get("sort", "position")
    desc = sort.startswith("-")
    key = sort.lstrip("-")
    if key not in SORTS:
        raise ApiError(f"Invalid sort. Use one of {', '.join(SORTS)} (prefix '-' for descending).")
    direction = "DESC" if desc else "ASC"
    order_parts = []
    for part in (p.strip() for p in SORTS[key].split(",")):
        if part.endswith(" NULLS LAST"):  # keep undated tasks last in both directions
            order_parts.append(f"{part.removesuffix(' NULLS LAST')} {direction} NULLS LAST")
        else:
            order_parts.append(f"{part} {direction}")
    order = ", ".join(order_parts)

    where_sql = " AND ".join(where)
    with get_conn() as conn:
        total = conn.execute(f"SELECT count(*) AS n FROM tasks WHERE {where_sql}", params).fetchone()["n"]
        rows = conn.execute(
            f"SELECT {COLUMNS} FROM tasks WHERE {where_sql} ORDER BY {order} LIMIT %s OFFSET %s",
            [*params, per_page, (page - 1) * per_page],
        ).fetchall()

    return _with_rate_headers(jsonify({
        "tasks": [serialize(r) for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": math.ceil(total / per_page),
    }))


# ---------------------------------------------------------------- create

@bp.post("")
@require_auth
def create_task():
    fields = validate(_body(), partial=False)
    status = fields.get("status", "todo")
    with get_conn() as conn:
        row = conn.execute(
            f"""INSERT INTO tasks (user_id, title, description, status, priority, due_date, position)
                VALUES (%s, %s, %s, %s, %s, %s,
                        COALESCE(%s, (SELECT max(position) FROM tasks WHERE user_id = %s AND status = %s) + 1, 1))
                RETURNING {COLUMNS}""",
            (g.user_id, fields["title"], fields.get("description", ""), status,
             fields.get("priority", "medium"), fields.get("due_date"),
             fields.get("position"), g.user_id, status),
        ).fetchone()
    resp = jsonify(serialize(row))
    resp.status_code = 201
    resp.headers["Location"] = f"/api/tasks/{row['id']}"
    return _with_rate_headers(resp)


# ---------------------------------------------------------------- read / update / delete

def _fetch_owned(conn, task_id: int):
    row = conn.execute(f"SELECT {COLUMNS} FROM tasks WHERE id = %s AND user_id = %s",
                       (task_id, g.user_id)).fetchone()
    if row is None:
        raise ApiError("Task not found.", 404)
    return row


@bp.get("/<int:task_id>")
@require_auth
def get_task(task_id):
    with get_conn() as conn:
        return _with_rate_headers(jsonify(serialize(_fetch_owned(conn, task_id))))


@bp.route("/<int:task_id>", methods=["PATCH", "PUT"])
@require_auth
def update_task(task_id):
    is_put = request.method == "PUT"
    fields = validate(_body(), partial=not is_put)
    if is_put:  # PUT replaces the task: omitted fields reset to their defaults
        fields = {"description": "", "status": "todo", "priority": "medium", "due_date": None, **fields}
    if not fields:
        raise ApiError("No fields to update.")

    with get_conn() as conn:
        current = _fetch_owned(conn, task_id)
        # Moving to another column without an explicit position -> append at the bottom.
        if "status" in fields and fields["status"] != current["status"] and "position" not in fields:
            top = conn.execute("SELECT max(position) AS m FROM tasks WHERE user_id = %s AND status = %s",
                               (g.user_id, fields["status"])).fetchone()["m"]
            fields["position"] = (top or 0) + 1

        # Column names come from validate()'s fixed keys, never from user input.
        assignments = ", ".join(f"{col} = %s" for col in fields)
        row = conn.execute(
            f"UPDATE tasks SET {assignments}, updated_at = now() WHERE id = %s AND user_id = %s "
            f"RETURNING {COLUMNS}",
            [*fields.values(), task_id, g.user_id],
        ).fetchone()
    return _with_rate_headers(jsonify(serialize(row)))


@bp.delete("/<int:task_id>")
@require_auth
def delete_task(task_id):
    with get_conn() as conn:
        deleted = conn.execute("DELETE FROM tasks WHERE id = %s AND user_id = %s",
                               (task_id, g.user_id)).rowcount
    if not deleted:
        raise ApiError("Task not found.", 404)
    return "", 204


# ---------------------------------------------------------------- stats

@bp.get("/stats")
@require_auth
def stats():
    with get_conn() as conn:
        row = conn.execute(
            """SELECT count(*)                                                   AS total,
                      count(*) FILTER (WHERE status = 'todo')                    AS todo,
                      count(*) FILTER (WHERE status = 'in_progress')             AS in_progress,
                      count(*) FILTER (WHERE status = 'done')                    AS done,
                      count(*) FILTER (WHERE priority = 'high' AND status <> 'done') AS high_open,
                      count(*) FILTER (WHERE due_date < CURRENT_DATE AND status <> 'done') AS overdue,
                      count(*) FILTER (WHERE due_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 6
                                       AND status <> 'done')                     AS due_this_week
               FROM tasks WHERE user_id = %s""",
            (g.user_id,),
        ).fetchone()
    total = row["total"]
    return _with_rate_headers(jsonify({
        "total": total,
        "by_status": {s: row[s] for s in STATUSES},
        "high_priority_open": row["high_open"],
        "overdue": row["overdue"],
        "due_this_week": row["due_this_week"],
        "completion_rate": round(row["done"] / total, 3) if total else 0.0,
    }))
