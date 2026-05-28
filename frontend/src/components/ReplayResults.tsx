import { CheckCircle2, XCircle, Hash, MessageSquare, Zap } from 'lucide-react';
import type { TranscriptReplayResponse } from '../types';
import { TurnCard } from './TurnCard';
import { IntentBadge } from './IntentBadge';

interface ReplayResultsProps {
  result: TranscriptReplayResponse;
  callMeta?: { category?: string; duration_seconds?: number; channel?: string };
}

export function ReplayResults({ result, callMeta }: ReplayResultsProps) {
  const escalated = result.turns.some((t) => t.should_escalate);
  const avgLatency = result.turns.length
    ? Math.round(result.turns.reduce((s, t) => s + t.latency_ms, 0) / result.turns.length)
    : 0;

  // Dominant intent
  const intentCounts: Record<string, number> = {};
  for (const t of result.turns) {
    if (t.intent) intentCounts[t.intent] = (intentCounts[t.intent] ?? 0) + 1;
  }
  const dominantIntent = Object.entries(intentCounts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;

  return (
    <div className="space-y-6">
      {/* Summary bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard icon={<Hash size={16} />} label="Call ID" value={result.call_id ?? '—'} />
        <StatCard icon={<MessageSquare size={16} />} label="Customer turns" value={String(result.customer_turns_replayed)} />
        <StatCard icon={<Zap size={16} />} label="Avg latency" value={`${avgLatency} ms`} />
        <StatCard
          icon={escalated ? <XCircle size={16} className="text-rose-400" /> : <CheckCircle2 size={16} className="text-emerald-400" />}
          label="Outcome"
          value={escalated ? 'Escalated' : 'Resolved'}
          valueClass={escalated ? 'text-rose-300' : 'text-emerald-300'}
        />
      </div>

      {/* Tags row */}
      <div className="flex flex-wrap items-center gap-2">
        {dominantIntent && <IntentBadge intent={dominantIntent} />}
        {callMeta?.channel && (
          <span className="px-2 py-0.5 rounded-full text-xs font-medium border border-slate-600 text-slate-400">
            {callMeta.channel}
          </span>
        )}
        {callMeta?.duration_seconds && (
          <span className="px-2 py-0.5 rounded-full text-xs font-medium border border-slate-600 text-slate-400">
            {Math.floor(callMeta.duration_seconds / 60)}m {callMeta.duration_seconds % 60}s
          </span>
        )}
        {callMeta?.category && (
          <span className="px-2 py-0.5 rounded-full text-xs font-medium border border-slate-600 text-slate-400 capitalize">
            {callMeta.category}
          </span>
        )}
      </div>

      {/* Turn-by-turn */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Transcript Replay</h2>
        {result.turns.map((turn, i) => (
          <TurnCard key={turn.turn_index} turn={turn} index={i} />
        ))}
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  valueClass = 'text-slate-100',
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4 flex flex-col gap-1">
      <div className="flex items-center gap-1.5 text-slate-500 text-xs">{icon}{label}</div>
      <span className={`text-lg font-semibold truncate ${valueClass}`}>{value}</span>
    </div>
  );
}
