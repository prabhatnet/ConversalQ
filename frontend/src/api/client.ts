import type { TranscriptFile, TranscriptReplayResponse, ChatRequest, ChatResponse, ConversationSummaryResponse, QAScoreResponse, AudioTranscriptionResponse } from '../types';

const BASE = '/api/v1';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function replayTranscript(file: TranscriptFile): Promise<TranscriptReplayResponse> {
  const res = await fetch(`${BASE}/chat/replay`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      call_id: file.call_id ?? null,
      transcript: file.transcript,
    }),
  });
  return handleResponse<TranscriptReplayResponse>(res);
}

export async function sendChatMessage(req: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  return handleResponse<ChatResponse>(res);
}

export async function fetchSummary(conversationId: string): Promise<ConversationSummaryResponse> {
  const res = await fetch(`${BASE}/chat/${conversationId}/summary`);
  return handleResponse<ConversationSummaryResponse>(res);
}

export async function updateConversationStatus(
  conversationId: string,
  status: string,
): Promise<{ conversation_id: string; status: string }> {
  const res = await fetch(`${BASE}/chat/${conversationId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  return handleResponse<{ conversation_id: string; status: string }>(res);
}

export async function fetchQAScore(conversationId: string, notes?: string): Promise<QAScoreResponse> {
  const res = await fetch(`${BASE}/chat/${conversationId}/qa-score`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes: notes ?? null }),
  });
  return handleResponse<QAScoreResponse>(res);
}

export async function uploadAudio(file: File): Promise<AudioTranscriptionResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE}/voice/upload`, { method: 'POST', body: form });
  return handleResponse<AudioTranscriptionResponse>(res);
}

