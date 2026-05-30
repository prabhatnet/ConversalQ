import { useRef, useState, type DragEvent, type ChangeEvent } from "react";
import { Upload, Mic, AlertCircle, CheckCircle2, Clock, BarChart2 } from "lucide-react";
import { uploadAudio } from "../api/client";
import type { AudioTranscriptionResponse } from "../types";

const ACCEPTED = ".wav,.mp3,.mp4,.m4a,.ogg,.webm,.flac,.aac";
const MAX_MB = 25;

export function AudioUpload() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AudioTranscriptionResponse | null>(null);

  async function process(file: File) {    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`File is too large. Maximum size is ${MAX_MB} MB.`);
      return;
    }
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const res = await uploadAudio(file);
      setResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) process(file);
    e.target.value = "";
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) process(file);
  }

  return (
    <div className="space-y-6">
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={[
          "relative flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed cursor-pointer transition-colors select-none",
          "py-14 px-8 text-center",
          dragging
            ? "border-indigo-500 bg-indigo-950/40"
            : "border-slate-700 bg-slate-900/50 hover:border-slate-500 hover:bg-slate-900",
        ].join(" ")}
      >
        <input ref={inputRef} type="file" accept={ACCEPTED} className="hidden" onChange={onFileChange} />
        {loading ? (
          <>
            <Mic size={36} className="text-indigo-400 animate-pulse" />
            <p className="text-sm text-slate-300 font-medium">Transcribing…</p>
            <p className="text-xs text-slate-500">Deepgram Nova-2 is processing your file</p>
          </>
        ) : (
          <>
            <Upload size={36} className={dragging ? "text-indigo-400" : "text-slate-500"} />
            <div>
              <p className="text-sm font-medium text-slate-200">Drop an audio file or click to browse</p>
              <p className="mt-1 text-xs text-slate-500">WAV · MP3 · MP4 · M4A · OGG · WEBM · FLAC · AAC — up to {MAX_MB} MB</p>
            </div>
          </>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-rose-800 bg-rose-950/40 px-4 py-3 text-sm text-rose-300">
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="rounded-2xl border border-slate-700 bg-slate-900 overflow-hidden">
          {/* Header row */}
          <div className="flex items-center justify-between border-b border-slate-800 px-5 py-3">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-200">
              <CheckCircle2 size={15} className="text-emerald-400" />
              <span className="truncate max-w-xs">{result.filename}</span>
            </div>
            <div className="flex items-center gap-4 text-xs text-slate-400">
              <span className="flex items-center gap-1">
                <Clock size={12} />
                {result.duration_seconds.toFixed(1)}s
              </span>
              <span className="flex items-center gap-1">
                <BarChart2 size={12} />
                {Math.round(result.confidence * 100)}% confidence
              </span>
              {!result.stt_available && (
                <span className="rounded-full bg-amber-900/50 border border-amber-700 px-2 py-0.5 text-amber-300 text-xs">
                  STT unavailable — set DEEPGRAM_API_KEY
                </span>
              )}
            </div>
          </div>

          {/* Transcript */}
          <div className="px-5 py-4">
            {result.transcript ? (
              <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{result.transcript}</p>
            ) : (
              <p className="text-sm text-slate-500 italic">
                {result.stt_available
                  ? "No speech detected in audio."
                  : "Transcription skipped — DEEPGRAM_API_KEY not configured."}
              </p>
            )}
          </div>

          {/* Word timestamps */}
          {result.words.length > 0 && (
            <details className="border-t border-slate-800">
              <summary className="cursor-pointer px-5 py-2 text-xs text-slate-500 hover:text-slate-300 select-none">
                {result.words.length} word timestamps
              </summary>
              <div className="flex flex-wrap gap-1.5 px-5 pb-4 pt-2">
                {result.words.map((w, i) => (
                  <span
                    key={i}
                    title={`${w.start.toFixed(2)}s – ${w.end.toFixed(2)}s  (${Math.round(w.confidence * 100)}%)`}
                    className="rounded-md bg-slate-800 px-2 py-0.5 text-xs text-slate-300 cursor-default"
                  >
                    {w.word}
                  </span>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
