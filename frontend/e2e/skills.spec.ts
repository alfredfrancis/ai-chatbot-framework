import { execFileSync } from "node:child_process";
import { expect, test } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

const SKILL = `---
name: charts
description: Make clean bar charts from CSV files. Use when the user asks for a chart.
---
# Charts
1. Read the CSV.
2. Run python skills/charts/chart.py <file>.
`;

function zip(files: Record<string, string>): Buffer {
  const script = "import io,json,sys,zipfile\nb=io.BytesIO()\nz=zipfile.ZipFile(b,'w')\n" +
    "[z.writestr(k,v) for k,v in json.loads(sys.argv[1]).items()]\nz.close()\nsys.stdout.buffer.write(b.getvalue())";
  return execFileSync("python3", ["-c", script, JSON.stringify(files)]);
}

test("upload a skill, the agent uses it, remove it", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Skills" }).click();
  await expect(page.getByTestId("skill-skill-creator")).toBeVisible();

  await page.getByTestId("skill-upload").setInputFiles({
    name: "charts.zip", mimeType: "application/zip",
    buffer: zip({ "charts/SKILL.md": SKILL, "charts/chart.py": "print('chart')" }),
  });
  await expect(page.getByRole("status")).toHaveText("Added “charts”.");
  const card = page.getByTestId("skill-charts");
  await expect(card).toContainText("Make clean bar charts from CSV files.");
  await expect(card).toContainText("2 files");
  await shot(page, "07-skills");

  await page.getByTestId("skill-upload").setInputFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("x") });
  await expect(page.getByRole("alert")).toContainText("Upload a .zip");

  await nav(page).getByRole("link", { name: "New chat" }).click();
  await say(page, "show system");
  await expect(lastAssistant(page)).toContainText("charts: Make clean bar charts from CSV files.");
  await say(page, "read: skills/charts/SKILL.md");
  await expect(page.getByTestId("tool-step").last()).toContainText("Used skill charts");

  await nav(page).getByRole("link", { name: "Skills" }).click();
  await page.getByRole("button", { name: "More actions for charts" }).click();
  await page.getByRole("menuitem", { name: "Remove skill" }).click();
  await page.getByRole("menuitem", { name: "Yes, remove this skill" }).click();
  await expect(page.getByTestId("skill-charts")).toHaveCount(0);
});

test("upload a single SKILL.md", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Skills" }).click();
  await page.getByTestId("skill-upload").setInputFiles({ name: "SKILL.md", mimeType: "text/markdown", buffer: Buffer.from(SKILL) });
  await expect(page.getByTestId("skill-charts")).toContainText("1 file");
});
