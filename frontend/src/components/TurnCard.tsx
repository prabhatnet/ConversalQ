import { User, Bot, Clock, AlertTriangle } from 'lucide-react';
import type { ReplayTurnResult } from '../types';
import { IntentBadge } from './IntentBadge';
import { ConfidenceBar } from './ConfidenceBar';

interface TurnCardProps {
  turn: ReplayTurnResult;
  index: number;
}

export function TurnCard({ turn, index }: TurnCardProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
      {/* Customer turn */}
      <div className="flex gap-3 p-4 border-b border-slate-800">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-700">
          <User size={14} className="text-slate-300" />
        </div>
        <div className="flex-1 space-y-1">
          <span className="text-xs font-medium text-slate-400">Customer · turn {index + 1}</span>
          <p className="text-sm text-slate-200">{turn.customer_text}</p>
        </div>
      </div>

      {/* Agent turn */}
      <div className="flex gap-3 p-4 bg-slate-900/60">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-600/30">
          <Bot size={14} className="text-indigo-300" />
        </div>
        <div className="flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-slate-400">
              {turn.agent_name ?? 'Agent'}
            </span>
            <IntentBadge intent={turn.intent} />
            {turn.should_escalate && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border bg-rose-500/20 text-rose-300 border-rose-500/30">
                <AlertTriangle size={10} /> Escalate
              </span>
            )}
          </div>
          <p className="text-sm text-slate-200 whitespace-pre-wrap">{turn.agent_response}</p>
          <div className="space-y-1.5 pt-1">
            <ConfidenceBar intent={turn.intent} confidence={turn.confidence} />
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Clock size={11} />
              <span>{turn.latency_ms} ms</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
