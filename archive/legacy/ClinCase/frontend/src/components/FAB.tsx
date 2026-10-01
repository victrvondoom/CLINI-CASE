/**
 * Floating Action Button — fixed bottom-right "New case" pill.
 * Ported from the deployed showcase (components.jsx FAB, lines 179-203).
 *
 * Behavior:
 *   - Pulses with the navy gradient via .fab-pulse keyframe
 *   - Hover expands to reveal the "New case" label
 *   - Keyboard shortcut hint "N" rendered as <kbd>
 *   - Clicking navigates to /intake (Drop a scan / new case workflow)
 */
import { Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";

export function FAB() {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      onClick={() => navigate("/intake")}
      className="group fixed bottom-6 right-6 z-30 inline-flex items-center gap-2 h-14 pl-4 pr-5 rounded-full text-white font-medium text-sm fab-pulse focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand focus-visible:ring-offset-2 focus-visible:ring-offset-surface-bg transition-transform active:scale-[0.97]"
      style={{
        background: "linear-gradient(180deg, #525252 0%, #121212 100%)",
        boxShadow:
          "inset 0 1px 0 rgba(255,255,255,0.20), 0 0 0 1px rgba(18,18,18,0.55), 0 18px 40px -12px rgba(18,18,18,0.55)",
      }}
      title="New case (N)"
      aria-label="Start a new case"
    >
      <span className="w-7 h-7 rounded-full grid place-items-center bg-white/15">
        <Plus size={16} className="text-white" />
      </span>
      <span className="max-w-0 overflow-hidden whitespace-nowrap transition-all duration-300 group-hover:max-w-[180px]">
        <span className="pl-1">New case</span>
      </span>
      <kbd className="hidden md:inline-block px-1.5 py-0.5 text-[10px] text-mono-tech bg-white/20 rounded text-white/95">
        N
      </kbd>
    </button>
  );
}
