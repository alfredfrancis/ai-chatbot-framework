import { expect, test } from "@playwright/test";
import { nav, shot, signUp } from "./helpers";

test("the web app installs as an app and opens offline", async ({ page, context }) => {
  await signUp(page);

  // Installable: a valid manifest with icons, and a service worker that controls the page.
  const manifest = await page.evaluate(async () => {
    const href = document.querySelector<HTMLLinkElement>('link[rel="manifest"]')!.href;
    return (await fetch(href)).json();
  });
  expect(manifest).toMatchObject({ name: "AI Chatbot Framework", short_name: "AI Chatbot", start_url: "/", display: "standalone" });
  const sizes = manifest.icons.map((i: { sizes: string; purpose?: string }) => `${i.sizes} ${i.purpose ?? "any"}`);
  expect(sizes).toEqual(expect.arrayContaining(["192x192 any", "512x512 any", "512x512 maskable"]));
  for (const icon of manifest.icons) {
    const res = await page.request.get(icon.src);
    expect(res.ok(), icon.src).toBe(true);
    expect(res.headers()["content-type"]).toBe("image/png");
  }
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload();
  await expect(page.getByLabel("Message")).toBeVisible();
  expect(await page.evaluate(() => navigator.serviceWorker.controller?.scriptURL)).toMatch(/\/sw\.js$/);

  // Chrome itself finds nothing in the way of installing it.
  const cdp = await context.newCDPSession(page);
  const { installabilityErrors } = await cdp.send("Page.getInstallabilityErrors");
  expect(installabilityErrors).toEqual([]);

  // Offline, the app still opens and says so instead of asking to sign in again.
  await context.setOffline(true);
  await page.goto("/files");
  await expect(page.getByRole("heading", { name: "You're offline" })).toBeVisible();
  await expect(page.getByText("Reconnect to the internet, then try again.")).toBeVisible();
  await expect(page.getByRole("heading", { name: /Welcome back|Create your account/ })).toHaveCount(0);
  await shot(page, "65-offline");

  // Back online, "Try again" picks up where the user was, still signed in.
  await context.setOffline(false);
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(nav(page).getByRole("link", { name: "Files" })).toBeVisible();
  await expect(page).toHaveURL(/\/files$/);
});

test("the API is never answered from the offline cache", async ({ page }) => {
  await signUp(page);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload();
  const cached = await page.evaluate(async () => {
    const keys: string[] = [];
    for (const name of await caches.keys()) {
      for (const req of await (await caches.open(name)).keys()) keys.push(new URL(req.url).pathname);
    }
    return keys;
  });
  expect(cached).toContain("/");
  expect(cached.some((p) => p.startsWith("/assets/"))).toBe(true);
  expect(cached.filter((p) => p.startsWith("/api/"))).toEqual([]);
});
