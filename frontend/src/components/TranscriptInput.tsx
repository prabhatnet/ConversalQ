import { useState, useRef } from 'react';
import { UploadCloud, FileJson, ClipboardPaste, AlertCircle } from 'lucide-react';
import type { TranscriptFile } from '../types';

interface TranscriptInputProps {
  onTranscript: (t: TranscriptFile) => void;
  loading: boolean;
}

export function TranscriptInput({ onTranscript, loading }: TranscriptInputProps) {
  const [mode, setMode] = useState<'upload' | 'paste'>('upload');
  const [pasteValue, setPasteValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function parseJSON(raw: string): TranscriptFile | null {
    try {
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed.transcript)) throw new Error('Missing "transcript" array.');
      return parsed as TranscriptFile;
    } catch (e) {
      setError((e as Error).message);
      return null;
    }
  }

  function handleFile(file: File) {
    setError(null);
    const reader = new FileReader();
    reader.onload = (e) => {
      const t = parseJSON(e.target?.result as string);
      if (t) onTranscript(t);
    };
    reader.readAsText(file);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  function handlePasteSubmit() {
    setError(null);
    const t = parseJSON(pasteValue);
    if (t) onTranscript(t);
  }

  return (
    <div className="space-y-4">
      {/* Mode toggle */}
      <div className="flex rounded-lg border border-slate-700 overflow-hidden w-fit">
        {(['upload', 'paste'] as const).map((m) => (
          <button
            key={m}
            onClick={() => { setMode(m); setError(null); }}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              mode === m ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            {m === 'upload' ? <span className="flex items-center gap-1.5"><UploadCloud size={14} />Upload file</span>
                            : <span className="flex items-center gap-1.5"><ClipboardPaste size={14} />Paste JSON</span>}
          </button>
        ))}
      </div>

      {mode === 'upload' ? (
        <div
          onDrop={handleDrop}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onClick={() => fileInputRef.current?.click()}
          className={`flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-12 cursor-pointer transition-colors
            ${dragOver ? 'border-indigo-500 bg-indigo-500/10' : 'border-slate-700 bg-slate-900 hover:border-slate-500'}`}
        >
          <FileJson size={36} className="text-slate-500" />
          <div className="text-center">
            <p className="text-sm font-medium text-slate-300">Drop a transcript JSON file here</p>
            <p className="text-xs text-slate-500 mt-1">or click to browse</p>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
        </div>
      ) : (
        <div className="space-y-3">
          <textarea
            value={pasteValue}
            onChange={(e) => setPasteValue(e.target.value)}
            placeholder='{ "call_id": "CALL_001", "transcript": [...] }'
            rows={12}
            className="w-full rounded-xl border border-slate-700 bg-slate-900 text-slate-200 text-xs font-mono p-4 resize-y focus:outline-none focus:ring-2 focus:ring-indigo-500 placeholder:text-slate-600"
          />
          <button
            onClick={handlePasteSubmit}
            disabled={!pasteValue.trim() || loading}
            className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-sm font-medium text-white transition-colors"
          >
            Run Replay
          </button>
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
