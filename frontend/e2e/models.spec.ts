import { expect, test } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

test("pick a chat's model and effort in the message box", async ({ page }) => {
  await signUp(page);
  const model = page.getByLabel("Model", { exact: true });
  const effort = page.getByLabel("Effort", { exact: true });
  await expect(model).toHaveValue("anthropic:claude-opus-5-5");
  await expect(effort).toHaveValue("medium");
  // Models without a key are off, so they aren't offered.
  await expect(model.locator("option")).not.toContainText(["GPT-5"]);

  await model.selectOption({ label: "Claude Sonnet 5.5" });
  await effort.selectOption("high");
  await shot(page, "70-model-picker");
  await say(page, "show model");
  await expect(lastAssistant(page)).toHaveText("Model: claude-sonnet-5-5");
  await expect(model).toHaveValue("anthropic:claude-sonnet-5-5");
  await say(page, "show effort");
  await expect(lastAssistant(page)).toHaveText("Effort: high");

  // Mid-chat: the next message uses the new choice, and it is kept with the chat.
  await effort.selectOption("low");
  await say(page, "show effort");
  await expect(lastAssistant(page)).toHaveText("Effort: low");
  await page.reload();
  await expect(page.getByLabel("Model", { exact: true })).toHaveValue("anthropic:claude-sonnet-5-5");
  await expect(page.getByLabel("Effort", { exact: true })).toHaveValue("low");

  // A new chat starts on the default again.
  await nav(page).getByRole("link", { name: "New chat" }).click();
  await expect(page.getByLabel("Model", { exact: true })).toHaveValue("anthropic:claude-opus-5-5");
});

test("the model list: turn models on and off, set a token window, choose the default", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Settings" }).click();
  const anthropic = page.getByRole("region", { name: "Anthropic" });
  const openai = page.getByRole("region", { name: "OpenAI" });
  // Each provider holds its own models.
  await expect(anthropic.getByTestId("model-row")).toHaveCount(4);
  await expect(anthropic.getByRole("switch", { name: "Use Claude Opus 5.5" })).toBeChecked();
  await expect(openai.getByRole("switch", { name: "Use GPT-5", exact: true })).not.toBeChecked();
  await expect(openai).toContainText("No API key");

  // Off: gone from the picker.
  await anthropic.getByRole("switch", { name: "Use Claude Haiku 5.5" }).click();
  await expect(anthropic.getByRole("switch", { name: "Use Claude Haiku 5.5" })).not.toBeChecked();
  // The token window: the context meter and compaction follow it.
  await anthropic.getByRole("button", { name: "Options for Claude Opus 5.5" }).click();
  await anthropic.getByLabel("Token window").fill("64000");
  await anthropic.getByRole("button", { name: "Save token window" }).click();
  await expect(anthropic.getByTestId("model-row").filter({ hasText: "Claude Opus 5.5" })).toContainText("64K token window");
  // Default model and effort for new chats: saved as they change.
  const models = page.getByRole("region", { name: "Models" });
  await page.getByLabel("Default model", { exact: true }).selectOption({ label: "Claude Sonnet 5.5" });
  await expect(models.getByRole("status")).toHaveText("Saved");
  await expect(anthropic.getByTestId("model-row").filter({ hasText: "Claude Sonnet 5.5" })).toContainText("Default");
  await page.getByLabel("Default model", { exact: true }).selectOption({ label: "Claude Opus 5.5 (server default)" });
  await page.getByLabel("Default effort").selectOption("max");
  await expect(page.getByLabel("Default effort")).toHaveValue("max");
  await page.reload();
  await expect(page.getByLabel("Default model", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Default effort")).toHaveValue("max");
  await shot(page, "71-model-list");

  await nav(page).getByRole("link", { name: "New chat" }).click();
  const model = page.getByLabel("Model", { exact: true });
  await expect(model.locator("option")).not.toContainText(["Claude Haiku 5.5"]);
  await expect(page.getByLabel("Effort", { exact: true })).toHaveValue("max");
  await say(page, "show effort");
  await expect(lastAssistant(page)).toHaveText("Effort: max");
  await page.getByRole("button", { name: /Context usage/ }).click();
  await expect(page.getByRole("dialog", { name: "Context usage" })).toContainText("of 64,000 tokens");
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 390, height: 844 } });
  test("the pickers fit in the message box", async ({ page }) => {
    await signUp(page);
    await expect(page.getByLabel("Model", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Effort", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Send" })).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false);
    await shot(page, "72-phone-model-picker");
  });
});
