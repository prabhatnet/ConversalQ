import { useRef, useState, type DragEvent, type ChangeEvent } from "react";
import { Upload, Mic, AlertCircle } from "lucide-react";
import { uploadAudio } from "../api/client";
import type { AudioTranscriptionResponse } from "../types";

const ACCEPTED = ".wav,.mp3,.mp4,.m4a,.ogg,.webm,.flac,.aac";
const MAX_MB = 25;

interface Props {
  onTranscribed: (result: AudioTranscriptionResponse) => void;
}

export function AudioUpload({ onTranscribed }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function process(file: File) {
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`File is too large. Maximum size is ${MAX_MB} MB.`);
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await uploadAudio(file);
      onTranscribed(res);
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

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-rose-800 bg-rose-950/40 px-4 py-3 text-sm text-rose-300">
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
