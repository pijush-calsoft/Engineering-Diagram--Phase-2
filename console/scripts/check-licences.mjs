// Licence gate for npm packages (plan §9), the counterpart of edp_ci.license_gate.
// Reads the licence that package-lock.json records for every installed package.
import { readFileSync } from "node:fs";

// Plan §9: permissive licences allowed anywhere.
const ALLOWED = new Set(["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "MPL-2.0"]);
// Not named in plan §9; allowed pending sign-off (OD-31).
const PENDING = new Set(["ISC", "0BSD", "OFL-1.1"]);

const lock = JSON.parse(readFileSync(new URL("../package-lock.json", import.meta.url), "utf8"));
const failures = [];
const pending = new Map();
for (const [path, meta] of Object.entries(lock.packages)) {
  if (!path) continue;
  const licence = meta.license ?? "(none)";
  const ids = licence.replace(/[()]/g, "").split(/\s+OR\s+/);
  if (ids.some((id) => ALLOWED.has(id))) continue;
  if (ids.some((id) => PENDING.has(id))) {
    pending.set(licence, (pending.get(licence) ?? 0) + 1);
    continue;
  }
  failures.push(`${path}: ${licence}`);
}
const total = Object.keys(lock.packages).length - 1;
for (const [licence, n] of pending) console.log(`pending sign-off (OD-31): ${licence} x${n}`);
if (failures.length) {
  console.error(`Licence gate FAILED for ${failures.length} of ${total} packages:\n  ${failures.join("\n  ")}`);
  process.exit(1);
}
console.log(`npm licence gate passed: ${total} packages.`);
