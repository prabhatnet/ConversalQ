export const INTENT_META: Record<string, { label: string; pill: string; bar: string }> = {
  billing:    { label: 'Billing',     pill: 'bg-amber-500/20 text-amber-300 border-amber-500/30',    bar: 'bg-amber-400' },
  technical:  { label: 'Technical',   pill: 'bg-blue-500/20 text-blue-300 border-blue-500/30',       bar: 'bg-blue-400' },
  account:    { label: 'Account',     pill: 'bg-violet-500/20 text-violet-300 border-violet-500/30', bar: 'bg-violet-400' },
  general:    { label: 'General',     pill: 'bg-slate-500/20 text-slate-300 border-slate-500/30',    bar: 'bg-slate-400' },
  escalation: { label: 'Escalation',  pill: 'bg-rose-500/20 text-rose-300 border-rose-500/30',       bar: 'bg-rose-400' },
};

interface IntentBadgeProps {
  intent: string | null;
}

export function IntentBadge({ intent }: IntentBadgeProps) {
  if (!intent) return null;
  const meta = INTENT_META[intent] ?? INTENT_META['general'];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${meta.pill}`}>
      {meta.label}
    </span>
  );
}
