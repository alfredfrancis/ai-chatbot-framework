import { expect, test } from "@playwright/test";
import { shot, signUp } from "./helpers";

test("sign up, sign out and sign back in", async ({ page }) => {
  const email = await signUp(page);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await shot(page, "01-sign-in");

  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("wrong password!");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toHaveText("Wrong email or password");

  await page.getByLabel("Password").fill("correct horse battery");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /^Good (morning|afternoon|evening), Maya\.$/ })).toBeVisible();
});
