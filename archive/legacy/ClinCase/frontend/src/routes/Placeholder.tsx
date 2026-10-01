/**
 * Generic placeholder for pages not yet built. Renders a clean "coming in
 * Phase X" card so the sidenav is fully clickable from Phase 1 onward.
 */
import { Hammer } from "lucide-react";
import { Link } from "react-router-dom";

interface Props {
  title: string;
  phase: number;
  description: string;
}

export function Placeholder({ title, phase, description }: Props) {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <div className="bg-surface-raised border border-dashed border-surface-border rounded-2xl p-10 text-center">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-accent-brand/10 text-accent-brand mb-4">
          <Hammer size={20} />
        </div>
        <div className="text-[10px] text-compact text-ink-faint mb-2">
          Phase {phase}
        </div>
        <h1 className="text-xl font-semibold text-ink-primary mb-2">{title}</h1>
        <p className="text-sm text-ink-muted mb-6 max-w-md mx-auto leading-relaxed">
          {description}
        </p>
        <Link
          to="/dashboard"
          className="inline-flex items-center gap-1.5 text-sm text-accent-brand hover:underline"
        >
          Back to dashboard →
        </Link>
      </div>
    </div>
  );
}
