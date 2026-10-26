import { expect, test } from "@playwright/test";

const tags = [
  "globird-usage-cost-card",
  "globird-electricity-usage-card",
  "globird-latest-day-card",
  "globird-account-card",
];
test("all built cards, duplicate registration, more-info and mobile layouts", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.setViewportSize({ width: 360, height: 900 });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute(
    "data-duplicate-module",
    "loaded",
  );
  for (const tag of tags)
    await expect(page.locator(tag).getByRole("heading")).toBeVisible();
  await expect(page.locator("globird-latest-day-card")).toContainText("-5 kWh");
  expect(await page.evaluate(() => window.customCards.length)).toBe(4);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page
    .locator(tags[0])
    .getByRole("button", { name: /Cost so far/ })
    .focus();
  await page.keyboard.press("Enter");
  await page.setViewportSize({ width: 1440, height: 1000 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
test("keyboard radio selection, gas pending reading and focus", async ({
  page,
}) => {
  await page.goto("/");
  const card = page.locator("globird-latest-day-card");
  const electricity = card.getByRole("radio", { name: "Electricity" });
  await electricity.focus();
  await page.keyboard.press("ArrowRight");
  await expect(card).toContainText("Gas meter reading");
  await expect(card).toContainText("No data");
  await expect(card.getByRole("radio", { name: "Gas" })).toBeFocused();
});
for (const tag of tags)
  test(`native editor for ${tag}`, async ({ page }) => {
    await page.goto(`/?editor=${tag}`);
    const editor = page.locator("globird-card-editor");
    const title = editor.getByLabel("Title (optional)");
    await title.fill("My energy");
    await expect(title).toHaveValue("My energy");
    await title.press("Tab");
    if (tag !== "globird-account-card")
      await expect(editor.getByLabel("History source")).toBeVisible();
  });
test("dark theme, loading, stale and unavailable states", async ({ page }) => {
  await page.goto("/?dark=true&mode=stale");
  await expect(page.locator(tags[0])).toContainText("Refresh failed");
  const color = await page
    .locator(tags[0])
    .locator("ha-card")
    .evaluate((e) => getComputedStyle(e).backgroundColor);
  expect(color).toBe("rgb(32, 33, 36)");
  await page.goto("/?mode=loading");
  await expect(page.locator(tags[0])).toContainText("Waiting for GloBird");
  await page.goto("/?mode=unavailable");
  await expect(page.locator(tags[2])).toContainText("Unavailable");
});

for (const dark of [false, true])
  test(`WCAG accessibility in ${dark ? "dark" : "light"} theme`, async ({
    page,
  }) => {
    await page.goto(`/?dark=${dark}&editor=globird-electricity-usage-card`);
    await expect(page.locator("html")).toHaveAttribute(
      "data-duplicate-module",
      "loaded",
    );
    await page.addScriptTag({ path: "node_modules/axe-core/axe.min.js" });
    const violations = await page.evaluate(async () => {
      const results = await window.axe.run(document, {
        runOnly: {
          type: "tag",
          values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"],
        },
      });
      return results.violations.map((v) => ({
        id: v.id,
        description: v.description,
        nodes: v.nodes.map((n) => n.target),
      }));
    });
    expect(violations).toEqual([]);
  });
