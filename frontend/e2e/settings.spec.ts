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

test("only providers the server offers can be chosen", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Settings" }).click();
  await page.getByLabel("Model provider").selectOption("other");
  await page.getByLabel("LangChain provider id").fill("bedrock_converse");
  await page.getByLabel("Model", { exact: true }).fill("x");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("alert")).toContainText("doesn't offer 'bedrock_converse'");
  await expect(page.getByRole("alert")).toContainText("anthropic");
});

test("the server's key is only offered for the server's own model", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Settings" }).click();
  await expect(page.getByLabel("API key")).toHaveAttribute("placeholder", "Using the server's key");
  await page.getByLabel(/Server address/).fill("https://models.example.com");
  await expect(page.getByLabel("API key")).toHaveAttribute("placeholder", "Paste your API key");
  await expect(page.getByText("The server's key only works with its own model provider and address.")).toBeVisible();
  await shot(page, "12b-settings-own-key");
  await page.getByLabel(/Server address/).fill("");
  await page.getByLabel("Model provider").selectOption("openai");
  await expect(page.getByLabel("API key")).toHaveAttribute("placeholder", "Paste your API key");
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

test.describe("phone and light mode", () => {
  test.use({ viewport: { width: 390, height: 844 }, colorScheme: "light" });
  test("works on a phone in light mode", async ({ page }) => {
    await signUp(page);
    await shot(page, "13-phone-light-home");
    await expect(nav(page)).not.toBeInViewport();
    await say(page, "run: echo phone");
    await expect(lastAssistant(page)).toContainText("Result: phone");
    await shot(page, "14-phone-light-chat");
    await page.getByRole("button", { name: "Open menu" }).click();
    await nav(page).getByRole("link", { name: "Skills" }).click();
    await expect(page.getByRole("heading", { name: "Skills" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    expect(overflow).toBe(false);
  });
});
