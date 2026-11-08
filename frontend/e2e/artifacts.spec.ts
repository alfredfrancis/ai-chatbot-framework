import { expect, test } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

test("a chat's artifacts panel lists the files attached to it and the files the agent made", async ({ page }) => {
  await signUp(page);
  await page.getByTestId("chat-upload").setInputFiles({ name: "sales.csv", mimeType: "text/csv", buffer: Buffer.from("day,eur\nmon,120\n") });
  await expect(page.getByRole("list", { name: "Files to send" })).toContainText("sales.csv");
  await say(page, "Summarise this");
  await expect(lastAssistant(page)).toContainText("Echo: Summarise this");

  // Closed by default; the toggle counts the chat's files
  const toggle = page.getByRole("button", { name: "Artifacts", exact: true });
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(toggle).toContainText("1");
  await toggle.click();
  const panel = page.getByRole("complementary", { name: "Artifacts" });
  await expect(panel.getByRole("list", { name: "Uploaded files" }).getByRole("link", { name: /^sales\.csv/ }))
    .toHaveAttribute("href", /path=uploads%2Fsales\.csv/);
  await expect(panel.getByRole("list", { name: "Produced files" })).toHaveCount(0);

  // Files the agent writes, and files its commands make, show up while the panel is open
  await say(page, "write: report.md | # Weekly sales");
  await expect(lastAssistant(page)).toContainText("Result: Wrote report.md");
  await say(page, "run: mkdir -p out && echo 'mon 120' > out/chart.txt");
  await expect(page.getByTestId("tool-step").last()).toContainText("Ran mkdir");
  const produced = panel.getByRole("list", { name: "Produced files" });
  await expect(produced.getByRole("listitem")).toHaveText([/report\.md/, /chart\.txt\s*out ·/]);
  await expect(produced.getByRole("link", { name: "Download report.md" })).toHaveAttribute("href", /path=report\.md&download=true/);
  await expect(toggle).toContainText("3");
  await shot(page, "20-artifacts-panel");

  // The file opens from the panel
  const [popup] = await Promise.all([page.waitForEvent("popup"), produced.getByRole("link", { name: /^report\.md/ }).click()]);
  await expect(popup.locator("body")).toContainText("# Weekly sales");
  await popup.close();

  // The panel stays open after a reload; another chat has its own artifacts
  await page.reload();
  await expect(panel.getByRole("list", { name: "Produced files" }).getByRole("listitem")).toHaveCount(2);
  await nav(page).getByRole("link", { name: "New chat" }).click();
  await expect(page.getByRole("heading", { name: /^Good (morning|afternoon|evening), Maya\.$/ })).toBeVisible();
  await say(page, "hello");
  await expect(lastAssistant(page)).toContainText("Echo: hello");
  await expect(panel).toContainText("Files you attach and files the agent makes in this chat show up here.");
  await page.getByRole("button", { name: "Close artifacts" }).click();
  await expect(panel).toHaveCount(0);
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
});

test("on a phone the artifacts panel opens over the chat", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signUp(page);
  await say(page, "write: notes.md | hi");
  await expect(lastAssistant(page)).toContainText("Result: Wrote notes.md");
  // On a phone the artifacts button lives in the chat actions sheet.
  await page.getByRole("button", { name: "Chat actions" }).click();
  await page.getByRole("menuitem", { name: "Show artifacts" }).click();
  const panel = page.getByRole("complementary", { name: "Artifacts" });
  await expect(panel.getByRole("link", { name: /^notes\.md/ })).toBeVisible();
  const box = await panel.boundingBox();
  expect(box && box.x + box.width).toBeLessThanOrEqual(390);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await shot(page, "21-artifacts-phone");
  await page.getByRole("button", { name: "Close artifacts" }).click();
  await expect(panel).toHaveCount(0);
});
