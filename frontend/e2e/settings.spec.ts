import { expect, test } from "@playwright/test";
import { lastAssistant, say, signUp } from "./helpers";

test("switch to an OpenAI-compatible model server", async ({ page }) => {
  await signUp(page);
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByText("Local folder (development mode)").or(page.getByText("Private container"))).toBeVisible();
  await page.getByLabel("Model provider").selectOption("openai");
  await page.getByLabel("Model", { exact: true }).fill("llama3");
  await page.getByLabel(/Server address/).fill("http://127.0.0.1:9100/v1");
  await page.getByLabel("API key").fill("sk-local");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("status")).toHaveText("Saved");
  await expect(page.getByLabel("API key")).toHaveAttribute("placeholder", "•••••••• (saved)");

  await page.getByRole("link", { name: "Chats" }).click();
  await say(page, "run: echo via-openai");
  await expect(lastAssistant(page)).toContainText("Result: via-openai");
});

test("model errors are shown to the user", async ({ page }) => {
  await signUp(page);
  await page.getByRole("link", { name: "Settings" }).click();
  await page.getByLabel("Model provider").selectOption("openai");
  await page.getByLabel(/Server address/).fill("http://127.0.0.1:1/v1");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("status")).toHaveText("Saved");
  await page.getByRole("link", { name: "Chats" }).click();
  await say(page, "hi");
  await expect(page.getByRole("alert")).toContainText("Could not reach the model");
});

test("works on a phone-sized screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signUp(page);
  await expect(page.getByRole("navigation", { name: "Main" })).not.toBeInViewport();
  await page.getByRole("button", { name: "Open menu" }).click();
  await page.getByRole("link", { name: "Tasks" }).click();
  await expect(page.getByRole("heading", { name: "Tasks" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
});
