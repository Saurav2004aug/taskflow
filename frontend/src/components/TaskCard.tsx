import type { DragEvent } from "react";
import type { Task } from "../api/types";
import { formatDue, isOverdue } from "../lib/board";

interface Props {
  task: Task;
  dragging: boolean;
  onOpen: (task: Task) => void;
  onDragStart: (task: Task) => void;
  onDragEnd: () => void;
}

export default function TaskCard({ task, dragging, onOpen, onDragStart, onDragEnd }: Props) {
  const overdue = isOverdue(task);

  function handleDragStart(e: DragEvent) {
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(task.id));
    onDragStart(task);
  }

  return (
    <button
      type="button"
      className={`card priority-${task.priority}${dragging ? " dragging" : ""}${task.status === "done" ? " is-done" : ""}`}
      draggable
      onDragStart={handleDragStart}
      onDragEnd={onDragEnd}
      onClick={() => onOpen(task)}
      data-task-id={task.id}
      aria-label={`${task.title}, ${task.priority} priority${task.due_date ? `, due ${task.due_date}` : ""}`}
    >
      <span className="card-title">{task.title}</span>
      {task.description && <span className="card-desc">{task.description}</span>}
      <span className="card-meta">
        <span className={`pill pill-${task.priority}`}>{task.priority}</span>
        {task.due_date && (
          <span className={`due${overdue ? " due-overdue" : ""}`}>
            {overdue ? "⚠ " : "📅 "}
            {formatDue(task.due_date)}
          </span>
        )}
      </span>
    </button>
  );
}
