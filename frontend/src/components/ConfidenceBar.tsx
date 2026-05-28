import { INTENT_META } from './IntentBadge';

interface ConfidenceBarProps {
  intent: string | null;
  confidence: number | null;
}

export function ConfidenceBar({ intent, confidence }: ConfidenceBarProps) {
  if (confidence === null || confidence === undefined) return null;
  const pct = Math.round(confidence * 100);
  const meta = intent ? INTENT_META[intent] ?? INTENT_META['general'] : INTENT_META['general'];

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-slate-400 w-16 shrink-0">Confidence</span>
      <div className="flex-1 bg-slate-700 rounded-full h-1.5 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${meta.bar}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-slate-300 w-8 text-right">{pct}%</span>
    </div>
  );
}
