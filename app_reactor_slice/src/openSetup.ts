const LAST_SETUP_KEY = "reactor-slice-last-setup";

/** Name of the setup opened on the previous visit, or null when none was stored. */
export function readStoredSetup(): string | null {
  try {
    const stored = window.localStorage.getItem(LAST_SETUP_KEY);
    return stored && stored.trim() ? stored : null;
  } catch {
    return null;
  }
}

/** Remember which save was opened, or forget it when that save is deleted. */
export function writeStoredSetup(name: string | null): void {
  try {
    if (name && name.trim()) window.localStorage.setItem(LAST_SETUP_KEY, name);
    else window.localStorage.removeItem(LAST_SETUP_KEY);
  } catch {
    // Storage may be unavailable; the address still names the open setup.
  }
}

/**
 * Which saved setup to open.
 * An address that names a save wins. Otherwise the last opened save is used.
 * A library with one save opens that save when the address names none.
 */
export function chooseSetupToOpen(
  names: readonly string[],
  urlCfg: string | null,
  remembered: string | null,
): string | null {
  if (urlCfg && names.includes(urlCfg)) return urlCfg;
  if (!urlCfg && remembered && names.includes(remembered)) return remembered;
  if (!urlCfg && names.length === 1) return names[0];
  return null;
}

/**
 * True when the saved file should replace the page.
 * A remembered save is the visit's setup. An address that already carries
 * this visit's fields keeps those fields and only fills placeholder layers.
 */
export function usesSavedFile(hasUrlState: boolean, openedFromMemory: boolean): boolean {
  return openedFromMemory || !hasUrlState;
}
