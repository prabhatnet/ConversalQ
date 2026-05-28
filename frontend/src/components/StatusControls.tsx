import { useState } from 'react';
import { CheckCircle2, AlertTriangle, XCircle, Loader2 } from 'lucide-react';
import { updateConversationStatus } from '../api/client';

interface StatusControlsProps {
  conversationId: string;
  currentStatus?: string;
}

const ACTIONS = [
  {
    status: 'resolved',
    label: 'Mark Resolved',
    icon: CheckCircle2,
    style: 'border-emerald-600 text-emerald-300 hover:bg-emerald-600/20',
    activeStyle: 'bg-emerald-600/20 border-emerald-500 text-emerald-300',
  },
  {
    status: 'escalated',
    label: 'Mark Escalated',
    icon: AlertTriangle,
    style: 'border-amber-600 text-amber-300 hover:bg-amber-600/20',
    activeStyle: 'bg-amber-600/20 border-amber-500 text-amber-300',
  },
  {
    status: 'closed',
    label: 'Close',
    icon: XCircle,
    style: 'border-slate-600 text-slate-400 hover:bg-slate-700',
    activeStyle: 'bg-slate-700 border-slate-500 text-slate-300',
  },
] as const;

export function StatusControls({ conversationId, currentStatus }: StatusControlsProps) {
  const [status, setStatus] = useState<string>(currentStatus ?? 'active');
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAction(newStatus: string) {
    if (status === newStatus) return;
    setError(null);
    setLoading(newStatus);
    try {
      await updateConversationStatus(conversationId, newStatus);
      setStatus(newStatus);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-slate-200">Conversation Actions</span>
        <span className="text-xs text-slate-500">
          Status: <span className="text-slate-300 capitalize">{status}</span>
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        {ACTIONS.map(({ status: s, label, icon: Icon, style, activeStyle }) => (
          <button
            key={s}
            onClick={() => handleAction(s)}
            disabled={status === s || loading !== null}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed
              ${status === s ? activeStyle : style}`}
          >
            {loading === s
              ? <Loader2 size={12} className="animate-spin" />
              : <Icon size={12} />}
            {label}
          </button>
        ))}
      </div>

      {error && (
        <p className="text-xs text-rose-400">{error}</p>
      )}
    </div>
  );
}
