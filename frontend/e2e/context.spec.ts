import { expect, test } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

test("a chat shows how full the context window is and what fills it", async ({ page }) => {
  await signUp(page);
  await say(page, "run: echo context-check");
  await expect(lastAssistant(page)).toContainText("Result: context-check");

  // While the chat is short the meter stays out of the top bar; the chat's menu opens it.
  const meter = page.getByRole("button", { name: /^Context usage/ });
  await expect(meter).toHaveCount(0);
  const openUsage = async () => {
    await page.getByRole("button", { name: "Chat actions" }).click();
    await page.getByRole("menuitem", { name: "Context usage" }).click();
  };
  await openUsage();

  const details = page.getByRole("dialog", { name: "Context usage" });
  await expect(details).toContainText(/[\d,]+ of 1,000,000 tokens/);
  const parts = details.getByRole("list", { name: "What is in the context" });
  await expect(parts.getByRole("listitem")).toHaveCount(4);
  await expect(parts.getByRole("listitem").nth(0)).toContainText("System prompt");
  const tools = parts.getByRole("listitem").filter({ hasText: "Tools" });
  await expect(tools).toContainText("bash");
  await expect(tools).toContainText("read");
  await expect(parts.getByRole("listitem").filter({ hasText: "Skills" })).toContainText("skill-creator");
  await expect(parts.getByRole("listitem").filter({ hasText: "Messages" })).toContainText("4 messages");
  await shot(page, "22-context-usage");

  // Esc closes it; the usage comes back after a reload (the latest usage is replayed)
  await page.keyboard.press("Escape");
  await expect(details).toHaveCount(0);
  await page.reload();
  await expect(lastAssistant(page)).toContainText("Result: context-check");
  await openUsage();
  await expect(details.locator(".context-total strong")).toHaveText(/^\d+(\.\d)?%$/);
  await page.keyboard.press("Escape");

  // A new chat has no usage to show until the model has answered
  await nav(page).getByRole("link", { name: "New chat" }).click();
  await expect(page.getByRole("heading", { name: /^Good (morning|afternoon|evening)/ })).toBeVisible();
  await say(page, "hello");
  await expect(lastAssistant(page)).toContainText("Echo: hello");
  await openUsage();
  await expect(details.getByRole("list", { name: "What is in the context" }).getByRole("listitem").filter({ hasText: "Messages" }))
    .toContainText("2 messages");
});

test("on a phone the context details fit the screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signUp(page);
  await say(page, "hello");
  await expect(lastAssistant(page)).toContainText("Echo: hello");
  await page.getByRole("button", { name: "Chat actions" }).click();
  await page.getByRole("menuitem", { name: "Context usage" }).click();
  const details = page.getByRole("dialog", { name: "Context usage" });
  await expect(details).toBeVisible();
  const box = await details.boundingBox();
  expect(box && box.x).toBeGreaterThanOrEqual(0);
  expect(box && box.x + box.width).toBeLessThanOrEqual(390);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await shot(page, "22-context-usage-phone");
  // A click outside closes it
  await page.getByLabel("Message").click();
  await expect(details).toHaveCount(0);
});
