import { useState, useRef, useEffect } from 'react';
import { Mic, MicOff, Loader2, VolumeX, RotateCcw, AlertCircle } from 'lucide-react';
import type { LiveChatMessage } from '../types';
import { uploadAudio, sendChatMessage, speakText } from '../api/client';
import { ChatMessage } from './ChatMessage';

type Phase = 'idle' | 'recording' | 'transcribing' | 'thinking' | 'speaking';

export function LiveVoice() {
  const [messages, setMessages] = useState<LiveChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const blobUrlRef = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, phase]);

  useEffect(() => {
    return () => {
      stopStream();
      stopAudio();
    };
  }, []);

  function stopStream() {
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
  }

  function stopAudio() {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
      audioRef.current = null;
    }
    if (blobUrlRef.current) {
      URL.revokeObjectURL(blobUrlRef.current);
      blobUrlRef.current = null;
    }
    window.speechSynthesis?.cancel();
  }

  async function toggleRecording() {
    if (phase === 'recording') {
      mediaRecorderRef.current?.stop();
      stopStream();
      return;
    }
    if (phase !== 'idle') return;

    stopAudio();
    setError(null);

    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Your browser does not support microphone access.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType =
        ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg'].find(t =>
          MediaRecorder.isTypeSupported(t),
        ) ?? '';

      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = e => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => processRecording();
      recorder.start(100);
      setPhase('recording');
    } catch {
      setError('Microphone access denied. Allow microphone access in your browser and try again.');
    }
  }

  async function processRecording() {
    const chunks = chunksRef.current;
    if (!chunks.length) {
      setPhase('idle');
      return;
    }

    const mimeType = chunks[0].type || 'audio/webm';
    const blob = new Blob(chunks, { type: mimeType });
    const file = new File([blob], 'recording.webm', { type: mimeType });

    setPhase('transcribing');
    let transcript = '';
    try {
      const stt = await uploadAudio(file);
      transcript = stt.transcript.trim();
    } catch (e) {
      setError('Transcription failed: ' + (e as Error).message);
      setPhase('idle');
      return;
    }

    if (!transcript) {
      setError('No speech detected — please speak clearly and try again.');
      setPhase('idle');
      return;
    }

    const userMsg: LiveChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: transcript,
    };
    setMessages(prev => [...prev, userMsg]);
    setPhase('thinking');

    try {
      const res = await sendChatMessage({ message: transcript, conversation_id: conversationId });
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
      setMessages(prev => [...prev, assistantMsg]);

      setPhase('speaking');
      await playResponse(res.response);
      setPhase('idle');
    } catch (e) {
      setError((e as Error).message);
      setPhase('idle');
    }
  }

  async function playResponse(text: string) {
    try {
      const buffer = await speakText(text);
      await playMp3(buffer);
    } catch {
      // Fallback to browser TTS if the /speak endpoint is unavailable
      await browserSpeak(text);
    }
  }

  function playMp3(arrayBuffer: ArrayBuffer): Promise<void> {
    return new Promise(resolve => {
      const blob = new Blob([arrayBuffer], { type: 'audio/mpeg' });
      const url = URL.createObjectURL(blob);
      blobUrlRef.current = url;

      const audio = new Audio(url);
      audioRef.current = audio;

      const cleanup = () => {
        URL.revokeObjectURL(url);
        blobUrlRef.current = null;
        audioRef.current = null;
        resolve();
      };
      audio.onended = cleanup;
      audio.onerror = cleanup;
      audio.play().catch(cleanup);
    });
  }

  function browserSpeak(text: string): Promise<void> {
    return new Promise(resolve => {
      if (!window.speechSynthesis) { resolve(); return; }
      window.speechSynthesis.cancel();
      const utt = new SpeechSynthesisUtterance(text);
      utt.onend = () => resolve();
      utt.onerror = () => resolve();
      window.speechSynthesis.speak(utt);
    });
  }

  function stopSpeaking() {
    stopAudio();
    setPhase('idle');
  }

  function handleReset() {
    mediaRecorderRef.current?.stop();
    stopStream();
    stopAudio();
    setMessages([]);
    setConversationId(undefined);
    setPhase('idle');
    setError(null);
  }

  const isBusy = phase === 'transcribing' || phase === 'thinking';

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 shrink-0">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-violet-600/30">
            <Mic size={13} className="text-violet-300" />
          </div>
          <span className="text-sm font-semibold text-slate-200">Live Voice Support</span>
          {phase !== 'idle' && (
            <span className="text-xs text-slate-500 capitalize">{phase}…</span>
          )}
        </div>
        <button
          onClick={handleReset}
          className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
          title="Start new call"
        >
          <RotateCcw size={12} /> New call
        </button>
      </div>

      {/* Message history */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
            <div className="h-16 w-16 rounded-full bg-violet-600/10 border border-violet-800/50 flex items-center justify-center">
              <Mic size={28} className="text-violet-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-300">Voice call ready</p>
              <p className="text-xs text-slate-500 mt-1 max-w-xs">
                Click the microphone button below, speak your question, then click again to send it to the agent
              </p>
            </div>
            <div className="flex flex-col gap-1 text-xs text-slate-600 mt-2">
              <span>STT: Deepgram Nova-2</span>
              <span>TTS: OpenAI tts-1</span>
            </div>
          </div>
        )}

        {messages.map(msg => (
          <ChatMessage key={msg.id} message={msg} />
        ))}

        {(phase === 'transcribing' || phase === 'thinking') && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-slate-800/50 w-fit">
            <Loader2 size={14} className="animate-spin text-violet-400" />
            <span className="text-xs text-slate-400">
              {phase === 'transcribing' ? 'Transcribing your voice…' : 'Agent is thinking…'}
            </span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Error banner */}
      {error && (
        <div className="mx-4 mb-2 flex items-start gap-2 rounded-lg border border-rose-800 bg-rose-950/40 px-3 py-2 text-xs text-rose-300 shrink-0">
          <AlertCircle size={13} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Voice control */}
      <div className="px-4 py-6 border-t border-slate-800 shrink-0 flex flex-col items-center gap-3">
        <button
          onClick={phase === 'speaking' ? stopSpeaking : toggleRecording}
          disabled={isBusy}
          className={[
            'relative h-16 w-16 rounded-full flex items-center justify-center',
            'transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500',
            phase === 'recording'
              ? 'bg-rose-600 hover:bg-rose-700 shadow-lg shadow-rose-900/50'
              : phase === 'speaking'
              ? 'bg-violet-600 hover:bg-violet-700 shadow-lg shadow-violet-900/50'
              : isBusy
              ? 'bg-slate-700 cursor-not-allowed opacity-60'
              : 'bg-violet-600 hover:bg-violet-700 shadow-lg shadow-violet-900/50 hover:scale-105',
          ].join(' ')}
        >
          {/* Pulse ring while recording */}
          {phase === 'recording' && (
            <span className="absolute inset-0 rounded-full bg-rose-500 animate-ping opacity-30" />
          )}
          {/* Pulse ring while speaking */}
          {phase === 'speaking' && (
            <span className="absolute inset-0 rounded-full bg-violet-400 animate-pulse opacity-20" />
          )}

          {isBusy ? (
            <Loader2 size={24} className="text-white animate-spin" />
          ) : phase === 'recording' ? (
            <MicOff size={24} className="text-white" />
          ) : phase === 'speaking' ? (
            <VolumeX size={24} className="text-white" />
          ) : (
            <Mic size={24} className="text-white" />
          )}
        </button>

        <p className="text-xs text-slate-500 select-none">
          {phase === 'idle' && 'Click to start recording'}
          {phase === 'recording' && 'Recording — click to send'}
          {phase === 'transcribing' && 'Transcribing…'}
          {phase === 'thinking' && 'Agent is thinking…'}
          {phase === 'speaking' && 'Agent is speaking — click to stop'}
        </p>
      </div>
    </div>
  );
}
