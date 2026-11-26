import { expect, type Page, test } from "@playwright/test";

async function runSample(page: Page, suffix: string): Promise<string> {
  const samples: string[] = await (await page.request.get("/api/samples")).json();
  const name = samples.find((s) => s.endsWith(suffix));
  expect(name, `a ${suffix} sample`).toBeTruthy();
  await page.goto("/");
  await page.getByLabel("Sample").selectOption(name!);
  await page.getByRole("button", { name: "Run sample" }).click();
  await expect(page.getByLabel(/^8\. Insight report: Done/)).toBeVisible();
  return name!;
}

test("a DXF sample runs through the pipeline and its features trace to the drawing", async ({ page }) => {
  const name = await runSample(page, ".dxf");
  await expect(page.getByRole("button", { name: new RegExp(name.replace(".", "\\.")) })).toBeVisible();
  const sheet = page.getByRole("img", { name: /Drawing as read by the parser/ });
  await expect(sheet.locator(".ent-line").first()).toBeAttached();
  const markers = sheet.locator(".feature-mark");
  expect(await markers.count()).toBeGreaterThan(0);

  // A feature marker on the drawing selects the same feature in the panel and traces its source.
  await markers.first().click();
  await expect(page.locator(".feature.is-selected")).toHaveCount(1);
  expect(await sheet.locator(".ent.traced").count()).toBeGreaterThan(0);

  // Selecting a parameter in the panel traces its dimension on the drawing.
  await page.locator(".params .param").first().click();
  await expect(page.locator(".params .param[aria-pressed=true]")).toHaveCount(1);
  expect(await sheet.locator(".ent.traced").count()).toBeGreaterThan(0);
});

test("zoom and layer switches change the drawing view", async ({ page }) => {
  await runSample(page, ".dxf");
  const sheet = page.getByRole("img", { name: /Drawing as read by the parser/ });
  await expect(page.locator(".zoom-level")).toHaveText("100%");
  await page.getByRole("button", { name: "Zoom in" }).click();
  await expect(page.locator(".zoom-level")).toHaveText("125%");
  await page.getByRole("button", { name: "Fit" }).click();
  await expect(page.locator(".zoom-level")).toHaveText("100%");

  expect(await sheet.locator(".ent-dimension").count()).toBeGreaterThan(0);
  await page.getByRole("button", { name: /^Dimensions/ }).click();
  await expect(sheet.locator(".ent-dimension")).toHaveCount(0);
  await page.getByRole("button", { name: /^Dimensions/ }).click();
  expect(await sheet.locator(".ent-dimension").count()).toBeGreaterThan(0);

  await page.getByRole("button", { name: "Title block" }).click();
  await expect(page.getByRole("table", { name: "Title block" })).toHaveCount(0);
});

test("a STEP model opens in the 3D viewer and a hole highlights", async ({ page }) => {
  const meshReply = page.waitForResponse((r) => r.url().includes("/mesh") && r.status() === 200);
  await runSample(page, ".step");
  await meshReply;
  await expect(page.locator(".viewer3d canvas")).toBeVisible();
  await expect(page.getByText(/triangles, \d+ named faces/)).toBeVisible();
  const hole = page.locator(".hole-list .param").first();
  await hole.click();
  await expect(hole).toHaveAttribute("aria-pressed", "true");
});

test("the runs list reopens an earlier run", async ({ page }) => {
  const first = await runSample(page, ".dxf");
  await runSample(page, ".step");
  await page.getByRole("button", { name: new RegExp(first.replace(".", "\\.")) }).first().click();
  await expect(page.getByRole("img", { name: /Drawing as read by the parser/ })).toBeVisible();
  await expect(page).toHaveURL(/\?run=run-/);
});

test("chat answers list their sources and a source traces to the drawing (mocked model)", async ({ page }) => {
  await page.route("**/api/chat", (route) =>
    route.fulfill({ json: { available: true, reason: null, model: "test-model" } }),
  );
  await page.route("**/api/runs/*/chat", async (route) => {
    const run = await (await page.request.get(page.url().replace(/.*\?run=/, "/api/runs/"))).json();
    const geometry = await (
      await page.request.get(`/api/artifact?uri=${encodeURIComponent(run.artifacts.find((a: { kind: string }) => a.kind === "geometry").uri)}`)
    ).json();
    const dim = geometry.entities.find((e: { kind: string }) => e.kind === "dimension");
    await route.fulfill({
      json: {
        answer: "The first dimension is shown on the drawing.",
        from_facts: true,
        citations: [{ id: "D1", text: "linear dimension", handles: [dim.locator.handle] }],
        flags: [],
        cost_usd: 0.001,
        input_tokens: 10,
        output_tokens: 5,
        facts: 3,
      },
    });
  });
  await runSample(page, ".dxf");
  await page.getByRole("tab", { name: "Ask about it" }).click();
  await page.getByRole("button", { name: "List the holes with their diameters." }).click();
  const cite = page.locator(".cite").first();
  await expect(cite).toBeVisible();
  await cite.click();
  await expect(cite).toHaveAttribute("aria-pressed", "true");
  expect(await page.locator(".ent.traced").count()).toBeGreaterThan(0);
});

test("an unreadable upload is refused with a clear message", async ({ page }) => {
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles({ name: "notes.dxf", mimeType: "text/plain", buffer: Buffer.from("not a drawing") });
  await expect(page.getByRole("alert")).toContainText(/not|unsupported|recognised|type/i);
});
