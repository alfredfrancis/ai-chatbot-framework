import { mkdirSync } from "node:fs";
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
  await expect(page.getByRole("heading", { name: "What can I take off your plate today?" })).toBeVisible();
  return email;
}

export async function say(page: Page, text: string) {
  const box = page.getByLabel("Message");
  await box.fill(text);
  await box.press("Enter");
}

export const lastAssistant = (page: Page) => page.getByTestId("assistant-msg").last();
export const nav = (page: Page) => page.getByRole("navigation", { name: "Main" });
