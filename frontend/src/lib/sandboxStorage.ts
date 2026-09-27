/**
 * PA Decision Sandbox — scenario history persistence.
 *
 * localStorage only, under its own namespaced key — completely separate from
 * clincase-jwt / clincase-user (real auth) and from any real case data. This
 * is scenario *history* for the sandbox UI, never a source of truth: clearing
 * it (or a user's browser storage) only loses saved sandbox scenarios, never
 * anything in the real cases table.
 */
import type { ScenarioRunResult } from "./sandboxSimulation";

const STORAGE_KEY = "clincase-sandbox-scenarios-v1";
const MAX_SAVED = 30;

export interface SavedScenario extends ScenarioRunResult {
  id: string;
}

export function loadScenarios(): SavedScenario[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    // Corrupt or inaccessible storage — sandbox starts empty rather than crashing.
    return [];
  }
}

function persist(scenarios: SavedScenario[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(scenarios.slice(0, MAX_SAVED)));
  } catch {
    // Storage full / unavailable (private browsing, quota) — fail soft. The
    // in-memory list in the component still reflects the save for this session.
  }
}

export function saveScenario(run: ScenarioRunResult): SavedScenario {
  const saved: SavedScenario = { ...run, id: `scn_${Math.random().toString(36).slice(2, 10)}` };
  const existing = loadScenarios();
  persist([saved, ...existing]);
  return saved;
}

export function deleteScenario(id: string): void {
  persist(loadScenarios().filter((s) => s.id !== id));
}

export function clearAllScenarios(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}
