import { expect, test } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

test("browse the workspace, upload, and see the agent's changes", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Files" }).click();
  const list = page.getByRole("list", { name: "Files" });
  await expect(list.getByRole("listitem")).toHaveText([/skills/, /context\.md/, /memory\.md/]);
  // No editor for context files: they are read-only here
  await list.getByRole("button", { name: /context\.md/ }).click();
  await expect(page.getByTestId("preview")).toContainText("About me");
  await expect(page.getByRole("textbox")).toHaveCount(0);

  await page.getByTestId("upload").setInputFiles({ name: "sales.csv", mimeType: "text/csv", buffer: Buffer.from("day,eur\nmon,120\n") });
  await list.getByRole("button", { name: /sales\.csv/ }).click();
  await expect(page.getByTestId("preview")).toContainText("mon,120");
  await expect(page.getByRole("link", { name: "Download" })).toHaveAttribute("href", /download=true/);

  // Changes happen through the agent
  await nav(page).getByRole("link", { name: "New chat" }).click();
  await say(page, "write: notes/plan.md | # Plan for Friday\n\n- Bake 40 pastéis de nata\n- Call the flour supplier");
  await expect(lastAssistant(page)).toContainText("Result: Wrote notes/plan.md");
  await say(page, "remember: Maya prefers euros");
  await expect(page.getByTestId("tool-step").last()).toContainText("memory.md");

  await nav(page).getByRole("link", { name: "Files" }).click();
  await list.getByRole("button", { name: /notes/ }).click();
  await expect(page.getByRole("navigation", { name: "Folder" })).toContainText("workspace/notes");
  await list.getByRole("button", { name: /plan\.md/ }).click();
  await expect(page.getByTestId("preview").getByRole("heading", { name: "Plan for Friday" })).toBeVisible();
  await shot(page, "06-files");
  await page.getByRole("navigation", { name: "Folder" }).getByRole("button", { name: "workspace" }).click();
  await list.getByRole("button", { name: /memory\.md/ }).click();
  await expect(page.getByTestId("preview")).toContainText("Maya prefers euros");
});
