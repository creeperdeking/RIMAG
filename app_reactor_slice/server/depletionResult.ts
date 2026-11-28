export type DepletionParse = {
  summary: string;
  belowOne: boolean;
  years: number;
  days: number;
  burnup: number;
  keff: number;
  keffUncertainty: number;
};

const NUM = String.raw`[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?`;

const CROSSES = new RegExp(
  String.raw`Fuel depletion: keff crosses 1 at (${NUM}) years \((${NUM}) d\), burnup (${NUM}) MWd/kgHM\. First step below 1 has keff (${NUM}) \+\/- (${NUM})`,
  "i",
);

const STAYED = new RegExp(
  String.raw`Fuel depletion: keff stayed at or above 1 through (${NUM}) years \((${NUM}) d\), burnup (${NUM}) MWd/kgHM \(keff (${NUM}) \+\/- (${NUM})\)`,
  "i",
);

function read(match: RegExpMatchArray, belowOne: boolean): DepletionParse | null {
  const years = Number(match[1]);
  const days = Number(match[2]);
  const burnup = Number(match[3]);
  const keff = Number(match[4]);
  const keffUncertainty = Number(match[5]);
  if (![years, days, burnup, keff, keffUncertainty].every((value) => Number.isFinite(value))) {
    return null;
  }
  return {
    summary: match[0].trim(),
    belowOne,
    years,
    days,
    burnup,
    keff,
    keffUncertainty,
  };
}

/** Last fuel-lifetime line in a simulation log. */
export function parseDepletionLine(text: string): DepletionParse | null {
  let found: DepletionParse | null = null;
  for (const line of text.split(/\r?\n/)) {
    const crosses = line.match(CROSSES);
    if (crosses) {
      const parsed = read(crosses, true);
      if (parsed) found = parsed;
      continue;
    }
    const stayed = line.match(STAYED);
    if (stayed) {
      const parsed = read(stayed, false);
      if (parsed) found = parsed;
    }
  }
  return found;
}
