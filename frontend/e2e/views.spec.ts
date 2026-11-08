import { expect, test } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

const fence = "```";
const VIEW = `reply: Here is where the money went:

${fence}openui
root = Screen([spend, split, tabs, pick])
$food = 300
$when = "monthly"
spend = BarChart("Spending by month", ["Aug", "Sep", "Oct"], [{name: "Food", values: [320, 280, 345]}, {name: "Travel", values: [120, 410, 90]}], "EUR")
split = PieChart("October", [{label: "Food", value: 345}, {label: "Travel", value: 90}, {label: "Home", value: 610}], "EUR")
tabs = Tabs([Tab("Plan", [Steps([{title: "Cancel the gym", done: true}, {title: "Cook on Sundays", note: "Saves about 60 EUR"}])]), Tab("Bills", [List([{title: "Rent", note: "1st of the month", badge: "Paid", tone: "success"}]), Progress("Budget used", 420, 600)])])
pick = Card("Set a budget", [Slider("Monthly food budget", $food, 200, 500, 10), RadioGroup("Remind me", [{value: "weekly", label: "Weekly"}, {value: "monthly", label: "Monthly"}], $when), Button("Track it", @ToAssistant("Track food at " + $food + " EUR, remind me " + $when), "primary")])
${fence}

October was the highest month.`;

test("the agent answers with a chart and a choice; the user's pick comes back as a message", async ({ page }) => {
  await signUp(page);
  await say(page, VIEW);
  const answer = lastAssistant(page);
  await expect(answer).toContainText("October was the highest month.");
  const view = answer.getByTestId("chat-view");
  await expect(view.getByRole("figure", { name: "Spending by month" })).toBeVisible();
  await expect(view.getByRole("figure", { name: "Spending by month" }).getByRole("table")).toContainText("410");
  await expect(view.getByRole("figure", { name: "October" })).toContainText("Home");
  await expect(view.getByRole("figure", { name: "October" })).toContainText("58%");
  await expect(answer.locator("pre")).toHaveCount(0); // rendered, not shown as code

  // Tabs switch pages; the keyboard works too.
  await expect(view.getByRole("tab", { name: "Plan" })).toHaveAttribute("aria-selected", "true");
  await expect(view.getByText("Cook on Sundays")).toBeVisible();
  await view.getByRole("tab", { name: "Bills" }).click();
  await expect(view.getByText("Rent")).toBeVisible();
  await expect(view.getByRole("progressbar", { name: "Budget used" })).toHaveAttribute("aria-valuenow", "420");
  await view.getByRole("tab", { name: "Bills" }).press("ArrowLeft");
  await expect(view.getByRole("tab", { name: "Plan" })).toBeFocused();
  await expect(view.getByText("Cook on Sundays")).toBeVisible();

  await view.getByLabel("Monthly food budget").fill("450");
  await view.getByLabel("Weekly").check();
  await shot(page, "50-chat-view");

  await view.getByRole("button", { name: "Track it" }).click();
  await expect(page.getByTestId("user-msg").last()).toHaveText("Track food at 450 EUR, remind me weekly");
  await expect(lastAssistant(page)).toHaveText("Echo: Track food at 450 EUR, remind me weekly");

  // The view is part of the chat: it comes back after a reload.
  await page.reload();
  await expect(page.getByRole("figure", { name: "Spending by month" })).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("figure", { name: "Spending by month" }).scrollIntoViewIfNeeded();
  await shot(page, "51-chat-view-phone");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test("a chat view says what it cannot do and lists its problems", async ({ page }) => {
  await signUp(page);
  await say(page, `reply: Two views:

${fence}openui
root = Screen([b])
b = Board("To-do", "apps/x/tasks.json", [{id: "do", title: "Do"}])
${fence}

${fence}openui
root = Screen([Nope("x")])
${fence}

${fence}python
print("plain code stays code")
${fence}`);
  const answer = lastAssistant(page);
  await expect(answer.getByRole("note")).toHaveText("A board works in a personal app, not in a chat.");
  await expect(answer.getByText("This view has problems")).toBeVisible();
  await answer.getByText("This view has problems").click();
  await expect(answer.locator(".oui-problems")).toContainText("Nope");
  await expect(answer.locator("pre")).toContainText("plain code stays code");
});

test("a personal app charts its data file and follows the agent's edits", async ({ page }) => {
  await signUp(page);
  const write = (path: string, content: string) => `tool: write ${JSON.stringify({ path, content })}`;
  const screen = `root = Screen([top, chart, trend, more])
spend = Query("read_file", {path: "apps/budget/spend.json"}, {data: {months: [], food: []}}, 2)
top = Grid([Stat("Months", @Count(spend.data.months)), Stat("Total food", @Sum(spend.data.food))], 2)
chart = BarChart("Food by month", spend.data.months, [{name: "Food", values: spend.data.food}], "EUR")
trend = LineChart("Food trend", spend.data.months, [{name: "Food", values: spend.data.food}])
more = Collapsible("How this is counted", [Text("Card payments tagged **food**.")])`;
  await say(page, [
    write("apps/budget/app.json", JSON.stringify({ title: "Budget", order: 1 })),
    write("apps/budget/app.oui", screen),
    write("apps/budget/spend.json", JSON.stringify({ months: ["Aug", "Sep"], food: [320, 280] })),
  ].join("\n"));
  await expect(lastAssistant(page)).toContainText("Result:");

  await nav(page).getByRole("group", { name: "Apps" }).getByRole("link", { name: "Budget", exact: true }).click();
  const chart = page.getByRole("figure", { name: "Food by month" });
  await expect(chart.getByRole("table")).toContainText("280");
  await expect(page.locator(".oui-stat").nth(1)).toContainText("600");
  await expect(page.getByRole("figure", { name: "Food trend" })).toBeVisible();
  await page.getByText("How this is counted").click();
  await expect(page.getByText("Card payments tagged")).toBeVisible();
  await shot(page, "52-app-charts");

  await nav(page).getByRole("link", { name: "New chat" }).click();
  await say(page, write("apps/budget/spend.json", JSON.stringify({ months: ["Aug", "Sep", "Oct"], food: [320, 280, 345] })));
  await expect(lastAssistant(page)).toContainText("Result:");
  await nav(page).getByRole("group", { name: "Apps" }).getByRole("link", { name: "Budget", exact: true }).click();
  await expect(chart.getByRole("table")).toContainText("345");
  await expect(page.locator(".oui-stat").nth(1)).toContainText("945");
});
