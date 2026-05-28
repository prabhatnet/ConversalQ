import { Tag } from 'lucide-react';

interface MetadataPanelProps {
  metadata: Record<string, unknown>;
  callId?: string;
  channel?: string;
  category?: string;
  timestamp?: string;
}

const SENTIMENT_STYLES: Record<string, string> = {
  positive: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  neutral:  'bg-slate-500/20 text-slate-300 border-slate-500/30',
  negative: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
};

// Fields handled separately as top-level badges
const BADGE_KEYS = new Set(['resolved', 'escalated', 'sentiment', 'issue_type']);

function formatKey(k: string) {
  return k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatValue(v: unknown): string {
  if (typeof v === 'boolean') return v ? 'Yes' : 'No';
  if (v === null || v === undefined) return '—';
  return String(v);
}

export function MetadataPanel({ metadata, callId, channel, category, timestamp }: MetadataPanelProps) {
  const sentiment = metadata.sentiment as string | undefined;
  const resolved  = metadata.resolved  as boolean | undefined;
  const escalated = metadata.escalated as boolean | undefined;
  const issueType = metadata.issue_type as string | undefined;

  // Remaining fields not shown as badges
  const extras = Object.entries(metadata).filter(([k]) => !BADGE_KEYS.has(k));

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-800">
        <Tag size={15} className="text-indigo-400" />
        <h2 className="text-sm font-semibold text-slate-200">Tags &amp; Highlights</h2>
      </div>

      <div className="p-4 space-y-4">
        {/* Badge row */}
        <div className="flex flex-wrap gap-2">
          {sentiment && (
            <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border capitalize ${SENTIMENT_STYLES[sentiment] ?? SENTIMENT_STYLES.neutral}`}>
              {sentiment} sentiment
            </span>
          )}
          {resolved !== undefined && (
            <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${resolved ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' : 'bg-amber-500/20 text-amber-300 border-amber-500/30'}`}>
              {resolved ? 'Resolved' : 'Unresolved'}
            </span>
          )}
          {escalated && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border bg-rose-500/20 text-rose-300 border-rose-500/30">
              Escalated
            </span>
          )}
          {issueType && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border bg-violet-500/20 text-violet-300 border-violet-500/30 capitalize">
              {issueType.replace(/_/g, ' ')}
            </span>
          )}
          {channel && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border border-slate-600 text-slate-400 capitalize">
              {channel}
            </span>
          )}
          {category && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border border-slate-600 text-slate-400 capitalize">
              {category}
            </span>
          )}
        </div>

        {/* Key-value table for remaining metadata */}
        {extras.length > 0 && (
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
            {extras.map(([k, v]) => (
              <div key={k} className="flex justify-between gap-2 text-xs border-b border-slate-800 pb-2">
                <dt className="text-slate-500 shrink-0">{formatKey(k)}</dt>
                <dd className="text-slate-300 text-right truncate">{formatValue(v)}</dd>
              </div>
            ))}
            {callId && (
              <div className="flex justify-between gap-2 text-xs border-b border-slate-800 pb-2">
                <dt className="text-slate-500 shrink-0">Call ID</dt>
                <dd className="text-slate-300 text-right font-mono">{callId}</dd>
              </div>
            )}
            {timestamp && (
              <div className="flex justify-between gap-2 text-xs border-b border-slate-800 pb-2">
                <dt className="text-slate-500 shrink-0">Timestamp</dt>
                <dd className="text-slate-300 text-right">{new Date(timestamp).toLocaleString()}</dd>
              </div>
            )}
          </dl>
        )}
      </div>
    </div>
  );
}
