import { ShieldCheck, Loader2, RefreshCw } from 'lucide-react';
import type { QAScoreResponse } from '../types';

const DIMENSIONS: { key: keyof Pick<QAScoreResponse, 'empathy' | 'tone' | 'resolution' | 'professionalism'>; label: string; description: string }[] = [
  { key: 'empathy',        label: 'Empathy',        description: 'Agent acknowledged and validated customer feelings' },
  { key: 'tone',           label: 'Tone',            description: 'Professional, courteous, and calm throughout' },
  { key: 'resolution',     label: 'Resolution',      description: 'Customer issue fully resolved or appropriately escalated' },
  { key: 'professionalism',label: 'Professionalism', description: 'Followed correct procedures and communicated clearly' },
];

function scoreColor(pct: number | null) {
  if (pct === null) return { bar: 'bg-slate-700', text: 'text-slate-600' };
  if (pct >= 86) return { bar: 'bg-emerald-500', text: 'text-emerald-400' };
  if (pct >= 70) return { bar: 'bg-sky-500',     text: 'text-sky-400' };
  if (pct >= 50) return { bar: 'bg-amber-500',   text: 'text-amber-400' };
  return            { bar: 'bg-rose-500',         text: 'text-rose-400' };
}

interface QAScorePanelProps {
  scores?: QAScoreResponse | null;
  loading?: boolean;
  onRequestScore?: () => void;
  conversationId?: string;
}

export function QAScorePanel({ scores, loading, onRequestScore }: QAScorePanelProps) {
  const overall = scores ? Math.round(scores.overall_score * 100) : null;
  const { text: overallText } = scoreColor(overall);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-800">
        <ShieldCheck size={15} className="text-indigo-400" />
        <h2 className="text-sm font-semibold text-slate-200">QA Score</h2>
        {overall !== null && (
          <span className={`ml-auto text-lg font-bold tabular-nums ${overallText}`}>
            {overall}%
          </span>
        )}
        {!scores && !loading && onRequestScore && (
          <button
            onClick={onRequestScore}
            className="ml-auto inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/40 border border-indigo-500/30 text-xs text-indigo-300 transition-colors"
          >
            <ShieldCheck size={11} /> Run QA Score
          </button>
        )}
        {loading && (
          <span className="ml-auto flex items-center gap-1.5 text-xs text-slate-500">
            <Loader2 size={12} className="animate-spin" /> Scoring…
          </span>
        )}
        {scores && onRequestScore && (
          <button
            onClick={onRequestScore}
            disabled={loading}
            className="ml-2 p-1 rounded text-slate-600 hover:text-slate-400 transition-colors"
            title="Re-run QA score"
          >
            <RefreshCw size={12} />
          </button>
        )}
      </div>

      <div className="p-4 space-y-4">
        {/* Overall summary */}
        {scores?.overall_summary && (
          <p className="text-xs text-slate-400 leading-relaxed border-b border-slate-800 pb-4">
            {scores.overall_summary}
          </p>
        )}

        {!scores && !loading && (
          <p className="text-xs text-slate-600 italic">
            Click "Run QA Score" to evaluate this conversation with the Quality Scoring Agent.
          </p>
        )}

        {/* Dimension bars */}
        {DIMENSIONS.map((dim) => {
          const dimension = scores?.[dim.key];
          const pct = dimension ? Math.round(dimension.score * 100) : null;
          const { bar, text } = scoreColor(pct);

          return (
            <div key={dim.key} className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-300 font-medium">{dim.label}</span>
                <span className={`font-semibold tabular-nums ${pct === null ? 'text-slate-600' : text}`}>
                  {pct !== null ? `${pct}%` : '—'}
                </span>
              </div>
              <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${bar}`}
                  style={{ width: pct !== null ? `${pct}%` : '0%' }}
                />
              </div>
              {dimension?.reasoning && (
                <p className="text-xs text-slate-600 italic">{dimension.reasoning}</p>
              )}
              {!dimension && (
                <p className="text-xs text-slate-700">{dim.description}</p>
              )}
            </div>
          );
        })}

        {scores && (
          <p className="text-xs text-slate-700 pt-1">
            Scored by {scores.model} · {scores.latency_ms}ms
          </p>
        )}
      </div>
    </div>
  );
}

