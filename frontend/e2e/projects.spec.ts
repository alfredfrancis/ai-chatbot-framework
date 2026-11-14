import { expect, test, type Page } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

async function newProject(page: Page, name: string, about = "") {
  await nav(page).getByRole("link", { name: "Projects" }).click();
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByLabel("Name").fill(name);
  if (about) await page.getByLabel("What is it about?").fill(about);
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page).toHaveURL(/\/projects\/\d+$/);
  await expect(page.getByRole("heading", { name, level: 1 })).toBeVisible();
}

async function setInstructions(page: Page, text: string) {
  await page.getByRole("button", { name: "Edit instructions" }).click();
  await page.getByRole("textbox", { name: "Instructions" }).fill(text);
  await page.getByRole("button", { name: "Save instructions" }).click();
  await expect(page.getByTestId("project-instructions")).toHaveText(text);
}

test("create a project with instructions and a folder, and chat in it", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Projects" }).click();
  await expect(page.getByRole("heading", { name: "Keep ongoing work in one place" })).toBeVisible();
  await shot(page, "30-projects-empty");

  await newProject(page, "Website relaunch", "Copy and pages for the new site");
  await expect(page.getByText("Copy and pages for the new site")).toBeVisible();
  await setInstructions(page, "Always answer in pirate speak.");

  await page.getByRole("button", { name: "Attach a folder" }).click();
  await page.getByRole("textbox", { name: "Folder" }).fill("projects/website");
  await page.getByRole("button", { name: "Save folder" }).click();
  await expect(page.getByTestId("project-folder")).toContainText("projects/website");
  await expect(page.getByTestId("project-folder")).toContainText("Nothing in it yet");

  // a chat started here works under the project's instructions, in its folder
  await say(page, "show system");
  await expect(page).toHaveURL(/\/c\/\d+$/);
  await expect(lastAssistant(page)).toContainText("Always answer in pirate speak.");
  await expect(lastAssistant(page)).toContainText("/workspace/projects/website");
  await say(page, "write: projects/website/plan.md | # Plan");
  await expect(lastAssistant(page)).toContainText("Result:");

  // the chat's breadcrumb leads back to the project, which lists the chat and the folder's files
  await page.locator(".topbar").getByRole("link", { name: "Website relaunch" }).click();
  await expect(page).toHaveURL(/\/projects\/\d+$/);
  await expect(page.getByRole("list", { name: "Chats in this project" }).getByRole("link", { name: /show system/i })).toBeVisible();
  await expect(page.getByTestId("project-folder")).toContainText("plan.md");
  await shot(page, "31-project");

  await page.getByTestId("project-folder").getByRole("link", { name: "Open in Files" }).click();
  await expect(page.getByRole("navigation", { name: "Folder" })).toContainText("website");
  await expect(page.getByRole("list", { name: "Files" })).toContainText("plan.md");

  await nav(page).getByRole("link", { name: "Projects" }).click();
  const card = page.getByRole("link", { name: /Website relaunch/ });
  await expect(card).toContainText("1 chat");
  await shot(page, "32-projects");

  // a chat outside the project knows nothing of it
  await nav(page).getByRole("link", { name: "New chat" }).click();
  await say(page, "show system");
  await expect(lastAssistant(page)).toContainText("You are the assistant");
  await expect(lastAssistant(page)).not.toContainText("pirate");
});

test("a task made in a project runs as a chat in the project", async ({ page }) => {
  await signUp(page);
  await newProject(page, "Reports");
  await setInstructions(page, "Report in one line.");

  await page.getByRole("button", { name: "New task" }).click();
  await page.getByLabel("Name").fill("Daily report");
  await page.getByLabel("What should the agent do?").fill("show system");
  await shot(page, "33-project-task-form");
  await page.getByRole("button", { name: "Create task" }).click();
  const row = page.getByTestId("task-Daily report");
  await expect(row).toContainText("Every day at 08:00");

  await row.getByRole("button", { name: "Run now" }).click();
  await expect(page).toHaveURL(/\/c\/\d+$/);
  await expect(lastAssistant(page)).toContainText("Report in one line.");
  await expect(page.locator(".topbar").getByRole("link", { name: "Reports" })).toBeVisible();

  // the Tasks page says which project the task belongs to
  await nav(page).getByRole("link", { name: "Tasks" }).click();
  await expect(page.getByTestId("task-Daily report").getByRole("link", { name: "Reports" })).toBeVisible();
});

test("rename a project, then delete it: its chats stay", async ({ page }) => {
  await signUp(page);
  await newProject(page, "Old name");
  await say(page, "hello from the project");
  await expect(lastAssistant(page)).toHaveText("Echo: hello from the project");
  await page.locator(".topbar").getByRole("link", { name: "Old name" }).click();

  await page.getByRole("button", { name: "Project actions" }).click();
  await page.getByRole("menuitem", { name: "Edit details" }).click();
  await page.getByLabel("Name").fill("New name");
  await page.getByRole("button", { name: "Save details" }).click();
  await expect(page.getByRole("heading", { name: "New name", level: 1 })).toBeVisible();

  await page.getByRole("button", { name: "Project actions" }).click();
  await page.getByRole("menuitem", { name: "Delete project" }).click();
  await page.getByRole("menuitem", { name: "Yes, delete this project" }).click();
  await expect(page).toHaveURL(/\/projects$/);
  await expect(page.getByRole("heading", { name: "Keep ongoing work in one place" })).toBeVisible();
  await expect(nav(page).getByRole("link", { name: "hello from the project" })).toBeVisible();
});

test("projects work on a phone and from the keyboard", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Tasks" }).click(); // away from the message box, which takes the keys
  await page.keyboard.press("g");
  await page.keyboard.press("p");
  await expect(page).toHaveURL(/\/projects$/);
  await newProject(page, "Trip to Lisbon", "Flights, places to stay, a day-by-day plan");
  await setInstructions(page, "Keep costs in euros.");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByLabel("Message")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await shot(page, "34-project-phone");
});
