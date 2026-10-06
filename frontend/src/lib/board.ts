import type { Status, Task } from "../api/types";

/**
 * Fractional indexing: the position for a card dropped between two others.
 *
 * Moving a card changes only that card's `position`; no other rows are
 * renumbered. Dropping between 1 and 2 gives 1.5, and between 1 and 1.5
 * gives 1.25. A double can be halved roughly 50 times before neighbours
 * collide; a production system would re-space a column when gaps get too
 * small.
 */
export function positionBetween(before: number | undefined, after: number | undefined): number {
  if (before === undefined && after === undefined) return 1;
  if (before === undefined) return after! - 1;
  if (after === undefined) return before + 1;
  return (before + after) / 2;
}

/** Tasks grouped into board columns, each sorted by position (id breaks ties). */
export function groupByStatus(tasks: Task[]): Record<Status, Task[]> {
  const columns: Record<Status, Task[]> = { todo: [], in_progress: [], done: [] };
  for (const t of tasks) columns[t.status].push(t);
  for (const list of Object.values(columns)) list.sort((a, b) => a.position - b.position || a.id - b.id);
  return columns;
}

/**
 * Where does a dragged card land? `column` is the target column's cards in
 * order (the dragged card excluded); `index` is the slot it was dropped in.
 */
export function dropPosition(column: Task[], index: number): number {
  return positionBetween(column[index - 1]?.position, column[index]?.position);
}

/** YYYY-MM-DD for "today" in the user's local timezone. */
export function todayISO(now: Date = new Date()): string {
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

export function isOverdue(task: Pick<Task, "due_date" | "status">, today: string = todayISO()): boolean {
  return task.due_date !== null && task.status !== "done" && task.due_date < today;
}

/** "Today", "Tomorrow", "Yesterday", "3 days ago" or a short date. */
export function formatDue(due: string, today: string = todayISO()): string {
  const days = Math.round((Date.parse(due) - Date.parse(today)) / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  if (days === -1) return "Yesterday";
  if (days < 0 && days > -7) return `${-days} days ago`;
  if (days > 0 && days < 7) return `In ${days} days`;
  return new Date(due + "T00:00:00").toLocaleDateString(undefined, { day: "numeric", month: "short" });
}
