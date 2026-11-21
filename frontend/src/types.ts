export interface ChatMetadata {
  resolution_source: "LIVE_INFERENCE" | "LLM_CACHE";
  model: string;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  key_id?: string | null;
  fallback_attempts: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "error";
  content: string;
  metadata?: ChatMetadata;
}

export interface HealthInfo {
  status: string;
  keys_configured: number;
  cache_enabled: boolean;
}
