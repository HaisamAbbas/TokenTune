"use client";

import { useEffect, useState } from "react";

export type ThemePreference = "system" | "light" | "dark";

const STORAGE_KEY = "theme-preference";

export function getStoredTheme(): ThemePreference {
  if (typeof window === "undefined") return "system";
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") return stored;
  } catch {
    // localStorage can throw in private-browsing contexts - fall back to system.
  }
  return "system";
}

export function applyTheme(theme: ThemePreference): void {
  const root = document.documentElement;
  if (theme === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", theme);
  }
}

export function setStoredTheme(theme: ThemePreference): void {
  applyTheme(theme);
  try {
    window.localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Best-effort persistence only - the theme still applies for this load.
  }
}

/** Reads the current preference on mount (after the blocking init script has
 * already applied it) and exposes a setter that updates both the DOM
 * attribute and localStorage. */
export function useThemePreference(): [ThemePreference, (theme: ThemePreference) => void] {
  const [theme, setTheme] = useState<ThemePreference>("system");

  // This *must* be an effect, not a `useState(() => getStoredTheme())` lazy
  // initializer: this page is server-rendered (window is undefined there),
  // so a lazy initializer's "system" result from the server render is what
  // hydration keeps - it does not get recomputed against localStorage on
  // the client. An effect runs post-hydration unconditionally, which is the
  // whole point here: the real preference can only be known client-side.
  // Discovered for real - the lazy-initializer version left every reload
  // showing "System" as selected regardless of the actual stored/applied
  // theme, even though the theme itself (applied by the blocking head
  // script) was correct.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- see comment above: this sync-from-localStorage-on-mount is the intended behavior, not an accidental cascading render.
    setTheme(getStoredTheme());
  }, []);

  function update(next: ThemePreference) {
    setTheme(next);
    setStoredTheme(next);
  }

  return [theme, update];
}

/** Inlined into <head> as a blocking script so the correct theme (from a
 * prior visit) applies before first paint - without this, the page would
 * flash the wrong theme for a frame while React hydrates. */
export const themeInitScript = `
(function() {
  try {
    var theme = window.localStorage.getItem("${STORAGE_KEY}");
    if (theme === "light" || theme === "dark") {
      document.documentElement.setAttribute("data-theme", theme);
    }
  } catch (e) {}
})();
`;
