import { chromium } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
import path from 'node:path';

const out = process.argv[2];
fs.mkdirSync(out, { recursive: true });
const results = {};
const browser = await chromium.launch();
const context = await browser.newContext();
const page = await context.newPage();
await page.goto('http://localhost:3000/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForTimeout(1500);
await page.screenshot({ path: path.join(out, 'login.png') });
const loginScan = await new AxeBuilder({ page }).analyze();
results.login = {
  url: page.url(),
  violations: loginScan.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length,
    targets: v.nodes.slice(0, 3).map((n) => n.target) })),
  passes: loginScan.passes.length,
};
const email = process.env.QA_TEST_EMAIL || '';
const password = process.env.QA_TEST_PASSWORD || '';
let authed = false;
try {
  const emailBox = page.locator('input[type="email"], input[name="email"]').first();
  const pwBox = page.locator('input[type="password"], input[name="password"]').first();
  await emailBox.fill(email, { timeout: 8000 });
  await pwBox.fill(password, { timeout: 8000 });
  await page.getByRole('button', { name: /sign in|log in/i }).click({ timeout: 8000 });
  await page.waitForURL((u) => !u.pathname.endsWith('/login') && u.pathname !== '/', { timeout: 20000 });
  authed = true;
} catch (e) {
  results.loginError = String(e).slice(0, 300);
}
results.authed = authed;
if (authed) {
  await page.getByRole('button', { name: /data sources/i }).click({ timeout: 10000 });
  await page.waitForURL(/data-sources/, { timeout: 15000 });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(out, 'data-sources.png'), fullPage: true });
  const dsScan = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  results.dataSources = {
    url: page.url(),
    violations: dsScan.violations.map((v) => ({ id: v.id, impact: v.impact,
      description: v.description, helpUrl: v.helpUrl,
      nodes: v.nodes.length, targets: v.nodes.slice(0, 3).map((n) => n.target),
      html: v.nodes.slice(0, 2).map((n) => n.html).join(' | ').slice(0, 400) })),
    passes: dsScan.passes.length,
  };
}
await browser.close();
fs.writeFileSync(path.join(out, 'axe.json'), JSON.stringify(results, null, 2));
console.log(JSON.stringify({ authed, loginViolations: results.login.violations,
  dsViolations: (results.dataSources || {}).violations || 'n/a' }, null, 2));
