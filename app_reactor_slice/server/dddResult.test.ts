import assert from "node:assert/strict";
import test from "node:test";
import {
  displacementDamageFromResultsim,
  parseDisplacementDamageLine,
} from "./dddResult.ts";

const LINE =
  "Displacement damage: 3.1619e+09 MeV/g over 10 years (± 29.03%, 95% CI)";

test("reads the InGaAs displacement-damage line", () => {
  const parsed = parseDisplacementDamageLine(LINE);
  assert.ok(parsed);
  assert.equal(parsed.dddMeVPerG, 3.1619e9);
  assert.equal(parsed.dddYears, 10);
  assert.equal(parsed.dddCi95Pct, 29.03);
});

test("ignores other tally lines", () => {
  assert.equal(parseDisplacementDamageLine("Keff: 1.023980e+00"), null);
  assert.equal(
    parseDisplacementDamageLine("InGaAs gamma dose: 1.2e+01 kGy over 10 years (± 4.00%, 95% CI)"),
    null,
  );
});

test("reads resultsim.json and turns the fraction into a percent", () => {
  const parsed = displacementDamageFromResultsim(
    { ddd: [3.1619e9], ddd_ci95p: 0.29032337379903966, n_batches: 20 },
    10,
  );
  assert.ok(parsed);
  assert.equal(parsed.dddMeVPerG, 3.1619e9);
  assert.equal(parsed.dddYears, 10);
  assert.ok(parsed.dddCi95Pct != null && Math.abs(parsed.dddCi95Pct - 29.032337379903966) < 1e-9);
});

test("does not treat a gamma resultsim as neutron damage", () => {
  assert.equal(
    displacementDamageFromResultsim(
      { kind: "gamma_dose", gamma_kgy: [1.2], gamma_ci95p: 0.04, gamma_years: 10 },
      10,
    ),
    null,
  );
});
