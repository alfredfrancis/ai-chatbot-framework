import { expect, test } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

// The chat in plain words: a calm message box, finished work folded to what it did, what the agent learned
// with a way back, and chats named for what they are about.

test("the message box offers one quiet model choice and no key legend", async ({ page }) => {
  await signUp(page);
  const composer = page.locator("form.composer");
  await expect(composer).not.toContainText("new line");
  // Effort reads as plain words, next to the model it belongs to.
  const effort = page.getByLabel("Effort", { exact: true });
  await expect(effort.locator("option")).toHaveText(["Quick", "Balanced", "Thorough", "Deepest"]);
  await expect(effort.locator("option:checked")).toHaveText("Balanced");
  await expect(composer).toContainText("·");
  await say(page, "hello there");
  await expect(lastAssistant(page)).toHaveText("Echo: hello there");
  await expect(page.getByLabel("Message")).toHaveAttribute("placeholder", "Ask anything. Type / to use a skill");
  await shot(page, "80-calm-composer");
});

test("finished steps fold to what they did; the files a reply made are cards", async ({ page }) => {
  await signUp(page);
  await say(page, "write: notes/report.md | # Weekly sales");
  await expect(lastAssistant(page)).toContainText("Result: Wrote notes/report.md");
  const summary = page.getByTestId("steps-summary");
  await expect(summary).toContainText(/Done in (under a second|\d+ s)/);
  await expect(summary).toContainText("wrote 1 file");
  await expect(summary).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByTestId("tool-step")).toHaveCount(0);
  const files = page.getByRole("list", { name: "Files from this reply" });
  await expect(files.getByRole("listitem")).toHaveText(/report\.mdIn Files · notes/);
  await expect(files.getByRole("link", { name: "Open report.md" })).toHaveAttribute("href", /path=notes%2Freport\.md/);
  await expect(files.getByRole("link", { name: "Download report.md" })).toBeVisible();
  await shot(page, "81-steps-folded");

  await summary.click();
  await expect(page.getByTestId("tool-step")).toContainText("Wrote notes/report.md");
  await shot(page, "82-steps-open");

  // A command's output leaves out the "[exit code 0]" the model reads; a failure says so on the fold.
  await say(page, "run: echo done-$((6*7))");
  await expect(lastAssistant(page)).toContainText("Result: done-42");
  await page.getByTestId("steps-summary").last().click();
  await page.getByTestId("tool-step").last().click();
  await expect(page.locator(".step-output").last()).toHaveText("done-42");
  await say(page, "run: exit 4");
  await expect(lastAssistant(page)).toContainText("exit code 4");
  await expect(page.getByTestId("steps-summary").last()).toContainText("1 step failed");
});

test("the context meter stays out of the way until a chat gets long", async ({ page }) => {
  await signUp(page);
  await say(page, "hello");
  await expect(lastAssistant(page)).toHaveText("Echo: hello");
  await expect(page.getByRole("button", { name: /^Context usage/ })).toHaveCount(0);
  await page.getByRole("button", { name: "Chat actions" }).click();
  await page.getByRole("menuitem", { name: "Context usage" }).click();
  await expect(page.getByRole("dialog", { name: "Context usage" })).toContainText("of 1,000,000 tokens");
});

test("what the agent learned shows in the chat and can be undone", async ({ page }) => {
  await signUp(page);
  const md = "---\\nname: greet\\ndescription: Greet people warmly. Use when greeting someone.\\n---\\n# Greet\\nSay hi by name.";
  await say(page, `learn: skills/greet/SKILL.md | ${md}`);
  await expect(lastAssistant(page)).toContainText("Echo: learn:");
  await say(page, "thanks, that is how I like it");
  const note = page.getByRole("region", { name: "Learned from this chat" });
  await expect(note).toContainText("Made a new skill: greet");
  await expect(note.getByRole("link", { name: "View" })).toHaveAttribute("href", "/files?path=skills%2Fgreet");
  await shot(page, "83-learned-note");

  await note.getByRole("button", { name: "Undo" }).click();
  await expect(note).toContainText("Undone: nothing from this chat is kept");
  await expect(note.getByRole("button", { name: "Undo" })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("region", { name: "Learned from this chat" })).toContainText("Undone");
  await nav(page).getByRole("link", { name: /^Skills( \d+)?$/ }).click();
  await expect(page.getByTestId("skill-weekly-review")).toBeVisible();
  await expect(page.getByTestId("skill-greet")).toHaveCount(0);
});

test("a new chat gets a short title after its first reply", async ({ page }) => {
  await signUp(page);
  await say(page, "please summarise the sales sheet in my files and send it to Ana");
  await expect(lastAssistant(page)).toContainText("Echo: please summarise");
  await expect(nav(page).getByRole("link", { name: "Please summarise the sales sheet", exact: true })).toBeVisible();
  await expect(page.locator(".topbar .here")).toHaveText("Please summarise the sales sheet");
  await shot(page, "84-chat-title");
});

test.describe("phone", () => {
  test.use({ viewport: { width: 390, height: 844 }, colorScheme: "light" });

  test("folded steps, file cards and the learned note fit a phone", async ({ page }) => {
    await signUp(page);
    await say(page, "write: notes/plan.md | # Plan for Friday");
    await expect(page.getByTestId("steps-summary")).toBeVisible();
    await expect(page.getByRole("list", { name: "Files from this reply" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    await shot(page, "85-steps-phone-light");
  });
});
