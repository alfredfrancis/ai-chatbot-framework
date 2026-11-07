import { expect, test } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

test("switch to an OpenAI-compatible model server", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Settings" }).click();
  await expect(page.getByText("Local folder (development mode)").or(page.getByText("Private container"))).toBeVisible();
  await page.getByLabel("Model provider").selectOption("openai");
  await page.getByLabel("Model", { exact: true }).fill("llama3");
  await page.getByLabel(/Server address/).fill("http://127.0.0.1:9100/v1");
  await page.getByLabel("API key").fill("sk-local");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("status")).toHaveText("Saved");
  await expect(page.getByLabel("API key")).toHaveAttribute("placeholder", "•••••••• (saved)");
  await shot(page, "12-settings");

  await nav(page).getByRole("link", { name: "New chat" }).click();
  await say(page, "run: echo via-openai");
  await expect(lastAssistant(page)).toContainText("Result: via-openai");
});

test("any LangChain provider id can be chosen; bad ones are explained", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Settings" }).click();
  await page.getByLabel("Model provider").selectOption("other");
  await page.getByLabel("LangChain provider id").fill("nosuchprovider");
  await page.getByLabel("Model", { exact: true }).fill("x");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("status")).toHaveText("Saved");
  await nav(page).getByRole("link", { name: "New chat" }).click();
  await say(page, "hi");
  await expect(page.getByRole("alert")).toContainText(/nosuchprovider|set up the model/);
});

test("model errors are shown to the user", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Settings" }).click();
  await page.getByLabel("Model provider").selectOption("openai");
  await page.getByLabel("Model", { exact: true }).fill("m");
  await page.getByLabel(/Server address/).fill("http://127.0.0.1:1/v1");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("status")).toHaveText("Saved");
  await nav(page).getByRole("link", { name: "New chat" }).click();
  await say(page, "hi");
  await expect(page.getByRole("alert")).toContainText("Could not reach the model");
});

test.describe("phone and dark mode", () => {
  test.use({ viewport: { width: 390, height: 844 }, colorScheme: "dark" });
  test("works on a phone in dark mode", async ({ page }) => {
    await signUp(page);
    await shot(page, "13-phone-dark-home");
    await expect(nav(page)).not.toBeInViewport();
    await say(page, "run: echo phone");
    await expect(lastAssistant(page)).toContainText("Result: phone");
    await shot(page, "14-phone-dark-chat");
    await page.getByRole("button", { name: "Open menu" }).click();
    await nav(page).getByRole("link", { name: "Skills" }).click();
    await expect(page.getByRole("heading", { name: "Skills" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    expect(overflow).toBe(false);
  });
});
