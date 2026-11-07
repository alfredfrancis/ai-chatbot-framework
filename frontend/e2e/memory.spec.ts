import { expect, test } from "@playwright/test";
import { lastAssistant, say, signUp } from "./helpers";

test("context.md and memory.md steer the agent", async ({ page }) => {
  await signUp(page);
  await page.getByRole("link", { name: "Memory" }).click();
  await expect(page.getByRole("heading", { name: "Memory" })).toBeVisible();
  const editor = page.getByLabel(/context\.md/);
  await editor.fill("# About me\nI run a small bakery in Porto.");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Saved" })).toBeVisible();

  await page.getByRole("link", { name: "Chats" }).click();
  await say(page, "remember: my favourite bread is broa");
  await expect(page.getByTestId("tool-chip")).toContainText("Remembered my favourite bread is broa");
  await say(page, "show system");
  await expect(lastAssistant(page)).toContainText("I run a small bakery in Porto.");
  await expect(lastAssistant(page)).toContainText("my favourite bread is broa");

  await page.getByRole("link", { name: "Memory" }).click();
  await page.getByRole("tab", { name: "What Harbor remembers" }).click();
  await expect(page.getByLabel(/memory\.md/)).toHaveValue(/- my favourite bread is broa/);
});

test("upload a file and let the agent read it", async ({ page }) => {
  await signUp(page);
  await page.getByRole("link", { name: "Memory" }).click();
  await page.getByTestId("upload").setInputFiles({ name: "sales.csv", mimeType: "text/csv", buffer: Buffer.from("day,eur\nmon,120\n") });
  await expect(page.getByText("sales.csv")).toBeVisible();
  await page.getByRole("link", { name: "Chats" }).click();
  await say(page, "read: sales.csv");
  await expect(lastAssistant(page)).toContainText("mon,120");
});
