import { expect, type Page } from "@playwright/test";

let n = 0;

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
  await expect(page.getByRole("heading", { name: `Hi ${name}. What can I do for you?` })).toBeVisible();
  return email;
}

export async function say(page: Page, text: string) {
  const box = page.getByLabel("Message");
  await box.fill(text);
  await box.press("Enter");
}

export const lastAssistant = (page: Page) => page.getByTestId("assistant-msg").last();
