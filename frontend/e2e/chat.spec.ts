import { expect, test } from "@playwright/test";
import { lastAssistant, say, signUp } from "./helpers";

test("chat with the agent, run a command in the sandbox, and keep history", async ({ page }) => {
  await signUp(page);
  await say(page, "hello harbor");
  await expect(page.getByTestId("user-msg")).toHaveText("hello harbor");
  await expect(lastAssistant(page)).toHaveText("Echo: hello harbor");
  await expect(page).toHaveURL(/\/c\/\d+$/);
  await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "hello harbor" })).toBeVisible();

  await say(page, "run: echo computed-$((6*7))");
  const chip = page.getByTestId("tool-chip").last();
  await expect(chip).toContainText("Ran echo computed-$((6*7))");
  await expect(lastAssistant(page)).toHaveText(/Result: computed-42/);
  await chip.click();
  await expect(page.locator(".chip-output").last()).toContainText("[exit code 0]");

  // history survives a reload
  await page.reload();
  await expect(page.getByTestId("user-msg")).toHaveCount(2);
  await expect(lastAssistant(page)).toHaveText(/Result: computed-42/);

  // delete the chat
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Delete chat" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("link", { name: "hello harbor" })).toHaveCount(0);
});

test("failed commands are shown as failed", async ({ page }) => {
  await signUp(page);
  await say(page, "run: exit 7");
  await expect(page.getByTestId("tool-chip")).toContainText("Ran exit 7");
  await expect(lastAssistant(page)).toContainText("exit code 7");
  await expect(page.getByTestId("tool-chip").locator("svg")).toBeVisible();
});
