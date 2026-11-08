import { expect, test, type Page } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

const COCKPIT = { title: "Cockpit", description: "What needs you today", order: 1 };
const SCREEN = `root = Screen([summary, needs, todo, actions, notes])
brief = Query("read_file", {path: "apps/cockpit/brief.md"}, {text: ""}, 2)
tasks = Query("read_file", {path: "apps/cockpit/tasks.json"}, {data: {items: []}}, 2)
summary = Grid([Stat("Open to-dos", @Count(@Filter(tasks.data.items, "done", "==", false))), Stat("Do first", @Count(@Filter(tasks.data.items, "column", "==", "do")))], 2)
needs = Card("Needs you", [Text(brief.text)])
todo = Board("To-do", "apps/cockpit/tasks.json", [{id: "do", title: "Do first", hint: "Urgent and important"}, {id: "schedule", title: "Schedule", hint: "Important, not urgent"}, {id: "delegate", title: "Delegate", hint: "Urgent, not important"}, {id: "drop", title: "Drop", hint: "Neither"}], "run: echo synced-$((40+2))")
count = Mutation("run", {script: "count"})
actions = Row([Button("Refresh", @ToAssistant("write: apps/cockpit/brief.md | Brief refreshed by the agent."), "primary"), Button("Count tasks", @Run(count), "secondary", "Count the open tasks?"), counted])
counted = count.status == "success" ? Badge("Open: " + count.data.output, "success") : null
note = Query("read_file", {path: "apps/cockpit/note.md"}, {text: ""})
saveNote = Mutation("update_file", {path: "apps/cockpit/note.md", content: $note})
notes = Card("Notes", [Text(note.text), TextField("Quick note", $note, "Write something…"), Button("Save note", Action([@Run(saveNote), @Run(note), @Reset($note)]))])`;
const TASKS = {
  items: [
    { id: "1", title: "Book flights", column: "do", due: "Fri", note: "email from Ana", done: false },
    { id: "2", title: "Renew passport", column: "schedule", done: false },
    { id: "3", title: "Newsletter", column: "drop", done: false },
  ],
};
const write = (path: string, content: string) => `tool: write ${JSON.stringify({ path, content })}`;

/** The agent makes the Cockpit, the way the personal-assistant skill does. */
async function makeCockpit(page: Page, ...more: string[]) {
  await say(page, [
    write("apps/cockpit/app.json", JSON.stringify(COCKPIT, null, 2)),
    write("apps/cockpit/app.oui", SCREEN),
    write("apps/cockpit/tasks.json", JSON.stringify(TASKS, null, 2)),
    write("apps/cockpit/brief.md", "**Book flights** before Friday - Ana is waiting."),
    write("apps/cockpit/actions/count.sh", "grep -c '\"done\": false' apps/cockpit/tasks.json || true\n"),
    ...more,
  ].join("\n"));
  await expect(lastAssistant(page)).toContainText("Result:");
}

const quadrant = (page: Page, name: string) => page.getByRole("region", { name, exact: true });

test("the agent makes a Cockpit app; the user moves tasks and the agent reacts", async ({ page }) => {
  await signUp(page);
  await makeCockpit(page);

  // The user's own apps sit in their own labelled section of the sidebar, and of the command menu.
  const apps = nav(page).getByRole("group", { name: "Your apps" });
  await expect(apps.getByText("Your apps", { exact: true })).toBeVisible();
  await apps.getByRole("link", { name: "Cockpit", exact: true }).click();
  await expect(page).toHaveURL(/\/apps\/cockpit$/);
  await expect(page.getByRole("heading", { name: "Cockpit", level: 1 })).toBeVisible();
  await expect(page.getByRole("region", { name: "Needs you" })).toContainText("Book flights before Friday");
  await expect(quadrant(page, "Do first").getByTestId("item-Book flights")).toContainText("Fri · email from Ana");
  await expect(quadrant(page, "Drop")).toContainText("Newsletter");
  await expect(page.getByText("Open to-dos")).toBeVisible();
  await expect(page.locator(".oui-stat").first()).toContainText("3");
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

  // Stats follow the file through their Query: 3 open (one ticked done, one added).
  await expect(page.locator(".oui-stat").first()).toContainText("3");

  // A sandbox script via Mutation("run"), behind a confirmation.
  await page.getByRole("button", { name: "Count tasks" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("Count the open tasks?");
  await page.getByRole("button", { name: "Yes, count tasks" }).click();
  await expect(page.getByText("Open: 3")).toBeVisible();

  // A form: $binding + Mutation("update_file") + refetching the Query.
  await page.getByLabel("Quick note").fill("Pick up dry cleaning");
  await page.getByRole("button", { name: "Save note" }).click();
  await expect(page.getByRole("region", { name: "Notes" })).toContainText("Pick up dry cleaning");
  await expect(page.getByLabel("Quick note")).toHaveValue("");
  await shot(page, "41-app-cockpit-moved");

  // The board's agentNote and the button reached the agent in the app's own chat.
  await page.getByRole("link", { name: "Open chat" }).click();
  await expect(page.locator(".topbar .here")).toHaveText("Cockpit app");
  await expect(page.getByTestId("assistant-msg").filter({ hasText: "synced-42" }).first()).toBeVisible();
  await expect(page.getByText(/\[App: Cockpit, apps\/cockpit\/app.json\] Moved "Book flights" from "Do first" to "Schedule"/)).toBeVisible();

  // Apps are in the command menu too.
  await page.keyboard.press("Control+k");
  await page.getByLabel("Search commands").fill("cock");
  await expect(page.getByRole("dialog").getByText("Your apps", { exact: true })).toBeVisible();
  await page.getByRole("option", { name: "Cockpit", exact: true }).click();
  await expect(page).toHaveURL(/\/apps\/cockpit$/);
});

test("a broken screen shows its problems and the agent is asked to fix it; phone and light layouts work", async ({ browser }) => {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, colorScheme: "light" });
  await signUp(page);
  await makeCockpit(page,
    write("apps/notes/app.json", JSON.stringify({ title: "Notes" })),
    write("apps/notes/app.oui", 'root = Screen([Chart("x")])'),
    write("apps/broken/app.json", "{ not json"));

  await page.goto("/apps/broken");
  await expect(page.getByRole("alert")).toContainText("apps/broken/app.json is not valid");
  await page.goto("/apps/notes");
  await expect(page.getByRole("alert")).toContainText("Chart");
  await shot(page, "43-app-problems");
  await page.getByRole("button", { name: "Ask the agent to fix it" }).click();
  await page.getByRole("link", { name: "Open chat" }).click();
  await expect(page.getByText(/\[App: Notes, apps\/notes\/app.json\] The screen has errors\./)).toBeVisible();

  await page.goto("/apps/cockpit");
  await expect(quadrant(page, "Do first")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.getByLabel("Move Book flights").selectOption({ label: "Drop" });
  await expect(quadrant(page, "Drop").getByTestId("item-Book flights")).toBeVisible();
  await shot(page, "42-app-cockpit-phone-light");
  await page.getByRole("button", { name: "Open menu" }).click();
  await expect(nav(page).getByRole("group", { name: "Your apps" }).getByRole("link")).toHaveText(["broken", "Cockpit", "Notes", /See all apps/]);
  await page.close();
});

test("the sidebar shows three apps and links to all of them; Create app starts a chat with the app prompt", async ({ page }) => {
  await signUp(page);
  const app = (id: string, title: string) => [
    write(`apps/${id}/app.json`, JSON.stringify({ title, description: `${title} app` })),
    write(`apps/${id}/app.oui`, 'root = Screen([Text("hi")])'),
  ];
  await makeCockpit(page, ...app("budget", "Budget"), ...app("reading", "Reading list"), ...app("workouts", "Workouts"));

  const apps = nav(page).getByRole("group", { name: "Your apps" });
  await expect(apps.getByRole("link")).toHaveText(["Cockpit", "Budget", "Reading list", /See all apps\s*4/]);
  await apps.getByRole("link", { name: /See all apps/ }).click();
  await expect(page).toHaveURL(/\/apps$/);
  await expect(page.getByRole("heading", { name: "Your apps", level: 1 })).toBeVisible();
  for (const [id, t] of [["cockpit", "Cockpit"], ["budget", "Budget"], ["reading", "Reading list"], ["workouts", "Workouts"]]) {
    await expect(page.getByTestId(`app-${id}`)).toContainText(t);
  }
  await shot(page, "44-all-apps");

  await page.getByTestId("app-workouts").click();
  await expect(page).toHaveURL(/\/apps\/workouts$/);
  await page.goto("/apps");
  await page.getByRole("button", { name: "Create app" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByLabel("Message")).toHaveValue(
    "I want to build an app using the personal-apps skill. Interview me about my app requirements.");
  await shot(page, "45-create-app-prompt");
});
