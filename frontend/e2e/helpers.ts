import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { expect, type Page } from "@playwright/test";

let n = 0;
const SHOTS = new URL("../../docs/screenshots/e2e/", import.meta.url).pathname;
mkdirSync(SHOTS, { recursive: true });

/** Save a screenshot of the current state into docs/screenshots/e2e/<name>.png. */
export async function shot(page: Page, name: string) {
  await page.waitForTimeout(250); // let transitions settle
  await page.screenshot({ path: `${SHOTS}${name}.png` });
}

export async function signUp(page: Page, name = "Maya") {
  const email = `e2e-${Date.now()}-${n++}@example.com`;
  const config = page.waitForResponse("**/api/auth/config");
  await page.goto("/");
  await config;
  await expect(page.getByRole("heading", { name: /Welcome back|Create your account/ })).toBeVisible();
  const toggle = page.getByRole("button", { name: "New here? Create an account" });
  if (await toggle.isVisible()) await toggle.click();
  await page.getByLabel("Name").fill(name);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("correct horse battery");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: new RegExp(`^Good (morning|afternoon|evening), ${name}\\.$`) })).toBeVisible();
  return email;
}

export async function say(page: Page, text: string) {
  const box = page.getByLabel("Message");
  await box.fill(text);
  await box.press("Enter");
}

export const lastAssistant = (page: Page) => page.getByTestId("assistant-msg").last();
export const nav = (page: Page) => page.getByRole("navigation", { name: "Main" });

/** Once the agent has finished, open every folded group of steps so each step row shows. */
export async function openSteps(page: Page, scope = page.locator("body")) {
  await expect(scope.getByTestId("steps-summary").first()).toBeVisible(); // a finished group of steps folds
  await expect(page.getByRole("button", { name: "Stop" })).toHaveCount(0);
  const folded = scope.locator('[data-testid="steps-summary"][aria-expanded="false"]');
  while (await folded.count()) await folded.first().click();
}

/** The app processes start-acf.sh runs (E2E_REPLICAS of them behind one address, else one), numbered from 1. */
export const APPS = Array.from({ length: Math.max(1, Number(process.env.E2E_REPLICAS ?? 1)) }, (_, i) => i + 1);
const CTL = process.env.E2E_CTL_DIR ?? new URL("../test-results/acf-ctl/", import.meta.url).pathname;
const appUrl = (n: number) => `http://127.0.0.1:${APPS.length > 1 ? 8765 + n : 8765}/api/health`;
const alive = (pid: number) => { try { process.kill(pid, 0); return true; } catch { return false; } };

/** Stop app process `n` and keep it down until startApp(n). SIGTERM is a deploy (running agents get their
 *  shutdown grace to finish); SIGKILL is a crash. */
export async function stopApp(n = 1, signal: NodeJS.Signals = "SIGTERM") {
  writeFileSync(`${CTL}app-${n}.hold`, "");
  const pid = Number(readFileSync(`${CTL}app-${n}.pid`, "utf8"));
  process.kill(pid, signal);
  await expect.poll(() => alive(pid), { timeout: 40_000 }).toBe(false);
}

export async function startApp(n = 1) {
  rmSync(`${CTL}app-${n}.hold`, { force: true });
  await expect.poll(() => fetch(appUrl(n)).then((r) => r.ok, () => false), { timeout: 30_000 }).toBe(true);
}
