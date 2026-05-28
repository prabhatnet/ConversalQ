import { FileText, Loader2, Info } from 'lucide-react';
import type { ConversationSummaryResponse } from '../types';

interface SummaryPanelProps {
  summary: ConversationSummaryResponse | null;
  loading: boolean;
}

export function SummaryPanel({ summary, loading }: SummaryPanelProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-800">
        <FileText size={15} className="text-indigo-400" />
        <h2 className="text-sm font-semibold text-slate-200">Conversation Summary</h2>
        {summary && (
          <span className="ml-auto text-xs text-slate-500">{summary.total_turns} turns · {summary.status}</span>
        )}
      </div>

      <div className="p-4">
        {loading && (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <Loader2 size={14} className="animate-spin" />
            Generating summary…
          </div>
        )}

        {!loading && summary?.has_summary && summary.summary && (
          <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{summary.summary}</p>
        )}

        {!loading && summary && !summary.has_summary && (
          <div className="flex items-start gap-2 text-sm text-slate-500">
            <Info size={14} className="mt-0.5 shrink-0 text-slate-600" />
            <span>
              Summary is generated after 10+ conversation turns. This call had {summary.total_turns} turn{summary.total_turns !== 1 ? 's' : ''}.
            </span>
          </div>
        )}

        {!loading && !summary && (
          <p className="text-sm text-slate-600 italic">No summary available.</p>
        )}
      </div>
    </div>
  );
}
