import { expect, type Page, test } from "@playwright/test";
import { lastAssistant, say, shot, signUp } from "./helpers";

/** Have the scripted model write files with the `write` tool, one call per file, in one reply. */
async function write(page: Page, files: Record<string, string>) {
  await say(page, Object.entries(files).map(([path, content]) => `tool: write ${JSON.stringify({ path, content })}`).join("\n"));
  await expect(lastAssistant(page)).toContainText(`Result: Wrote ${Object.keys(files).at(-1)}`);
}

const REPORT = [
  "# Weekly sales",
  "",
  "Sales rose **12%** on last week.",
  "",
  "| Day | EUR |",
  "| --- | --- |",
  "| Mon | 120 |",
  "",
  "See [the notes](notes.md), [the data](data.csv) and [the project site](https://example.com/q3).",
  "",
  "![Sales chart](chart.svg)",
  "",
  "<script>window.pwned = true</script>",
].join("\n");
const CHART = '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40"><rect width="80" height="40" fill="#4a946a"/></svg>';

test("a document the agent writes opens beside the chat, rendered, and follows the agent's edits", async ({ page, context }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await signUp(page);
  await write(page, { "reports/notes.md": "# Notes\n\nCall the supplier.", "reports/data.csv": "day,eur\nmon,120\n", "reports/chart.svg": CHART });
  await write(page, { "reports/q3.md": REPORT });

  // The reply offers the document; other files keep their plain card
  const card = page.getByRole("list", { name: "Files from this reply" }).last().getByRole("listitem");
  await expect(card).toContainText("q3.md");
  await expect(card).toContainText("Document · In Files · reports");
  const preview = card.getByRole("button", { name: "Preview q3.md" });
  await preview.click();

  const panel = page.getByRole("complementary", { name: "Document: q3.md" });
  await expect(page).toHaveURL(/[?&]doc=reports%2Fq3\.md/);
  await expect(panel.getByRole("heading", { name: "q3.md" })).toBeFocused();
  await expect(panel.getByRole("heading", { level: 1, name: "Weekly sales" })).toBeVisible();
  await expect(panel.locator("strong")).toHaveText("12%");
  await expect(panel.getByRole("cell", { name: "120" })).toBeVisible();
  await expect(panel).toContainText("reports");
  // Images inside the document load from Files; raw HTML is never run
  const img = panel.getByRole("img", { name: "Sales chart" });
  await expect(img).toHaveAttribute("src", /path=reports%2Fchart\.svg/);
  await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBeGreaterThan(0);
  expect(await page.evaluate(() => (window as unknown as { pwned?: boolean }).pwned)).toBeUndefined();
  await expect(panel).not.toContainText("pwned");
  // Wide windows keep the chat beside the document
  const msg = await page.getByLabel("Message").boundingBox();
  const side = await panel.boundingBox();
  expect(msg && side && msg.x + msg.width).toBeLessThanOrEqual(side!.x);
  await shot(page, "90-document-panel");

  // Links: another document opens in the panel, other files and web pages in a new tab
  await expect(panel.getByRole("link", { name: "the data" })).toHaveAttribute("href", /path=reports%2Fdata\.csv/);
  await expect(panel.getByRole("link", { name: "the data" })).toHaveAttribute("target", "_blank");
  await expect(panel.getByRole("link", { name: "the project site" })).toHaveAttribute("href", "https://example.com/q3");
  await expect(panel.getByRole("link", { name: "the project site" })).toHaveAttribute("target", "_blank");
  await panel.getByRole("link", { name: "the notes" }).click();
  const notes = page.getByRole("complementary", { name: "Document: notes.md" });
  await expect(notes.getByRole("heading", { level: 1, name: "Notes" })).toBeVisible();
  await page.goBack();
  await expect(panel.getByRole("heading", { level: 1, name: "Weekly sales" })).toBeVisible();

  // Copy and download
  await expect(panel.getByRole("link", { name: "Download q3.md" })).toHaveAttribute("href", /path=reports%2Fq3\.md&download=true/);
  await panel.getByRole("button", { name: "Copy text" }).click();
  await expect(panel.getByRole("button", { name: "Copied" })).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(REPORT);

  // The agent edits the open document: the panel shows the change
  await say(page, "edit: reports/q3.md | rose | climbed");
  await expect(panel).toContainText("Sales climbed 12% on last week.");

  // Esc closes it and gives focus back to what opened it
  await page.getByRole("list", { name: "Files from this reply" }).nth(1).getByRole("button", { name: "Preview q3.md" }).click();
  await expect(panel.getByRole("heading", { name: "q3.md" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(panel).toHaveCount(0);
  await expect(page).not.toHaveURL(/doc=/);
  await expect(page.getByRole("list", { name: "Files from this reply" }).nth(1).getByRole("button", { name: "Preview q3.md" })).toBeFocused();

  // From the artifacts list too, with a way back to the list
  await page.getByRole("button", { name: "Artifacts", exact: true }).click();
  const list = page.getByRole("complementary", { name: "Artifacts" });
  await list.getByRole("list", { name: "Produced files" }).getByRole("link", { name: /^q3\.md/ }).click();
  await expect(panel.getByRole("heading", { level: 1, name: "Weekly sales" })).toBeVisible();
  await panel.getByRole("button", { name: "Back to artifacts" }).click();
  await expect(list.getByRole("list", { name: "Produced files" })).toBeVisible();
  await list.getByRole("link", { name: /^notes\.md/ }).click();
  await expect(notes).toBeVisible();

  // A reload keeps it open; light theme
  await page.reload();
  await expect(notes.getByRole("heading", { level: 1, name: "Notes" })).toBeVisible();
  await page.goto(page.url().replace(/doc=[^&]+/, "doc=reports%2Fq3.md"));
  await expect(panel.getByRole("heading", { level: 1, name: "Weekly sales" })).toBeVisible();
  await page.emulateMedia({ colorScheme: "light" });
  await shot(page, "91-document-panel-light");
  await panel.getByRole("button", { name: "Close document" }).click();
  await expect(panel).toHaveCount(0);
  await expect(list).toHaveCount(0);
});

test("a document overlays the chat in narrower windows and fills a phone; missing and empty files say so", async ({ page }) => {
  await signUp(page); // 1280 wide
  await write(page, { "plan.md": "# Plan\n\n- Call the bank\n- Send the invoice", "empty.md": "" });
  await page.getByRole("button", { name: "Preview plan.md" }).click();
  const panel = page.getByRole("complementary", { name: "Document: plan.md" });
  await expect(panel.getByRole("listitem")).toHaveText(["Call the bank", "Send the invoice"]);
  const box = await panel.boundingBox();
  expect(box && Math.round(box.x + box.width)).toBe(1280);
  await expect(page.locator(".doc-scrim")).toBeVisible();
  await page.locator(".doc-scrim").click({ position: { x: 20, y: 400 } });
  await expect(panel).toHaveCount(0);

  await page.getByRole("button", { name: "Preview empty.md" }).click();
  await expect(page.getByRole("complementary", { name: "Document: empty.md" })).toContainText("This document is empty.");
  await page.goto(page.url().replace(/doc=[^&]+/, "doc=gone.md"));
  const gone = page.getByRole("complementary", { name: "Document: gone.md" });
  await expect(gone).toContainText("This file is no longer in Files.");
  await gone.getByRole("button", { name: "Close document" }).click();
  await expect(gone).toHaveCount(0);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Preview plan.md" }).click();
  await expect(panel.getByRole("heading", { level: 1, name: "Plan" })).toBeVisible();
  const phone = await panel.boundingBox();
  expect(phone && Math.round(phone.x)).toBe(0);
  expect(phone && Math.round(phone.width)).toBe(390);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await shot(page, "92-document-phone");
  await panel.getByRole("button", { name: "Close document" }).click();
  await expect(panel).toHaveCount(0);
});
