import { expect, test } from "@playwright/test";
import { nav, say, shot, signUp } from "./helpers";

test("command menu and keyboard shortcuts", async ({ page }) => {
  await signUp(page);
  await say(page, "hello shortcuts");
  await expect(page).toHaveURL(/\/c\/\d+$/);
  await page.locator("body").click({ position: { x: 600, y: 300 } }); // leave the composer

  // ⌘K / Ctrl+K opens the menu; typing filters; arrows + Enter run
  await page.keyboard.press("ControlOrMeta+k");
  const menu = page.getByRole("dialog", { name: "Command menu" });
  await expect(menu).toBeVisible();
  await expect(menu.getByRole("option", { name: /hello shortcuts/ })).toBeVisible();
  await page.getByLabel("Search commands").fill("ski");
  await expect(menu.getByRole("option")).toHaveText([/Upload a skill/, /Skills/]);
  await shot(page, "15-command-menu");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/skills$/);
  await expect(menu).toHaveCount(0);

  // G then F goes to Files, C starts a new chat, Esc closes the menu
  await page.keyboard.press("g");
  await page.keyboard.press("f");
  await expect(page).toHaveURL(/\/files$/);
  await page.keyboard.press("c");
  await expect(page).toHaveURL(/\/$/);
  await nav(page).getByRole("button", { name: /Search or run a command/ }).click();
  await expect(menu).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(menu).toHaveCount(0);

  // "New task" from the menu opens the task form
  await page.keyboard.press("ControlOrMeta+k");
  await page.getByLabel("Search commands").fill("new task");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("form", { name: "New task" })).toBeVisible();
});
