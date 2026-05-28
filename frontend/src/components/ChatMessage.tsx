import { Bot, User, AlertTriangle, Clock } from 'lucide-react';
import type { LiveChatMessage } from '../types';
import { IntentBadge } from './IntentBadge';

interface ChatMessageProps {
  message: LiveChatMessage;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full
        ${isUser ? 'bg-indigo-600' : 'bg-slate-700'}`}>
        {isUser ? <User size={13} className="text-white" /> : <Bot size={13} className="text-slate-300" />}
      </div>

      {/* Bubble */}
      <div className={`max-w-[75%] space-y-1.5 ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
        <div className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed
          ${isUser
            ? 'bg-indigo-600 text-white rounded-tr-sm'
            : 'bg-slate-800 text-slate-200 rounded-tl-sm border border-slate-700'}`}>
          {message.content}
        </div>

        {/* Agent metadata row */}
        {!isUser && (message.intent || message.should_escalate || message.latency_ms) && (
          <div className="flex flex-wrap items-center gap-1.5 px-1">
            {message.agent_name && (
              <span className="text-xs text-slate-600">{message.agent_name}</span>
            )}
            {message.intent && <IntentBadge intent={message.intent} />}
            {message.should_escalate && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs border bg-rose-500/20 text-rose-300 border-rose-500/30">
                <AlertTriangle size={9} /> Escalate
              </span>
            )}
            {message.latency_ms !== undefined && (
              <span className="flex items-center gap-1 text-xs text-slate-600">
                <Clock size={10} />{message.latency_ms}ms
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
