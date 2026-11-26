const { chromium } = require(process.env.RMSW_PLAYWRIGHT_PATH || "playwright");

async function main() {
  const [base, output = "code/webapp/static/II2202-Final-Seminar.pdf"] = process.argv.slice(2);
  if (!base) throw new Error("Usage: node export_seminar_pdf.cjs <dashboard URL> [output PDF]");
  const url = new URL(base);
  url.search = "?deck=seminar&lang=en&print=1";
  url.hash = "presentation";
  const browser = await chromium.launch(
    process.env.RMSW_CHROMIUM_PATH ? { executablePath: process.env.RMSW_CHROMIUM_PATH } : {}
  );
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto(url.href);
    await page.locator('html[data-seminar-print="ready"]').waitFor({ state: "attached" });
    await page.evaluate(() => document.fonts.ready);
    if (await page.locator(".seminar-sheet").count() !== 12) throw new Error("Expected nine slides and three appendices");
    await page.pdf({ path: output, preferCSSPageSize: true, printBackground: true });
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
