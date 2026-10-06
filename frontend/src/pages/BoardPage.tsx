import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { api, ApiError } from "../api/client";
import { STATUSES, STATUS_LABELS, type Stats, type Status, type Task, type TaskInput, type User } from "../api/types";
import StatsBar from "../components/StatsBar";
import TaskCard from "../components/TaskCard";
import TaskModal from "../components/TaskModal";
import { useAuth } from "../hooks/useAuth";
import { dropPosition, groupByStatus } from "../lib/board";

interface DropTarget {
  status: Status;
  index: number;
}

type ModalState = { task: Task | null; status: Status } | null;

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

export default function BoardPage({ user }: { user: User }) {
  const { logout } = useAuth();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [priority, setPriority] = useState("");
  const [modal, setModal] = useState<ModalState>(null);
  const [dragging, setDragging] = useState<Task | null>(null);
  const [dropTarget, setDropTarget] = useState<DropTarget | null>(null);
  const columnRefs = useRef<Partial<Record<Status, HTMLDivElement | null>>>({});
  // Drag state lives in refs as well as state: drag events can fire before
  // React re-renders, so handlers must not rely on a possibly-stale closure.
  const dragRef = useRef<Task | null>(null);
  const dropRef = useRef<DropTarget | null>(null);
  const q = useDebounced(search.trim(), 250);

  const showError = useCallback((err: unknown) => {
    setError(err instanceof ApiError ? err.message : "Something went wrong.");
  }, []);

  const refreshStats = useCallback(() => {
    api.stats().then(setStats).catch(() => {});
  }, []);

  // Load tasks whenever the search or filter changes. The `cancelled` flag
  // drops responses to superseded requests, so a slow old search can't
  // overwrite a newer one.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .listTasks({ q, priority })
      .then((page) => !cancelled && setTasks(page.tasks))
      .catch((err) => !cancelled && showError(err))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [q, priority, showError]);

  useEffect(refreshStats, [refreshStats]);

  const columns = useMemo(() => groupByStatus(tasks), [tasks]);

  // ------------------------------------------------------------- CRUD

  async function saveTask(input: TaskInput) {
    if (modal?.task) {
      const updated = await api.updateTask(modal.task.id, input);
      setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    } else {
      const created = await api.createTask(input);
      setTasks((prev) => [...prev, created]);
    }
    refreshStats();
  }

  async function deleteTask() {
    if (!modal?.task) return;
    const id = modal.task.id;
    await api.deleteTask(id);
    setTasks((prev) => prev.filter((t) => t.id !== id));
    refreshStats();
  }

  // ------------------------------------------------------------- drag and drop

  /** Which slot in the column is the pointer over? Compare against card midpoints. */
  function slotAt(status: Status, clientY: number): number {
    const cards = Array.from(
      columnRefs.current[status]?.querySelectorAll<HTMLElement>(".card:not(.dragging)") ?? [],
    );
    const index = cards.findIndex((el) => {
      const r = el.getBoundingClientRect();
      return clientY < r.top + r.height / 2;
    });
    return index === -1 ? cards.length : index;
  }

  function startDrag(task: Task) {
    dragRef.current = task;
    setDragging(task);
  }

  function onDragOver(e: DragEvent, status: Status) {
    if (!dragRef.current) return;
    e.preventDefault(); // allow dropping here
    const index = slotAt(status, e.clientY);
    const prev = dropRef.current;
    if (prev?.status !== status || prev.index !== index) {
      dropRef.current = { status, index };
      setDropTarget(dropRef.current);
    }
  }

  function endDrag() {
    dragRef.current = null;
    dropRef.current = null;
    setDragging(null);
    setDropTarget(null);
  }

  async function onDrop(e: DragEvent, status: Status) {
    e.preventDefault();
    const task = dragRef.current;
    const target = dropRef.current ?? { status, index: slotAt(status, e.clientY) };
    endDrag();
    if (!task) return;

    // Dropped back into its own slot: nothing to do.
    if (task.status === target.status && target.index === columns[task.status].findIndex((t) => t.id === task.id)) return;

    const others = columns[target.status].filter((t) => t.id !== task.id);
    const position = dropPosition(others, target.index);

    // Optimistic update: move the card now, and roll back if the server says no.
    const before = tasks;
    setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, status: target.status, position } : t)));
    try {
      const saved = await api.updateTask(task.id, { status: target.status, position });
      setTasks((prev) => prev.map((t) => (t.id === saved.id ? saved : t)));
      if (task.status !== target.status) refreshStats();
    } catch (err) {
      setTasks(before);
      showError(err);
    }
  }

  // ------------------------------------------------------------- render

  const initials = user.name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">✓</span> TaskFlow
        </div>
        <div className="topbar-right">
          <span className="avatar" title={user.email}>
            {initials}
          </span>
          <span className="hello">Hi, {user.name.split(" ")[0]}</span>
          <button className="btn btn-ghost" onClick={() => logout()}>
            Log out
          </button>
        </div>
      </header>

      <main className="board-page">
        <StatsBar stats={stats} />

        <div className="toolbar">
          <input
            className="search"
            type="search"
            placeholder="Search tasks…"
            aria-label="Search tasks"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select aria-label="Filter by priority" value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="">All priorities</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <span className="spacer" />
          <button className="btn btn-primary" onClick={() => setModal({ task: null, status: "todo" })}>
            + New task
          </button>
        </div>

        {error && (
          <div className="alert alert-dismissable" role="alert">
            {error}
            <button className="icon-btn" aria-label="Dismiss" onClick={() => setError(null)}>
              ✕
            </button>
          </div>
        )}

        <div className={`board${loading ? " is-loading" : ""}`}>
          {STATUSES.map((status) => {
            const list = columns[status];
            const showSlot = dropTarget?.status === status;
            // The dragged card stays mounted (faded) - removing the drag source
            // mid-drag cancels the drag in Chrome. Slots count the other cards only.
            let slot = 0;
            const stationary = list.filter((t) => t.id !== dragging?.id).length;
            return (
              <section
                key={status}
                className={`column column-${status}${showSlot ? " drop-active" : ""}`}
                onDragOver={(e) => onDragOver(e, status)}
                onDrop={(e) => onDrop(e, status)}
                aria-label={STATUS_LABELS[status]}
              >
                <header className="column-head">
                  <span className="column-dot" />
                  <h2>{STATUS_LABELS[status]}</h2>
                  <span className="count">{list.length}</span>
                  <button
                    className="icon-btn add-btn"
                    aria-label={`Add task to ${STATUS_LABELS[status]}`}
                    onClick={() => setModal({ task: null, status })}
                  >
                    +
                  </button>
                </header>
                <div className="cards" ref={(el) => void (columnRefs.current[status] = el)}>
                  {list.map((task) => {
                    const isDragged = task.id === dragging?.id;
                    const lineHere = showSlot && !isDragged && dropTarget.index === slot;
                    if (!isDragged) slot++;
                    return (
                      <Fragment key={task.id}>
                        {lineHere && <div className="drop-line" />}
                        <TaskCard
                          task={task}
                          dragging={isDragged}
                          onOpen={(t) => setModal({ task: t, status: t.status })}
                          onDragStart={startDrag}
                          onDragEnd={endDrag}
                        />
                      </Fragment>
                    );
                  })}
                  {showSlot && dropTarget.index >= stationary && <div className="drop-line" />}
                  {list.length === 0 && (
                    // Stays mounted while dragging (only hidden): if the element under the
                    // pointer is removed mid-drag, the browser never fires `drop`.
                    <p className={`empty${showSlot ? " empty-hidden" : ""}`}>
                      {q || priority ? "No matching tasks" : "Drop tasks here"}
                    </p>
                  )}
                </div>
              </section>
            );
          })}
        </div>
      </main>

      {modal && (
        <TaskModal
          task={modal.task}
          defaultStatus={modal.status}
          onSave={saveTask}
          onDelete={modal.task ? deleteTask : undefined}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  );
}
