export interface TranscriptTurn {
  speaker: 'agent' | 'customer' | string;
  text: string;
  timestamp_offset?: number;
}

export interface TranscriptFile {
  call_id?: string;
  timestamp?: string;
  duration_seconds?: number;
  channel?: string;
  category?: string;
  transcript: TranscriptTurn[];
  metadata?: Record<string, unknown>;
}

export interface ReplayTurnResult {
  turn_index: number;
  customer_text: string;
  agent_response: string;
  intent: string | null;
  agent_name: string | null;
  confidence: number | null;
  should_escalate: boolean;
  latency_ms: number;
}

export interface TranscriptReplayResponse {
  call_id: string | null;
  conversation_id: string;
  total_turns: number;
  customer_turns_replayed: number;
  turns: ReplayTurnResult[];
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
}

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  response: string;
  model: string;
  intent: string | null;
  agent_name: string | null;
  confidence: number | null;
  should_escalate: boolean;
  latency_ms: number;
}

export interface ConversationSummaryResponse {
  conversation_id: string;
  status: string;
  total_turns: number;
  has_summary: boolean;
  summary: string | null;
}

export interface DimensionScore {
  score: number;
  reasoning: string;
}

export interface QAScoreResponse {
  conversation_id: string;
  overall_score: number;
  empathy: DimensionScore;
  tone: DimensionScore;
  resolution: DimensionScore;
  professionalism: DimensionScore;
  overall_summary: string;
  model: string;
  latency_ms: number;
}

export interface LiveChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  intent?: string | null;
  agent_name?: string | null;
  confidence?: number | null;
  should_escalate?: boolean;
  latency_ms?: number;
}

export interface WordTimestamp {
  word: string;
  start: number;
  end: number;
  confidence: number;
}

export interface AudioTranscriptionResponse {
  transcript: string;
  confidence: number;
  duration_seconds: number;
  words: WordTimestamp[];
  filename: string;
  content_type: string;
  stt_available: boolean;
}

