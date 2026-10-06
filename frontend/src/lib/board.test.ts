// Unit tests for the board logic, using Node's built-in test runner (no extra deps):
//   npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { dropPosition, formatDue, groupByStatus, isOverdue, positionBetween } from "./board.ts";
import type { Task } from "../api/types.ts";

const task = (id: number, status: Task["status"], position: number): Task => ({
  id, status, position, title: `t${id}`, description: "", priority: "medium",
  due_date: null, created_at: "", updated_at: "",
});

test("positionBetween covers empty column, top, bottom and middle", () => {
  assert.equal(positionBetween(undefined, undefined), 1);
  assert.equal(positionBetween(undefined, 1), 0);
  assert.equal(positionBetween(3, undefined), 4);
  assert.equal(positionBetween(1, 2), 1.5);
});

test("repeated inserts at the same spot keep a strict order", () => {
  let lo = 1;
  const hi = 2;
  for (let i = 0; i < 40; i++) {
    const mid = positionBetween(lo, hi);
    assert.ok(lo < mid && mid < hi);
    lo = mid;
  }
});

test("groupByStatus sorts each column by position then id", () => {
  const cols = groupByStatus([task(1, "todo", 2), task(2, "done", 1), task(3, "todo", 1), task(4, "todo", 2)]);
  assert.deepEqual(cols.todo.map((t) => t.id), [3, 1, 4]);
  assert.deepEqual(cols.done.map((t) => t.id), [2]);
  assert.deepEqual(cols.in_progress, []);
});

test("dropPosition for every slot", () => {
  const col = [task(1, "todo", 1), task(2, "todo", 2)];
  assert.equal(dropPosition(col, 0), 0);
  assert.equal(dropPosition(col, 1), 1.5);
  assert.equal(dropPosition(col, 2), 3);
  assert.equal(dropPosition([], 0), 1);
});

test("isOverdue ignores finished and undated tasks", () => {
  assert.equal(isOverdue({ due_date: "2026-01-01", status: "todo" }, "2026-01-02"), true);
  assert.equal(isOverdue({ due_date: "2026-01-01", status: "done" }, "2026-01-02"), false);
  assert.equal(isOverdue({ due_date: "2026-01-02", status: "todo" }, "2026-01-02"), false);
  assert.equal(isOverdue({ due_date: null, status: "todo" }, "2026-01-02"), false);
});

test("formatDue uses friendly relative labels", () => {
  assert.equal(formatDue("2026-03-10", "2026-03-10"), "Today");
  assert.equal(formatDue("2026-03-11", "2026-03-10"), "Tomorrow");
  assert.equal(formatDue("2026-03-09", "2026-03-10"), "Yesterday");
  assert.equal(formatDue("2026-03-07", "2026-03-10"), "3 days ago");
  assert.equal(formatDue("2026-03-13", "2026-03-10"), "In 3 days");
});
