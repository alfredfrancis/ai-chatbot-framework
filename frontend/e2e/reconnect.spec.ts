import { expect, test, type Page } from "@playwright/test";
import { APPS, lastAssistant, say, shot, signUp, startApp, stopApp } from "./helpers";

// Every app process comes back up even when a test fails halfway, so the specs after this one still run.
test.afterEach(async () => { await Promise.all(APPS.map((n) => startApp(n))); });

/** Marks the page; a reload would lose the mark. */
const mark = (page: Page) => page.evaluate(() => { (window as unknown as { kept?: boolean }).kept = true; });
const marked = (page: Page) => page.evaluate(() => (window as unknown as { kept?: boolean }).kept === true);
const announced = (page: Page, text: string) => page.getByRole("status").filter({ hasText: text });

test("chat survives a 15 s restart", async ({ page }) => {
  test.setTimeout(150_000);
  await signUp(page, "Rae");
  await say(page, "hello there");
  await expect(lastAssistant(page)).toHaveText("Echo: hello there");
  const url = page.url();
  await mark(page);

  // A reply is on its way when the server goes: a deploy lets it finish, and the chat shows it once back.
  await say(page, "slow: 4 still here");
  await expect(page.getByText("Working").first()).toBeVisible();
  const down = Date.now();
  await Promise.all(APPS.map((n) => stopApp(n)));
  const note = page.getByTestId("connection");
  await expect(note).toContainText("Reconnecting");
  await expect(announced(page, "Reconnecting to your agent.")).toHaveCount(1);
  await expect(page.getByText("Working")).toHaveCount(0);

  // A message typed meanwhile stays in the box: it can't be sent yet.
  const box = page.getByLabel("Message");
  await box.fill("typed while away");
  await box.press("Enter");
  await expect(box).toHaveValue("typed while away");
  await expect(page.getByRole("button", { name: "Send" })).toBeDisabled();
  await shot(page, "66-reconnecting");

  await page.waitForTimeout(Math.max(0, 15_000 - (Date.now() - down)));
  await expect(page).toHaveURL(url);
  await Promise.all(APPS.map((n) => startApp(n)));
  const back = Date.now();
  await expect(note).toContainText("Reconnected", { timeout: 12_000 });
  await expect(announced(page, "Reconnected.")).toHaveCount(1);
  expect(Date.now() - back).toBeLessThan(11_000);
  await expect(page.getByTestId("user-msg")).toHaveText(["hello there", "slow: 4 still here"]);
  await expect(page.getByTestId("assistant-msg")).toHaveText(["Echo: hello there", "Echo: still here"]);
  await expect(page).toHaveURL(url);
  expect(await marked(page)).toBe(true);
  await shot(page, "67-reconnected");

  await expect(page.getByRole("button", { name: "Send" })).toBeEnabled();
  await box.press("Enter");
  await expect(lastAssistant(page)).toHaveText("Echo: typed while away");
  await expect(note).toHaveCount(0, { timeout: 10_000 }); // the note goes once it has said so
});

test("chat survives a restart onto the other replica", async ({ page }) => {
  test.skip(APPS.length < 2, "needs E2E_REPLICAS=2");
  test.setTimeout(150_000);
  const sockets: string[] = [];
  page.on("websocket", (ws) => sockets.push(ws.url()));
  // With app 2 down, the page and its chat connection land on app 1.
  await stopApp(2);
  await signUp(page, "Ines");
  await say(page, "hello there");
  await expect(lastAssistant(page)).toHaveText("Echo: hello there");
  await startApp(2);
  const url = page.url();
  await mark(page);

  // A reply streams from app 1 when it goes away: it finishes there, and the chat follows it from app 2.
  const words = "one two three four five six seven eight nine ten eleven twelve";
  await say(page, `typing: ${words}`);
  await expect(lastAssistant(page)).toContainText("Echo: one two");
  const before = sockets.length;
  await stopApp(1);
  await expect(lastAssistant(page)).toHaveText(`Echo: ${words}`); // once, with no word twice
  expect(sockets.length).toBeGreaterThan(before);
  await expect(page.getByTestId("assistant-msg")).toHaveCount(2);
  await expect(page).toHaveURL(url);
  expect(await marked(page)).toBe(true);
  await shot(page, "68-reconnected-other-replica");

  await say(page, "on the other one");
  await expect(lastAssistant(page)).toHaveText("Echo: on the other one");
});
