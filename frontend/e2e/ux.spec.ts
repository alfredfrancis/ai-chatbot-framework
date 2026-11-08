import { expect, test, type Page } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

const SKILL = `---
name: weekly-update
description: How I write my weekly update. Use when asked for a weekly update.
---
Three wins, one risk, next week's focus.
`;

/** Drop a file on an element the way a browser does: dragover, then drop, with the file in a DataTransfer. */
async function dropFile(page: Page, testId: string, name: string, text: string) {
  const data = await page.evaluateHandle(([n, t]) => {
    const dt = new DataTransfer();
    dt.items.add(new File([t], n, { type: "text/markdown" }));
    return dt;
  }, [name, text]);
  const target = page.getByTestId(testId);
  await target.dispatchEvent("dragover", { dataTransfer: data });
  await expect(target).toHaveClass(/dropping/);
  await target.dispatchEvent("drop", { dataTransfer: data });
}

test("every page has at most one filled button, and the sidebar hides zero counts", async ({ page }) => {
  await signUp(page);
  // Zero counts read like errors: Tasks and Connections show none, Files and Skills show theirs.
  await expect(nav(page).getByRole("link", { name: "Tasks" })).toHaveText("Tasks");
  await expect(nav(page).getByRole("link", { name: "Connections" })).toHaveText("Connections");
  await expect(nav(page).getByRole("link", { name: /^Skills/ })).toHaveText("Skills10");
  // New chat is a plain button with its shortcut; sign out lives in Settings.
  await expect(nav(page).getByRole("link", { name: "New chat" })).toContainText("C");
  await expect(nav(page).getByRole("button", { name: "Sign out" })).toHaveCount(0);

  for (const path of ["/", "/files", "/skills", "/tasks", "/connections", "/settings"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await page.locator(".btn.primary:visible").count(), path).toBeLessThanOrEqual(1);
  }
});

test("an empty Tasks page explains itself and a template fills in the form", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Tasks" }).click();
  await expect(page.getByRole("heading", { name: "Put your agent on a schedule" })).toBeVisible();
  const templates = page.getByRole("region", { name: "Start from a template" });
  await expect(templates.getByRole("button")).toHaveCount(3);
  await shot(page, "60-tasks-empty");

  await templates.getByRole("button", { name: "Use template: Weekly review" }).click();
  const form = page.getByRole("form", { name: "New task" });
  await expect(form.getByLabel("Name")).toHaveValue("Weekly review");
  await expect(form.getByLabel("What should the agent do?")).toHaveValue(/what got done/);
  await expect(form.getByLabel("Repeat")).toHaveValue("weekly");
  await expect(form.getByLabel("On", { exact: true })).toHaveValue("5");
  await expect(form.getByLabel("At", { exact: true })).toHaveValue("16:00");
  await form.getByRole("button", { name: "Create task" }).click();
  await expect(page.getByTestId("task-Weekly review")).toContainText("Every Friday at 16:00");
  // With a task, the action moves to the page header and the sidebar shows the count.
  await expect(page.getByRole("button", { name: "New task" })).toBeVisible();
  await expect(nav(page).getByRole("link", { name: /^Tasks/ })).toHaveText("Tasks1");
});

test("skills: yours apart from the built-in ones, drop anywhere, actions in a menu", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Skills" }).click();
  const mine = page.getByRole("region", { name: /Yours/ });
  const builtin = page.getByRole("region", { name: /Built in/ });
  await expect(mine).toContainText("Skills you upload, or ask the agent to write, show up here.");
  await expect(builtin.getByRole("heading")).toHaveText("Built in · 10");
  // Readable names; the id stays as the tooltip.
  await expect(builtin.getByTestId("skill-pdf").locator(".title")).toHaveText("PDF");
  await expect(builtin.getByTestId("skill-action-items").locator(".title")).toHaveText("Action items");

  await dropFile(page, "skills-page", "SKILL.md", SKILL);
  await expect(page.getByRole("status")).toHaveText("Added “weekly-update”.");
  await expect(mine.getByTestId("skill-weekly-update")).toContainText("Weekly update");
  await expect(mine.getByRole("heading")).toHaveText("Yours · 1");
  await shot(page, "61-skills");

  // The menu works from the keyboard and closes with Escape without doing anything.
  await mine.getByRole("button", { name: "More actions for weekly-update" }).click();
  await expect(page.getByRole("menuitem", { name: "Remove skill" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu")).toHaveCount(0);
  await expect(mine.getByTestId("skill-weekly-update")).toBeVisible();
});

test("settings: sections, cancel, and signing out from Account", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Settings" }).click();
  const sections = page.getByRole("navigation", { name: "Settings sections" });
  await expect(sections.getByRole("link", { name: "Model" })).toHaveAttribute("aria-current", "true");

  // Cancel puts back what is saved.
  const model = page.getByLabel("Model", { exact: true });
  await model.fill("something-else");
  await expect(page.getByTestId("model-in-use")).toContainText("something-else");
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(model).toHaveValue("");
  await expect(page.getByRole("button", { name: "Cancel" })).toBeDisabled();

  await sections.getByRole("link", { name: "Account" }).click();
  await expect(sections.getByRole("link", { name: "Account" })).toHaveAttribute("aria-current", "true");
  const account = page.getByRole("region", { name: "Account" });
  await expect(account).toContainText("Maya");
  await shot(page, "62-settings-account");
  await account.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
});

test("files: the agent's own files explain themselves, and one click asks for a change", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Files" }).click();
  const list = page.getByRole("list", { name: "Files" });
  await expect(list.getByRole("button", { name: /context\.md/ })).toContainText("What your agent knows about you");
  await expect(list.getByRole("button", { name: /^skills/ })).toContainText("10 items");
  await list.getByRole("button", { name: /context\.md/ }).click();
  await shot(page, "63-files");
  await page.getByRole("button", { name: "Ask the agent to edit this" }).click();
  await expect(page.getByLabel("Message")).toHaveValue("Change context.md: ");
});

test.describe("phone", () => {
  test.use({ viewport: { width: 390, height: 844 }, colorScheme: "dark" });

  test("chat actions open as a bottom sheet with the title given room", async ({ page }) => {
    await signUp(page);
    await say(page, "Plan my week of meetings");
    await expect(lastAssistant(page)).toContainText("Echo:");
    // On a phone the breadcrumb and the artifacts button give way to the title; artifacts move into the sheet.
    await expect(page.locator(".topbar .crumb").first()).toBeHidden();
    await expect(page.getByRole("button", { name: "Artifacts", exact: true })).toBeHidden();

    await page.getByRole("button", { name: "Chat actions" }).click();
    const sheet = page.getByRole("menu", { name: "Chat actions" });
    const box = (await sheet.boundingBox())!;
    expect(Math.round(box.y + box.height)).toBe(844);
    expect(Math.round(box.width)).toBe(390);
    for (const item of await sheet.getByRole("menuitem").all()) expect((await item.boundingBox())!.height).toBe(48);
    await shot(page, "64-phone-chat-actions");

    await sheet.getByRole("menuitem", { name: "Show artifacts" }).click();
    await expect(page.getByRole("complementary", { name: "Artifacts" })).toBeVisible();
  });

  test("compact buttons grow to 40px", async ({ page }) => {
    await signUp(page);
    await page.getByRole("button", { name: "Open menu" }).click();
    await nav(page).getByRole("link", { name: "Connections" }).click();
    await page.getByRole("button", { name: "Edit as JSON" }).click();
    expect((await page.getByRole("button", { name: "Insert example" }).boundingBox())!.height).toBe(40);
  });
});
