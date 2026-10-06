import { expect, test, type Page } from "@playwright/test";

const uniqueEmail = () => `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;

async function register(page: Page, name: string, email: string, password = "e2e-password-123") {
  await page.goto("/");
  await page.getByRole("button", { name: "Create an account" }).click();
  await page.getByLabel("Name").fill(name);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("button", { name: "+ New task" })).toBeVisible();
}

async function createTask(page: Page, title: string, opts: { priority?: string; due?: string } = {}) {
  await page.getByRole("button", { name: "+ New task" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Title").fill(title);
  if (opts.priority) await dialog.getByLabel("Priority").selectOption(opts.priority);
  if (opts.due) await dialog.getByLabel("Due date").fill(opts.due);
  await dialog.getByRole("button", { name: "Create task" }).click();
  await expect(dialog).toBeHidden();
}

const column = (page: Page, name: string) => page.getByRole("region", { name, exact: true });

test("full journey: register, create, drag, search, edit, delete, persist", async ({ page }) => {
  const email = uniqueEmail();
  await register(page, "Aman Jha", email);
  await expect(page.getByText("Hi, Aman")).toBeVisible();

  await createTask(page, "Fix login bug", { priority: "high", due: "2020-01-01" });
  await createTask(page, "Write README");

  const todo = column(page, "To do");
  await expect(todo.locator(".card")).toHaveCount(2);
  await expect(todo.getByText("Fix login bug")).toBeVisible();
  await expect(todo.locator(".due-overdue")).toHaveCount(1); // 2020 due date is overdue
  await expect(page.locator(".stat-bad .stat-value")).toHaveText("1");

  // Drag "Write README" into Done
  await todo.getByText("Write README").dragTo(column(page, "Done").locator(".cards"));
  await expect(column(page, "Done").getByText("Write README")).toBeVisible();
  await expect(todo.locator(".card")).toHaveCount(1);

  // The move was saved to the server: it survives a reload
  await page.reload();
  await expect(column(page, "Done").getByText("Write README")).toBeVisible();
  await expect(page.getByText("50%")).toBeVisible(); // completion rate

  // Search narrows the board
  await page.getByLabel("Search tasks").fill("login");
  await expect(page.locator(".card")).toHaveCount(1);
  await page.getByLabel("Search tasks").fill("");
  await expect(page.locator(".card")).toHaveCount(2);

  // Edit through the modal
  await page.getByText("Fix login bug").click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Title").fill("Fix login bug (JWT expiry)");
  await dialog.getByLabel("Status").selectOption("in_progress");
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(column(page, "In progress").getByText("Fix login bug (JWT expiry)")).toBeVisible();

  // Delete
  await page.getByText("Write README").click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete" }).click();
  await expect(page.getByText("Write README")).toHaveCount(0);

  // Log out and back in: data is still there
  await page.getByRole("button", { name: "Log out" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("e2e-password-123");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByText("Fix login bug (JWT expiry)")).toBeVisible();
});

test("each user sees only their own board", async ({ page, browser }) => {
  await register(page, "Alice", uniqueEmail());
  await createTask(page, "Alice's private task");

  const other = await browser.newPage();
  await register(other, "Bob", uniqueEmail());
  await expect(other.locator(".card")).toHaveCount(0);
  await expect(other.getByText("Alice's private task")).toHaveCount(0);
  await other.close();
});

test("helpful errors on bad login and duplicate signup", async ({ page }) => {
  const email = uniqueEmail();
  await register(page, "Dup", email);
  await page.getByRole("button", { name: "Log out" }).click();

  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("alert")).toHaveText("Invalid email or password.");

  await page.getByRole("button", { name: "Create an account" }).click();
  await page.getByLabel("Name").fill("Dup again");
  await page.getByLabel("Email").fill(email.toUpperCase());
  await page.getByLabel("Password").fill("another-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByText("Already registered.")).toBeVisible();
});

test("reorder within a column by dragging, and the order persists", async ({ page }) => {
  await register(page, "Reorder", uniqueEmail());
  for (const t of ["First", "Second", "Third"]) await createTask(page, t);
  const todo = column(page, "To do");
  const titles = () => todo.locator(".card-title").allInnerTexts();
  expect(await titles()).toEqual(["First", "Second", "Third"]);

  // Drop "Third" onto the top half of "First" -> it becomes the first card
  await todo.getByText("Third").dragTo(todo.getByText("First"), { targetPosition: { x: 10, y: 2 } });
  await expect.poll(titles).toEqual(["Third", "First", "Second"]);

  await page.reload();
  await expect.poll(titles).toEqual(["Third", "First", "Second"]);
});
