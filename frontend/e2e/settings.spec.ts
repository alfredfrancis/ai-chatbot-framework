import { expect, test } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

test("switch to an OpenAI-compatible model server", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Settings" }).click();
  await expect(page.getByText("Local folder (development mode)").or(page.getByText("Private container"))).toBeVisible();
  // A key and address for OpenAI-compatible servers…
  const openai = page.getByRole("region", { name: "OpenAI" });
  await expect(openai).toContainText("No API key");
  await openai.getByRole("button", { name: "Add key" }).click();
  const key = openai.getByRole("form", { name: "OpenAI key" });
  await key.getByLabel("OpenAI server address").fill("http://127.0.0.1:9100/v1");
  await key.getByLabel("OpenAI API key").fill("sk-local");
  await key.getByRole("button", { name: "Save OpenAI key" }).click();
  await expect(openai.getByRole("status")).toHaveText("Saved");
  await expect(openai).toContainText("Your key is saved · http://127.0.0.1:9100/v1");
  await expect(openai).not.toContainText("No API key");
  await openai.getByRole("button", { name: "Change key" }).click();
  await expect(key.getByLabel("OpenAI API key")).toHaveAttribute("placeholder", "•••••••• (saved)");
  await key.getByRole("button", { name: "Cancel" }).click();
  // …a model that server runs, made the default.
  await openai.getByLabel("New OpenAI model id").fill("llama3");
  await openai.getByRole("button", { name: "Add model" }).click();
  await expect(openai.getByRole("switch", { name: "Use llama3" })).toBeChecked();
  await page.getByLabel("Default model", { exact: true }).selectOption({ label: "llama3" });
  await expect(page.getByRole("region", { name: "Models" }).getByRole("status")).toHaveText("Saved");
  await shot(page, "12-settings");

  await nav(page).getByRole("link", { name: "New chat" }).click();
  await expect(page.getByLabel("Model", { exact: true })).toHaveValue("openai:llama3");
  await say(page, "run: echo via-openai");
  await expect(lastAssistant(page)).toContainText("Result: via-openai");
});

test("only providers the server offers can be chosen", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("region", { name: "Anthropic" })).toBeVisible();
  const more = page.getByLabel("Add a provider");
  expect(await more.locator("option").allTextContents()).not.toContain("bedrock_converse");
  // A provider added from the menu opens on its key.
  await more.selectOption("google_genai");
  await expect(page.getByRole("region", { name: "google_genai" }).getByLabel("google_genai API key")).toBeVisible();
});

test("the server's key is only offered for the server's own model", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Settings" }).click();
  const region = page.getByRole("region", { name: "Anthropic" });
  await expect(region).toContainText("Uses the server's key");
  await region.getByRole("button", { name: "Use my own key" }).click();
  const anthropic = region.getByRole("form", { name: "Anthropic key" });
  await expect(anthropic.getByLabel("Anthropic API key")).toHaveAttribute("placeholder", "Using the server's key");
  // The server's own model needs no address; the field is one click away.
  await expect(anthropic.getByLabel(/server address/)).toHaveCount(0);
  await anthropic.getByRole("button", { name: "Use a custom server address" }).click();
  await anthropic.getByLabel(/server address/).fill("https://models.example.com");
  await expect(anthropic.getByLabel("Anthropic API key")).toHaveAttribute("placeholder", "Paste your API key");
  await expect(anthropic.getByText("The server's key only works with its own model provider and address.")).toBeVisible();
  await shot(page, "12b-settings-own-key");
  await anthropic.getByLabel(/server address/).fill("");
  await expect(anthropic.getByLabel("Anthropic API key")).toHaveAttribute("placeholder", "Using the server's key");
  // Another provider never gets the server's key.
  const openai = page.getByRole("region", { name: "OpenAI" });
  await openai.getByRole("button", { name: "Add key" }).click();
  await expect(openai.getByLabel("OpenAI API key")).toHaveAttribute("placeholder", "Paste your API key");
});

test("model errors are shown to the user", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Settings" }).click();
  const openai = page.getByRole("region", { name: "OpenAI" });
  await openai.getByRole("button", { name: "Add key" }).click();
  await openai.getByLabel("OpenAI server address").fill("http://127.0.0.1:1/v1");
  await openai.getByLabel("OpenAI API key").fill("k");
  await openai.getByRole("button", { name: "Save OpenAI key" }).click();
  await expect(openai.getByRole("status")).toHaveText("Saved");
  await nav(page).getByRole("link", { name: "New chat" }).click();
  await page.getByLabel("Model", { exact: true }).selectOption({ label: "GPT-4.1 mini" });
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
