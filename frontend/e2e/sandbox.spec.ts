import { execFileSync } from "node:child_process";
import { expect, test } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

test("an idle computer sleeps and wakes on the next command, files intact", async ({ page }) => {
  test.skip(process.env.E2E_SANDBOX !== "docker", "only Docker sandboxes are stopped while idle");
  await signUp(page);
  await say(page, "run: echo kept > kept.txt && echo saved");
  await expect(lastAssistant(page)).toContainText("Result: saved");
  const { name } = await (await page.request.get("/api/sandbox")).json();
  execFileSync("docker", ["stop", "-t", "0", name]); // what the idle sweep does after ACF_SANDBOX_IDLE_MINUTES
  await page.reload();
  await expect(nav(page).getByTestId("sandbox-status")).toHaveText("Computer asleep");
  await shot(page, "sandbox-asleep");

  await say(page, "run: cat kept.txt");
  await expect(lastAssistant(page)).toContainText("Result: kept");
  await page.reload();
  await expect(nav(page).getByTestId("sandbox-status")).toHaveText("Computer ready");
});
