import { useState } from "react";
import { Loader2, RotateCcw, FileSearch, MessageSquare } from "lucide-react";
import { TranscriptInput } from "./components/TranscriptInput";
import { ReplayResults } from "./components/ReplayResults";
import { LiveChat } from "./components/LiveChat";
import { replayTranscript, fetchSummary } from "./api/client";
import type { TranscriptFile, TranscriptReplayResponse, ConversationSummaryResponse } from "./types";

type Tab = "replay" | "chat";

export default function App() {
  const [tab, setTab] = useState<Tab>("replay");

  // Replay state
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TranscriptReplayResponse | null>(null);
  const [callMeta, setCallMeta] = useState<TranscriptFile | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Summary state
  const [summary, setSummary] = useState<ConversationSummaryResponse | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);

  async function handleTranscript(file: TranscriptFile) {
    setError(null);
    setResult(null);
    setSummary(null);
    setCallMeta(file);
    setLoading(true);
    try {
      const res = await replayTranscript(file);
      setResult(res);
      // Fetch summary in background after replay completes
      setSummaryLoading(true);
      try {
        const sum = await fetchSummary(res.conversation_id);
        setSummary(sum);
      } catch {
        // Summary fetch failing is non-critical
      } finally {
        setSummaryLoading(false);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setResult(null);
    setCallMeta(null);
    setSummary(null);
    setError(null);
  }

  const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "replay", label: "Transcript Replay", icon: <FileSearch size={14} /> },
    { id: "chat",   label: "Live Chat",          icon: <MessageSquare size={14} /> },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-sm">CQ</div>
            <div>
              <span className="text-sm font-semibold text-slate-100">ConversalQ</span>
              <span className="ml-2 text-xs text-slate-500">AI Call Center Assistant</span>
            </div>
          </div>
          {result && tab === "replay" && (
            <button
              onClick={reset}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 transition-colors"
            >
              <RotateCcw size={12} /> New replay
            </button>
          )}
        </div>

        {/* Tab bar */}
        <div className="max-w-5xl mx-auto px-6 flex gap-1 -mb-px">
          {TABS.map(({ id, label, icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors
                ${tab === id
                  ? "border-indigo-500 text-indigo-300"
                  : "border-transparent text-slate-500 hover:text-slate-300"}`}
            >
              {icon}{label}
            </button>
          ))}
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 max-w-5xl mx-auto w-full px-6 py-8">

        {/* ── Transcript Replay tab ── */}
        {tab === "replay" && (
          <div className="space-y-6">
            {!result && !loading && (
              <>
                <div>
                  <h1 className="text-2xl font-bold text-slate-100">Transcript Replay</h1>
                  <p className="text-sm text-slate-400 mt-1">
                    Upload a call transcript JSON to replay it through the multi-agent system. View routing, intent classification, LLM summary, QA scores, and more.
                  </p>
                </div>
                <TranscriptInput onTranscript={handleTranscript} loading={loading} />
                {error && (
                  <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
                    {error}
                  </div>
                )}
              </>
            )}

            {loading && (
              <div className="flex flex-col items-center justify-center py-24 gap-4">
                <Loader2 size={32} className="animate-spin text-indigo-400" />
                <p className="text-sm text-slate-400">Replaying transcript through agents...</p>
              </div>
            )}

            {result && !loading && (
              <ReplayResults
                result={result}
                callMeta={callMeta ?? undefined}
                summary={summary}
                summaryLoading={summaryLoading}
              />
            )}
          </div>
        )}

        {/* ── Live Chat tab ── */}
        {tab === "chat" && <LiveChat />}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 py-4 text-center text-xs text-slate-600">
        ConversalQ - Powered by LangGraph + GPT-4o
      </footer>
    </div>
  );
}
