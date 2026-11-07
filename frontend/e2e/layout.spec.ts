import { expect, test } from "@playwright/test";
import { nav, say, shot, signUp } from "./helpers";

test("sidebar keeps full-height rows with many chats, and home lines up", async ({ page }) => {
  await signUp(page, "Layla");
  for (let i = 0; i < 18; i++) {
    await page.goto("/");
    await say(page, i % 2 ? "hello" : "can you describe the content of every file in my workspace please");
    await page.waitForURL(/\/c\//);
    await expect(page.getByTestId("assistant-msg").last()).toBeVisible();
  }
  const sidebar = nav(page);
  await expect(sidebar.getByRole("link", { name: /^hello$/ })).toHaveCount(9);

  // No row is squashed: nav items and recent chats stay 40px tall and show their whole text.
  for (const name of ["Files", "Skills", "Tasks", "Connections"]) {
    expect((await sidebar.getByRole("link", { name: new RegExp(`^${name}`) }).boundingBox())!.height).toBe(40);
  }
  const recents = sidebar.locator(".recent");
  for (const r of await recents.all()) {
    expect(await r.evaluate((el) => [el.clientHeight, el.scrollHeight])).toEqual([40, 40]);
  }
  // Only the recent chats scroll; the account row stays pinned and visible.
  await expect(sidebar.getByRole("button", { name: "Sign out" })).toBeInViewport();
  expect(await sidebar.locator(".recents").evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true);
  await expect(sidebar.getByRole("button", { name: "Search or run a command" })).toBeVisible();
  await shot(page, "sidebar-many-chats");

  // Home: greeting, composer and suggestions share one left edge.
  await page.goto("/");
  const left = async (l: ReturnType<typeof page.locator>) => Math.round((await l.boundingBox())!.x);
  const heading = await left(page.getByRole("heading", { level: 1 }));
  expect(await left(page.locator(".home .composer"))).toBe(heading);
  expect(await left(page.locator(".home .try"))).toBe(heading);
});

test("phone: section headers wrap instead of squeezing", async ({ browser }) => {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, colorScheme: "dark" });
  await signUp(page, "Pia");
  await page.goto("/connections");
  const heading = page.getByRole("heading", { name: "Popular apps" });
  await expect(heading).toBeVisible();
  expect((await heading.boundingBox())!.height).toBeLessThanOrEqual(28); // one line
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await shot(page, "phone-connections");
  await page.close();
});
