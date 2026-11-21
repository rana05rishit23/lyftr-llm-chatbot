import type { ChatMetadata, HealthInfo } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function fetchHealth(): Promise<HealthInfo | null> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error("Health check error:", err);
    return null;
  }
}

export async function sendChatMessage(
  sessionId: string,
  message: string,
  systemPrompt?: string,
  simulateFailureHeader?: string
): Promise<{ reply: string; metadata: ChatMetadata }> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (simulateFailureHeader) {
    headers["X-Simulate-Failure"] = simulateFailureHeader;
  }

  const payload: { session_id: string; message: string; system_prompt?: string } = {
    session_id: sessionId,
    message,
  };
  if (systemPrompt && systemPrompt.trim()) {
    payload.system_prompt = systemPrompt.trim();
  }

  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    try {
      const errorJson = await res.json();
      if (typeof errorJson.detail === "string") {
        errorDetail = errorJson.detail;
      } else if (Array.isArray(errorJson.detail)) {
        errorDetail = errorJson.detail.map((e: any) => e.msg || JSON.stringify(e)).join(", ");
      } else if (errorJson.detail) {
        errorDetail = JSON.stringify(errorJson.detail);
      }
    } catch (_) {
      // ignore
    }
    throw new Error(errorDetail);
  }

  const data = await res.json();
  return {
    reply: data.reply,
    metadata: data.metadata,
  };
}

export async function fetchSessionHistory(sessionId: string) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/messages`);
  if (!res.ok) {
    throw new Error(`Failed to fetch history: ${res.status}`);
  }
  return await res.json();
}
