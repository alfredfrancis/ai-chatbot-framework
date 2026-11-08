import { expect, test, type Page } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

const COLUMNS = [
  { id: "do", title: "Do first", hint: "Urgent and important" },
  { id: "schedule", title: "Schedule", hint: "Important, not urgent" },
  { id: "delegate", title: "Delegate", hint: "Urgent, not important" },
  { id: "drop", title: "Drop", hint: "Neither" },
];
const COCKPIT = {
  title: "Cockpit",
  description: "What needs you today",
  order: 1,
  blocks: [
    { type: "markdown", title: "Needs you", file: "apps/cockpit/brief.md" },
    { type: "board", title: "To-do", file: "apps/cockpit/tasks.json", columns: COLUMNS, on_change: "run: echo synced-$((40+2))" },
    { type: "buttons", buttons: [
      { label: "Refresh", action: "ask_agent", args: { prompt: "write: apps/cockpit/brief.md | Brief refreshed by the agent." } },
      { label: "Count tasks", action: "run", args: { script: "count" }, confirm: "Count the open tasks?" },
    ] },
  ],
};
const TASKS = {
  items: [
    { id: "1", title: "Book flights", column: "do", due: "Fri", note: "email from Ana", done: false },
    { id: "2", title: "Renew passport", column: "schedule", done: false },
    { id: "3", title: "Newsletter", column: "drop", done: false },
  ],
};
const write = (path: string, content: string) => `tool: write ${JSON.stringify({ path, content })}`;

/** The agent makes the Cockpit, the way the personal-assistant skill does. */
async function makeCockpit(page: Page) {
  await say(page, [
    write("apps/cockpit/app.json", JSON.stringify(COCKPIT, null, 2)),
    write("apps/cockpit/tasks.json", JSON.stringify(TASKS, null, 2)),
    write("apps/cockpit/brief.md", "**Book flights** before Friday - Ana is waiting."),
    write("apps/cockpit/actions/count.sh", "grep -c '\"done\": false' apps/cockpit/tasks.json || true\n"),
  ].join("\n"));
  await expect(lastAssistant(page)).toContainText("Result:");
}

const quadrant = (page: Page, name: string) => page.getByRole("region", { name, exact: true });

test("the agent makes a Cockpit app; the user moves tasks and the agent reacts", async ({ page }) => {
  await signUp(page);
  await makeCockpit(page);

  const apps = nav(page).getByRole("group", { name: "Apps" });
  await apps.getByRole("link", { name: "Cockpit", exact: true }).click();
  await expect(page).toHaveURL(/\/apps\/cockpit$/);
  await expect(page.getByRole("heading", { name: "Cockpit", level: 1 })).toBeVisible();
  await expect(page.getByRole("region", { name: "Needs you" })).toContainText("Book flights before Friday");
  await expect(quadrant(page, "Do first").getByTestId("item-Book flights")).toContainText("Fri · email from Ana");
  await expect(quadrant(page, "Drop")).toContainText("Newsletter");
  await shot(page, "40-app-cockpit");

  // Move with the menu (keyboard and phone), then by dragging.
  await page.getByLabel("Move Book flights").selectOption({ label: "Schedule" });
  await expect(quadrant(page, "Schedule").getByTestId("item-Book flights")).toBeVisible();
  await page.getByTestId("item-Newsletter").dragTo(quadrant(page, "Delegate"));
  await expect(quadrant(page, "Delegate").getByTestId("item-Newsletter")).toBeVisible();

  // Tick one done and add one.
  await page.getByLabel("Done: Renew passport").check();
  await page.getByLabel("Add to Do first").fill("Call the dentist");
  const saved = page.waitForResponse((r) => r.url().endsWith("/actions") && r.request().postData()!.includes("Call the dentist"));
  await page.getByLabel("Add to Do first").press("Enter");
  await expect(quadrant(page, "Do first")).toContainText("Call the dentist");
  await saved;

  // The files are the backend: the board survives a reload.
  await page.reload();
  await expect(quadrant(page, "Schedule").getByTestId("item-Book flights")).toBeVisible();
  await expect(quadrant(page, "Delegate").getByTestId("item-Newsletter")).toBeVisible();
  await expect(page.getByLabel("Done: Renew passport")).toBeChecked();
  await expect(quadrant(page, "Do first")).toContainText("Call the dentist");

  // A button sends work to the agent in the background; the screen updates when it is done.
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByRole("region", { name: "Needs you" })).toContainText("Brief refreshed by the agent.");
  await expect(page.getByRole("status")).toHaveCount(0);

  // A sandbox script, behind a confirmation.
  await page.getByRole("button", { name: "Count tasks" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("Count the open tasks?");
  await page.getByRole("button", { name: "Yes, count tasks" }).click();
  await expect(page.getByRole("region", { name: "Result" })).toContainText("3");
  await shot(page, "41-app-cockpit-moved");

  // The board's on_change and the button reached the agent in the app's own chat.
  await page.getByRole("link", { name: "Open chat" }).click();
  await expect(page.locator(".topbar .here")).toHaveText("Cockpit app");
  await expect(page.getByTestId("assistant-msg").filter({ hasText: "synced-42" }).first()).toBeVisible();
  await expect(page.getByText(/\[App: Cockpit, apps\/cockpit\/app.json\] Moved "Book flights" from "Do first" to "Schedule"/)).toBeVisible();

  // Apps are in the command menu too.
  await page.keyboard.press("Control+k");
  await page.getByLabel("Search commands").fill("cock");
  await page.getByRole("option", { name: "Cockpit", exact: true }).click();
  await expect(page).toHaveURL(/\/apps\/cockpit$/);
});

test("a broken app.json shows an error; phone and light layouts work", async ({ browser }) => {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, colorScheme: "light" });
  await signUp(page);
  await makeCockpit(page);
  await say(page, write("apps/notes/app.json", "{ not json"));
  await expect(lastAssistant(page)).toContainText("Result:");
  await page.goto("/apps/notes");
  await expect(page.getByRole("alert")).toContainText("apps/notes/app.json is not valid");
  await page.goto("/apps/cockpit");
  await expect(quadrant(page, "Do first")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.getByLabel("Move Book flights").selectOption({ label: "Drop" });
  await expect(quadrant(page, "Drop").getByTestId("item-Book flights")).toBeVisible();
  await shot(page, "42-app-cockpit-phone-light");
  await page.getByRole("button", { name: "Open menu" }).click();
  await expect(nav(page).getByRole("group", { name: "Apps" }).getByRole("link")).toHaveText(["notes", "Cockpit"]);
  await page.close();
});
