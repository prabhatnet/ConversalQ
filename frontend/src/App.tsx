import { useState } from "react";
import { Loader2, RotateCcw } from "lucide-react";
import { TranscriptInput } from "./components/TranscriptInput";
import { ReplayResults } from "./components/ReplayResults";
import { replayTranscript } from "./api/client";
import type { TranscriptFile, TranscriptReplayResponse } from "./types";

export default function App() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TranscriptReplayResponse | null>(null);
  const [callMeta, setCallMeta] = useState<TranscriptFile | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleTranscript(file: TranscriptFile) {
    setError(null);
    setResult(null);
    setCallMeta(file);
    setLoading(true);
    try {
      const res = await replayTranscript(file);
      setResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setResult(null);
    setCallMeta(null);
    setError(null);
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-sm">CQ</div>
            <div>
              <span className="text-sm font-semibold text-slate-100">ConversalQ</span>
              <span className="ml-2 text-xs text-slate-500">AI Call Center Assistant</span>
            </div>
          </div>
          {result && (
            <button
              onClick={reset}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 transition-colors"
            >
              <RotateCcw size={12} /> New replay
            </button>
          )}
        </div>
      </header>

      <main className="flex-1 max-w-5xl mx-auto w-full px-6 py-8 space-y-8">
        {!result && !loading && (
          <div className="space-y-6">
            <div>
              <h1 className="text-2xl font-bold text-slate-100">Transcript Replay</h1>
              <p className="text-sm text-slate-400 mt-1">
                Upload a call transcript JSON file to replay it through the multi-agent system and analyse routing, intent, and responses.
              </p>
            </div>
            <TranscriptInput onTranscript={handleTranscript} loading={loading} />
            {error && (
              <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
                {error}
              </div>
            )}
          </div>
        )}

        {loading && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <Loader2 size={32} className="animate-spin text-indigo-400" />
            <p className="text-sm text-slate-400">Replaying transcript through agents...</p>
          </div>
        )}

        {result && !loading && (
          <ReplayResults result={result} callMeta={callMeta ?? undefined} />
        )}
      </main>

      <footer className="border-t border-slate-800 py-4 text-center text-xs text-slate-600">
        ConversalQ - Powered by LangGraph + GPT-4o
      </footer>
    </div>
  );
}
