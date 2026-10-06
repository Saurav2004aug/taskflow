import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { PRIORITIES, STATUSES, STATUS_LABELS, type Priority, type Status, type Task, type TaskInput } from "../api/types";

interface Props {
  task: Task | null; // null = create a new task
  defaultStatus: Status;
  onSave: (input: TaskInput) => Promise<void>;
  onDelete?: () => Promise<void>;
  onClose: () => void;
}

export default function TaskModal({ task, defaultStatus, onSave, onDelete, onClose }: Props) {
  const [title, setTitle] = useState(task?.title ?? "");
  const [description, setDescription] = useState(task?.description ?? "");
  const [status, setStatus] = useState<Status>(task?.status ?? defaultStatus);
  const [priority, setPriority] = useState<Priority>(task?.priority ?? "medium");
  const [dueDate, setDueDate] = useState(task?.due_date ?? "");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const titleRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    titleRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    setFields({});
    try {
      await action();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      if (err instanceof ApiError) setFields(err.fields);
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    run(() => onSave({ title, description, status, priority, due_date: dueDate || null }));
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title" onSubmit={onSubmit}>
        <header className="modal-head">
          <h2 id="modal-title">{task ? "Edit task" : "New task"}</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>

        {error && (
          <div className="alert" role="alert">
            {error}
          </div>
        )}

        <label className="field">
          <span>Title</span>
          <input ref={titleRef} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} required />
          {fields.title && <small className="field-error">{fields.title}</small>}
        </label>

        <label className="field">
          <span>Description</span>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4} maxLength={5000} />
        </label>

        <div className="field-row">
          <label className="field">
            <span>Status</span>
            <select value={status} onChange={(e) => setStatus(e.target.value as Status)}>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s]}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Priority</span>
            <select value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p[0].toUpperCase() + p.slice(1)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Due date</span>
            <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            {fields.due_date && <small className="field-error">{fields.due_date}</small>}
          </label>
        </div>

        <footer className="modal-foot">
          {task && onDelete && (
            <button
              type="button"
              className="btn btn-danger-ghost"
              disabled={busy}
              onClick={() => run(onDelete)}
            >
              Delete
            </button>
          )}
          <span className="spacer" />
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? "Saving…" : task ? "Save changes" : "Create task"}
          </button>
        </footer>
      </form>
    </div>
  );
}
