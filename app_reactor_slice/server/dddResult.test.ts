import assert from "node:assert/strict";
import test from "node:test";
import {
  displacementDamageFromResultsim,
  parseDisplacementDamageLine,
  parseIngaasPmaxLine,
  parseIngaasPmaxSensitivityLine,
  pmaxFromResultsim,
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
  assert.equal(
    pmaxFromResultsim(
      { kind: "gamma_dose", pmax_remaining: [0.8], pmax_fluence_m2: [1e15] },
      10,
    ),
    null,
  );
});

const PMAX_LINE =
  "InGaAs Pmax remaining: 8.2340e-01 of initial over 10 years (± 1.23%, 95% CI), XPNR-equivalent fluence 1.2340e+15 m^-2";

test("reads the Wang Pmax line next to the displacement damage", () => {
  const parsed = parseIngaasPmaxLine(PMAX_LINE);
  assert.ok(parsed);
  assert.equal(parsed.pmaxRemaining, 8.234e-1);
  assert.equal(parsed.pmaxYears, 10);
  assert.equal(parsed.pmaxCi95Pct, 1.23);
  assert.equal(parsed.pmaxFluenceM2, 1.234e15);
  assert.equal(parsed.pmaxOutsideRange, false);
  assert.equal(parseDisplacementDamageLine(PMAX_LINE), null);
});

test("flags a Pmax line outside the measured fluence", () => {
  const parsed = parseIngaasPmaxLine(`${PMAX_LINE} (outside measured range)`);
  assert.ok(parsed);
  assert.equal(parsed.pmaxOutsideRange, true);
});

test("reads the two calibration sensitivities", () => {
  const parsed = parseIngaasPmaxSensitivityLine(
    "InGaAs Pmax sensitivity: fast-fluence 8.5100e-01, truncated spectrum 8.4600e-01",
  );
  assert.ok(parsed);
  assert.equal(parsed.pmaxFastRemaining, 8.51e-1);
  assert.equal(parsed.pmaxTruncatedRemaining, 8.46e-1);
});

test("reads pmax fields stored beside ddd in resultsim.json", () => {
  const parsed = pmaxFromResultsim(
    {
      ddd: [3.1619e9],
      ddd_ci95p: 0.29,
      pmax_remaining: [8.234e-1],
      pmax_ci95p: 0.0123,
      pmax_fluence_m2: [1.234e15],
      pmax_outside: true,
      pmax_fast: [8.51e-1],
      pmax_truncated: [8.46e-1],
      n_batches: 20,
    },
    10,
  );
  assert.ok(parsed);
  assert.equal(parsed.pmaxRemaining, 8.234e-1);
  assert.equal(parsed.pmaxYears, 10);
  assert.ok(parsed.pmaxCi95Pct != null && Math.abs(parsed.pmaxCi95Pct - 1.23) < 1e-9);
  assert.equal(parsed.pmaxOutsideRange, true);
  assert.equal(parsed.pmaxFastRemaining, 8.51e-1);
});
