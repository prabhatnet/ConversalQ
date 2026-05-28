import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, RotateCcw, Bot } from 'lucide-react';
import type { LiveChatMessage } from '../types';
import { sendChatMessage } from '../api/client';
import { ChatMessage } from './ChatMessage';

export function LiveChat() {
  const [messages, setMessages] = useState<LiveChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    setInput('');
    setError(null);

    const userMsg: LiveChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await sendChatMessage({ message: text, conversation_id: conversationId });
      setConversationId(res.conversation_id);

      const assistantMsg: LiveChatMessage = {
        id: res.message_id,
        role: 'assistant',
        content: res.response,
        intent: res.intent,
        agent_name: res.agent_name,
        confidence: res.confidence,
        should_escalate: res.should_escalate,
        latency_ms: res.latency_ms,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e) {
      setError((e as Error).message);
      // Remove the optimistic user message on error
      setMessages((prev) => prev.filter((m) => m.id !== userMsg.id));
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setMessages([]);
    setConversationId(undefined);
    setError(null);
    setInput('');
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 shrink-0">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-600/30">
            <Bot size={13} className="text-indigo-300" />
          </div>
          <span className="text-sm font-semibold text-slate-200">ConversalQ Assistant</span>
          <span className="flex h-2 w-2 rounded-full bg-emerald-400 ml-1" title="Online" />
        </div>
        <div className="flex items-center gap-3">
          {conversationId && (
            <span className="hidden sm:block text-xs text-slate-600 font-mono truncate max-w-[12rem]">
              {conversationId}
            </span>
          )}
          {messages.length > 0 && (
            <button
              onClick={handleReset}
              className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
              title="Start new conversation"
            >
              <RotateCcw size={12} /> New
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
            <div className="h-12 w-12 rounded-full bg-indigo-600/20 flex items-center justify-center">
              <Bot size={22} className="text-indigo-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-300">How can I help you today?</p>
              <p className="text-xs text-slate-600 mt-1">Ask about billing, technical issues, your account, or anything else.</p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 mt-2">
              {['I have a billing question', 'I need technical support', 'Help me reset my password'].map((s) => (
                <button
                  key={s}
                  onClick={() => { setInput(s); }}
                  className="px-3 py-1.5 rounded-full border border-slate-700 bg-slate-800 hover:bg-slate-700 text-xs text-slate-400 hover:text-slate-200 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-700">
              <Bot size={13} className="text-slate-300" />
            </div>
            <div className="rounded-2xl rounded-tl-sm bg-slate-800 border border-slate-700 px-4 py-3">
              <Loader2 size={14} className="animate-spin text-slate-500" />
            </div>
          </div>
        )}

        {error && (
          <p className="text-xs text-rose-400 text-center">{error}</p>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 border-t border-slate-800 px-4 py-3">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message… (Enter to send, Shift+Enter for newline)"
            rows={1}
            className="flex-1 resize-none rounded-xl border border-slate-700 bg-slate-800 text-sm text-slate-200 placeholder:text-slate-600 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500 max-h-32 overflow-y-auto"
            style={{ fieldSizing: 'content' } as React.CSSProperties}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <Send size={15} className="text-white" />
          </button>
        </div>
      </div>
    </div>
  );
}
