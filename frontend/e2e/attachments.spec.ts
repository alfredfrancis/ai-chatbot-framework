import { expect, test } from "@playwright/test";
import { lastAssistant, nav, openSteps, say, shot, signUp } from "./helpers";

const csv = (body: string) => ({ name: "sales.csv", mimeType: "text/csv", buffer: Buffer.from(body) });

test("attach files to a chat message; the agent reads them and they stay in the history", async ({ page }) => {
  await signUp(page);

  // Attach from the home composer, change your mind about one, send with a question
  await expect(page.getByRole("button", { name: "Attach files" })).toBeVisible();
  await page.getByTestId("chat-upload").setInputFiles([csv("day,eur\nmon,120\n"), { name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("x") }]);
  const toSend = page.getByRole("list", { name: "Files to send" });
  await expect(toSend.getByRole("listitem")).toHaveText([/sales\.csv/, /notes\.txt/]);
  await toSend.getByRole("button", { name: "Remove notes.txt" }).click();
  await expect(toSend.getByRole("listitem")).toHaveText([/sales\.csv/]);
  await shot(page, "18-attach-file");
  await say(page, "read: uploads/sales.csv");

  const sent = page.getByTestId("user-msg").first();
  await expect(sent).toContainText("read: uploads/sales.csv");
  await expect(sent.getByRole("link", { name: "sales.csv" })).toHaveAttribute("href", /path=uploads%2Fsales\.csv/);
  await expect(lastAssistant(page)).toContainText("mon,120");
  await openSteps(page);
  await expect(page.getByTestId("tool-step").last()).toContainText("Read uploads/sales.csv");
  await expect(page.getByRole("list", { name: "Files to send" })).toHaveCount(0);

  // A file alone can be sent; a second sales.csv does not replace the first
  await page.getByTestId("chat-upload").setInputFiles(csv("day,eur\ntue,80\n"));
  await expect(page.getByRole("list", { name: "Files to send" })).toContainText("sales (1).csv");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByTestId("user-msg").last().getByRole("link", { name: "sales (1).csv" })).toBeVisible();
  // the agent got the file's place in the workspace
  await expect(lastAssistant(page)).toHaveText("Echo: Attached file: sales (1).csv");
  await shot(page, "19-chat-with-attachments");

  // After a reload the history shows the files again, not the raw link lines
  await page.reload();
  await expect(page.getByTestId("user-msg")).toHaveCount(2);
  await expect(page.getByTestId("user-msg").first()).toHaveText(/^read: uploads\/sales\.csvsales\.csv$/);
  await expect(page.getByTestId("user-msg").last().getByRole("link", { name: "sales (1).csv" })).toBeVisible();

  // The files are in the workspace
  await nav(page).getByRole("link", { name: "Files" }).click();
  const list = page.getByRole("list", { name: "Files" });
  await list.getByRole("button", { name: /uploads/ }).click();
  // (a file removed before sending was already uploaded; it stays in the workspace)
  await expect(list.getByRole("listitem")).toHaveText([/notes\.txt/, /sales \(1\)\.csv/, /sales\.csv/]);
});
