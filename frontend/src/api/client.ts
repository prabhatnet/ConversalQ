import type { TranscriptFile, TranscriptReplayResponse, ChatRequest, ChatResponse } from '../types';

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
