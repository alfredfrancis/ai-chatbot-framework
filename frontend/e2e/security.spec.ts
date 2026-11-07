import { expect, test, type Page } from "@playwright/test";
import { nav, shot, signUp } from "./helpers";

/** Records Content-Security-Policy violations on the page, so a policy that breaks the app fails here. */
async function watchCsp(page: Page) {
  const violations: string[] = [];
  page.on("console", (m) => {
    if (/Content Security Policy/i.test(m.text())) violations.push(m.text());
  });
  await page.addInitScript(() => {
    document.addEventListener("securitypolicyviolation", (e) => {
      console.error(`Content Security Policy violation: ${e.violatedDirective} ${e.blockedURI}`);
    });
  });
  return violations;
}

test("the app works under its security headers", async ({ page }) => {
  const violations = await watchCsp(page);
  const res = await page.goto("/");
  const h = res!.headers();
  expect(h["content-security-policy"]).toContain("script-src 'self'");
  expect(h["content-security-policy"]).toContain("frame-ancestors 'none'");
  expect(h["x-content-type-options"]).toBe("nosniff");
  expect(h["x-frame-options"]).toBe("DENY");
  expect(h["referrer-policy"]).toBe("same-origin");

  await signUp(page);
  for (const name of ["Files", "Skills", "Connections", "Tasks", "Settings"]) {
    await nav(page).getByRole("link", { name }).click();
    await expect(page.getByRole("heading", { name, level: 1 })).toBeVisible();
  }
  await nav(page).getByRole("link", { name: "New chat" }).click();
  await page.getByLabel("Message").fill("hello");
  await page.getByLabel("Message").press("Enter");
  await expect(page.getByTestId("assistant-msg").last()).toContainText("Echo: hello"); // the WebSocket is allowed
  expect(violations).toEqual([]);
});

test("an HTML file in the workspace can't run scripts in the app", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Files" }).click();
  const html = '<h1 id="t">Report</h1><script>document.getElementById("t").textContent = "ran"; window.ran = true;</script>';
  await page.getByTestId("upload").setInputFiles({ name: "report.html", mimeType: "text/html", buffer: Buffer.from(html) });
  await expect(page.getByRole("list", { name: "Files" }).getByRole("button", { name: /report\.html/ })).toBeVisible();

  const res = await page.goto("/api/files/raw?path=report.html");
  expect(res!.headers()["content-security-policy"]).toMatch(/^sandbox;/);
  await expect(page.getByRole("heading", { name: "Report" })).toBeVisible();
  expect(await page.evaluate(() => (window as unknown as { ran?: boolean }).ran)).toBeUndefined();
  // a sandboxed page has no access to the app's origin (cookies, API)
  expect(await page.evaluate(() => window.origin)).toBe("null");
  await shot(page, "30-sandboxed-html-file");
});
