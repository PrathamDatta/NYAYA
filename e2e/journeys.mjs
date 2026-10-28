// End-to-end journeys against a running instance:  BASE_URL=http://127.0.0.1:8000 node e2e/journeys.mjs
import { createRequire } from "node:module";
import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const require = createRequire(import.meta.url);
let playwright;
try { playwright = require("playwright"); } catch { playwright = require(path.join(execSync("npm root -g").toString().trim(), "playwright")); }
const { chromium } = playwright;
const BASE = process.env.BASE_URL ?? "http://127.0.0.1:8000";
const OUT = process.env.SHOTS ?? "/tmp/nyaya-shots";
fs.mkdirSync(OUT, { recursive: true });

const results = [];
async function step(name, fn) {
  const t0 = Date.now();
  try { await fn(); results.push({ name, ok: true, ms: Date.now() - t0 }); console.log(`PASS  ${name} (${Date.now() - t0} ms)`); }
  catch (e) { results.push({ name, ok: false, err: String(e.message).split("\n")[0] }); console.log(`FAIL  ${name}\n      ${String(e.message).split("\n").slice(0, 3).join("\n      ")}`); }
}
const email = `e2e-${Date.now()}@example.com`;
const browser = await chromium.launch();

async function desktop() {
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errors.push(m.text()); });

  await step("J1 landing page shows product, live system strip and nav links work", async () => {
    await page.goto(BASE);
    await page.getByRole("heading", { level: 1 }).waitFor();
    await page.getByText("Live from this installation").waitFor();
    await page.screenshot({ path: `${OUT}/01-landing.png`, fullPage: true });
    for (const [name, h1] of [["Library", "Legal library"], ["Legal aid", "Free legal aid"], ["How it works", "How answers are produced"], ["System status", "System status"]]) {
      await page.getByRole("navigation", { name: "Main", exact: true }).getByRole("link", { name }).click();
      await page.getByRole("heading", { level: 1, name: h1 }).waitFor();
    }
  });

  await step("J1b library search works without sign-in and shows provenance", async () => {
    await page.goto(`${BASE}/library`);
    await page.getByLabel("Search", { exact: true }).fill("right to be heard before eviction from reserved forest");
    await page.getByRole("button", { name: "Search" }).click();
    await page.locator("article").first().waitFor({ timeout: 90000 });
    await page.screenshot({ path: `${OUT}/02-library.png` });
    if (!(await page.locator("article a", { hasText: "Original source" }).count())) throw new Error("no original-source link on results");
  });

  await step("J2 register, ask a legal question, get cited sources or an explicit decline", async () => {
    await page.goto(`${BASE}/register`);
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("e2e-password-long-1");
    await page.getByRole("button", { name: "Create account" }).click();
    await page.waitForURL(/\/app\/ask/);
    await page.getByLabel("Your question").fill("Does a person living in a reserved forest area have a right to be heard by the Forest Officer before eviction?");
    await page.getByRole("button", { name: "Send question" }).click();
    await page.getByRole("heading", { name: "Sources" }).or(page.getByText("don't support an answer")).waitFor({ timeout: 120000 });
    await page.screenshot({ path: `${OUT}/03-answer.png`, fullPage: true });
    if (await page.getByRole("heading", { name: "Sources" }).count()) {
      await page.locator("ul li button[aria-expanded]").first().click();
      await page.getByText("Open original source").first().waitFor();
    }
    await page.waitForURL(/\/app\/ask\/\d+/);
  });

  await step("J2b unrelated question is declined, not answered", async () => {
    await page.getByRole("link", { name: "New question" }).click();
    await page.getByLabel("Your question").fill("Explain the taxation of cryptocurrency mining rigs on the moon?");
    await page.getByRole("button", { name: "Send question" }).click();
    await page.getByText("don't support an answer").waitFor({ timeout: 120000 });
  });

  await step("J2c history lists conversations and reopens one", async () => {
    const n = await page.locator('aside[aria-label="Conversation history"] li').count();
    if (n < 2) throw new Error(`expected >=2 conversations, saw ${n}`);
    await page.locator('aside[aria-label="Conversation history"] li a').nth(1).click();
    await page.locator("article").first().waitFor();
  });

  await step("J3 upload a document and see extracted facts with page numbers", async () => {
    await page.goto(`${BASE}/app/documents`);
    const text = "RENTAL AGREEMENT dated 01 August 2023 between Mr. Raghavan Murthy (hereinafter referred to as the Landlord) and Ms. Asha Rao (hereinafter referred to as the Tenant).\n1. Rent. The Tenant shall pay Rs. 25,000/- per month.\n2. Deposit. A security deposit of Rs. 1,20,000/- shall be refunded within 7 days of handover on 31/07/2024.\n";
    fs.writeFileSync("/tmp/rent.txt", text);
    await page.setInputFiles('input[type="file"]', "/tmp/rent.txt");
    await page.getByRole("link", { name: /rent\.txt/ }).click();
    await page.getByRole("heading", { name: "Dates" }).waitFor({ timeout: 90000 });
    await page.getByText("1,20,000").first().waitFor();
    await page.screenshot({ path: `${OUT}/04-document.png`, fullPage: true });
  });

  await step("J4 create a draft, see missing facts and authority check, edit, save, export docx", async () => {
    await page.goto(`${BASE}/app/drafts`);
    await page.getByRole("button", { name: /Legal demand notice/ }).click();
    await page.getByLabel("Your full name").fill("Asha Rao");
    await page.getByRole("button", { name: "Create draft" }).click();
    await page.getByText(/facts? still missing/).waitFor();
    await page.getByRole("heading", { name: "Authorities check" }).waitFor();
    await page.getByLabel("Edit the draft").fill((await page.getByLabel("Edit the draft").inputValue()) + "\nUser-added paragraph.");
    await page.getByRole("button", { name: "Save changes" }).click();
    await page.getByText("Draft saved").waitFor();
    await page.screenshot({ path: `${OUT}/05-draft.png`, fullPage: true });
    const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: /Word/ }).click()]);
    const p = await dl.path();
    if (fs.statSync(p).size < 2000 || fs.readFileSync(p).subarray(0, 2).toString() !== "PK") throw new Error("docx export invalid");
  });

  await step("J5 legal aid directory renders with verification dates", async () => {
    await page.goto(`${BASE}/app/aid`);
    await page.getByText(/Last verified/).first().waitFor();
    await page.getByLabel("Search directory").fill("Karnataka");
    await page.getByText("Karnataka State Legal Services Authority").waitFor();
    await page.screenshot({ path: `${OUT}/06-aid.png` });
  });

  await step("J6 translate refuses nothing silently: works or shows a typed error", async () => {
    await page.goto(`${BASE}/app/translate`);
    await page.getByLabel("English text").fill("The tenant shall return the security deposit within thirty days.");
    await page.getByRole("button", { name: "Translate", exact: true }).click();
    await page.locator(".indic").or(page.getByRole("alert")).first().waitFor({ timeout: 240000 });
    await page.screenshot({ path: `${OUT}/07-translate.png` });
  });

  await step("J7 settings: export data and delete account", async () => {
    await page.goto(`${BASE}/app/settings`);
    const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Export my data" }).click()]);
    const j = JSON.parse(fs.readFileSync(await dl.path(), "utf8"));
    if (j.user.email !== email || !j.drafts.length) throw new Error("export incomplete");
    await page.getByRole("button", { name: "Delete account…" }).click();
    await page.getByLabel("Confirmation").fill("DELETE");
    await page.getByRole("button", { name: "Delete everything" }).click();
    await page.waitForURL(`${BASE}/`);
    await page.goto(`${BASE}/app/ask`);
    await page.waitForURL(/\/login/);
  });

  await step("no uncaught browser errors on desktop", async () => { if (errors.length) throw new Error(errors.slice(0, 3).join(" | ")); });
  await ctx.close();
}

async function isolation() {
  await step("J8 another user cannot read a private resource (API, via browser session)", async () => {
    const a = await browser.newContext(), b = await browser.newContext();
    const H = { "X-Requested-With": "nyaya" };
    const ra = await a.request.post(`${BASE}/api/auth/register`, { data: { email: `a-${Date.now()}@example.com`, password: "e2e-password-long-1" }, headers: H });
    const rb = await b.request.post(`${BASE}/api/auth/register`, { data: { email: `b-${Date.now()}@example.com`, password: "e2e-password-long-1" }, headers: H });
    if (ra.status() !== 201 || rb.status() !== 201) throw new Error("register failed");
    const c = await (await a.request.post(`${BASE}/api/cases`, { data: { title: "private" }, headers: H })).json();
    const st = (await b.request.get(`${BASE}/api/cases/${c.id}`)).status();
    if (st !== 404) throw new Error(`expected 404, got ${st}`);
    const anon = await (await browser.newContext()).request.get(`${BASE}/api/cases/${c.id}`);
    if (anon.status() !== 401) throw new Error(`anon expected 401, got ${anon.status()}`);
    await a.request.delete(`${BASE}/api/auth/account`, { headers: H }); await b.request.delete(`${BASE}/api/auth/account`, { headers: H });
  });
}

async function mobile() {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const page = await ctx.newPage();
  await step("J9 mobile: no horizontal scroll on landing, register, ask a question", async () => {
    const overflow = async (label) => { const w = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth); if (w > 1) throw new Error(`${label}: horizontal overflow ${w}px`); };
    await page.goto(BASE); await page.getByRole("heading", { level: 1 }).waitFor(); await overflow("landing");
    await page.screenshot({ path: `${OUT}/08-mobile-landing.png`, fullPage: true });
    await page.goto(`${BASE}/register`);
    await page.getByLabel("Email").fill(`m-${Date.now()}@example.com`); await page.getByLabel("Password").fill("e2e-password-long-1");
    await page.getByRole("button", { name: "Create account" }).click(); await page.waitForURL(/\/app\/ask/); await overflow("ask");
    await page.getByLabel("Your question").fill("What can a tenant do if the landlord does not return the security deposit after vacating?");
    await page.getByRole("button", { name: "Send question" }).click();
    await page.locator("article").or(page.getByText("don't support an answer")).first().waitFor({ timeout: 120000 });
    await overflow("answer");
    await page.screenshot({ path: `${OUT}/09-mobile-answer.png`, fullPage: true });
    for (const p of ["/app/documents", "/app/drafts", "/app/cases", "/app/aid", "/library"]) { await page.goto(BASE + p); await page.waitForLoadState("networkidle"); await overflow(p); }
    await page.goto(`${BASE}/app/settings`); await page.getByRole("button", { name: "Delete account…" }).click();
    await page.getByLabel("Confirmation").fill("DELETE"); await page.getByRole("button", { name: "Delete everything" }).click(); await page.waitForURL(`${BASE}/`);
  });
  await ctx.close();
}

await desktop(); await isolation(); await mobile();
await browser.close();
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} journeys passed`);
fs.writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 2));
process.exit(failed.length ? 1 : 0);
