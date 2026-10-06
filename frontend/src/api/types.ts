export type Status = "todo" | "in_progress" | "done";
export type Priority = "low" | "medium" | "high";

export const STATUSES: Status[] = ["todo", "in_progress", "done"];
export const STATUS_LABELS: Record<Status, string> = {
  todo: "To do",
  in_progress: "In progress",
  done: "Done",
};
export const PRIORITIES: Priority[] = ["high", "medium", "low"];

export interface User {
  id: number;
  email: string;
  name: string;
  created_at: string;
}

export interface Task {
  id: number;
  title: string;
  description: string;
  status: Status;
  priority: Priority;
  due_date: string | null; // YYYY-MM-DD
  position: number;
  created_at: string;
  updated_at: string;
}

export type TaskInput = Partial<Pick<Task, "title" | "description" | "status" | "priority" | "due_date" | "position">>;

export interface TaskPage {
  tasks: Task[];
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export interface Stats {
  total: number;
  by_status: Record<Status, number>;
  high_priority_open: number;
  overdue: number;
  due_this_week: number;
  completion_rate: number;
}

export interface AuthResponse {
  token: string;
  user: User;
}
