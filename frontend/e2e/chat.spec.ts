import { expect, test } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

test("home, chat, sandbox commands and history", async ({ page }) => {
  await signUp(page);
  // What the agent has, as links to where each part lives; no "0 connections".
  const has = page.getByRole("navigation", { name: "What your agent has" });
  await expect(has).toHaveText(/Private computer.*3 files.*11 skills.*Connect an app/);
  await expect(has.getByRole("link", { name: "Connect an app" })).toHaveAttribute("href", "/connections");
  await shot(page, "02-home");

  await say(page, "hello there");
  await expect(page.getByTestId("user-msg")).toHaveText("hello there");
  await expect(lastAssistant(page)).toHaveText("Echo: hello there");
  await expect(page).toHaveURL(/\/c\/\d+$/);
  await expect(nav(page).getByRole("link", { name: "hello there" })).toBeVisible();

  await say(page, "run: echo computed-$((6*7))");
  const step = page.getByTestId("tool-step").last();
  await expect(step).toContainText("Ran echo computed-$((6*7))");
  await expect(step).toContainText(/\d\.\ds/);
  await expect(lastAssistant(page)).toHaveText(/Result: computed-42/);
  await step.click();
  await expect(page.locator(".step-output").last()).toContainText("[exit code 0]");
  await shot(page, "03-chat-with-activity");

  await page.reload();
  await expect(page.getByTestId("user-msg")).toHaveCount(2);
  await expect(lastAssistant(page)).toHaveText(/Result: computed-42/);

  await page.getByRole("button", { name: "Chat actions" }).click();
  await page.getByRole("menuitem", { name: "Delete chat" }).click();
  await page.getByRole("menuitem", { name: "Yes, delete this chat" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(nav(page).getByRole("link", { name: "hello there" })).toHaveCount(0);
});

test("failed commands are marked as failed", async ({ page }) => {
  await signUp(page);
  await say(page, "run: exit 7");
  await expect(page.getByTestId("tool-step")).toContainText("Ran exit 7");
  await expect(page.getByTestId("tool-step").locator(".fail")).toBeVisible();
  await expect(lastAssistant(page)).toContainText("exit code 7");
});

test("a follow-up while the model thinks is picked up right away", async ({ page }) => {
  await signUp(page);
  await say(page, "slow: 60 first thought");
  await expect(page.getByLabel("Working").first()).toBeVisible();
  await say(page, "show messages");
  await expect(lastAssistant(page)).toHaveText("Messages: slow: 60 first thought | show messages", { timeout: 15_000 });
  await expect(page.getByTestId("user-msg")).toHaveCount(2);
  await expect(page.getByRole("button", { name: "Send" })).toBeVisible();
  await shot(page, "04b-steering-while-thinking");
});

test("steer the agent while it works, then stop it", async ({ page }) => {
  await signUp(page);
  await say(page, "run: sleep 3; echo slow-done");
  await expect(page.getByTestId("tool-step")).toContainText("Ran sleep 3; echo slow-done");
  await expect(page.getByRole("button", { name: "Stop" })).toBeVisible();

  await say(page, "show messages");
  await expect(page.getByTestId("queued-msg")).toHaveText("show messages");
  await expect(page.getByText("Queued · read as soon as the current step ends")).toBeVisible();
  await shot(page, "04-steering-queued");
  await expect(lastAssistant(page)).toHaveText("Messages: run: sleep 3; echo slow-done | show messages", { timeout: 20_000 });
  await expect(page.getByTestId("queued-msg")).toHaveCount(0);

  await say(page, "run: sleep 30");
  await expect(page.getByTestId("tool-step").last()).toContainText("Ran sleep 30");
  await page.getByRole("button", { name: "Stop" }).click();
  await expect(page.getByText("Stopped.")).toBeVisible();
  await expect(page.getByTestId("tool-step").last().locator(".fail")).toBeVisible();
  await expect(page.getByRole("button", { name: "Send" })).toBeVisible();
  await shot(page, "05-stopped");
});

test("replies appear word by word, and stopping keeps what was shown", async ({ page }) => {
  await signUp(page);
  await say(page, "typing: one two three four five six seven eight nine ten");
  await expect(lastAssistant(page)).toContainText("Echo: one two");
  await expect(lastAssistant(page)).not.toContainText("ten");
  await shot(page, "05b-streaming-reply");
  await expect(lastAssistant(page)).toHaveText("Echo: one two three four five six seven eight nine ten");

  await say(page, "typing: alpha beta gamma delta epsilon zeta eta theta iota kappa");
  await expect(lastAssistant(page)).toContainText("alpha beta");
  await page.getByRole("button", { name: "Stop" }).click();
  await expect(page.getByText("Stopped.")).toBeVisible();
  const shown = (await lastAssistant(page).textContent())!;
  expect(shown).not.toContain("kappa");
  await page.reload();
  await expect(lastAssistant(page)).toHaveText(shown);
});
