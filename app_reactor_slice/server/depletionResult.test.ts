import assert from "node:assert/strict";
import test from "node:test";
import { parseDepletionLine } from "./depletionResult.ts";

test("reads the crossing line, including one printed before the inventory table", () => {
  const crossing =
    "Fuel depletion: keff crosses 1 at 0.0365297 years (13.3333 d), burnup 6.66667 MWd/kgHM. First step below 1 has keff 0.90000 +/- 0.00200";
  const log = [
    "k-effective (Collision) = 1.05000 +/- 0.00100",
    crossing,
    "Heavy metals",
    "k-effective (Absorption) = 0.90000 +/- 0.00200",
    crossing,
  ].join("\n");
  const parsed = parseDepletionLine(log);
  assert.ok(parsed);
  assert.equal(parsed.belowOne, true);
  assert.equal(parsed.years, 0.0365297);
  assert.equal(parsed.days, 13.3333);
  assert.equal(parsed.burnup, 6.66667);
  assert.equal(parsed.keff, 0.9);
  assert.equal(parsed.keffUncertainty, 0.002);
});

test("reads a run that never dropped below 1", () => {
  const parsed = parseDepletionLine(
    "Fuel depletion: keff stayed at or above 1 through 40 years (14600 d), burnup 88.2 MWd/kgHM (keff 1.01234 +/- 0.00210)",
  );
  assert.ok(parsed);
  assert.equal(parsed.belowOne, false);
  assert.equal(parsed.years, 40);
  assert.equal(parsed.days, 14600);
  assert.equal(parsed.burnup, 88.2);
  assert.equal(parsed.keff, 1.01234);
});
