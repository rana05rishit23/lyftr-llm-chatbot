import React, { useState, useEffect, useRef } from "react";
import type { ChatMessage, HealthInfo } from "./types";
import { fetchHealth, sendChatMessage } from "./api";
import {
  Send,
  Zap,
  Database,
  ShieldAlert,
  Settings,
  RefreshCw,
  AlertTriangle,
  Bot,
  User,
  Activity,
  Cpu,
} from "lucide-react";
import "./App.css";

// Generate a random unique session id for each page load: e.g. "s-7f3a9b1c"
function generateSessionId(): string {
  return "s-" + Math.random().toString(36).substring(2, 10);
}

export default function App() {
  const [sessionId] = useState<string>(generateSessionId);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState<string>("");
  const [systemPrompt, setSystemPrompt] = useState<string>("");
  const [showSystemPrompt, setShowSystemPrompt] = useState<boolean>(false);
  const [simulateFailure, setSimulateFailure] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [health, setHealth] = useState<HealthInfo | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Poll health on mount
  useEffect(() => {
    fetchHealth().then((h) => setHealth(h));
  }, []);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = inputMessage.trim();
    if (!trimmed || loading) return;

    // Add user message to UI
    const userMsg: ChatMessage = {
      id: "usr-" + Date.now(),
      role: "user",
      content: trimmed,
    };
    setMessages((prev) => [...prev, userMsg]);

    // Clear input immediately as required by spec ("Empty after sending")
    setInputMessage("");
    setLoading(true);

    try {
      const result = await sendChatMessage(
        sessionId,
        trimmed,
        systemPrompt || undefined,
        simulateFailure || undefined
      );

      const assistantMsg: ChatMessage = {
        id: "ast-" + Date.now(),
        role: "assistant",
        content: result.reply,
        metadata: result.metadata,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      // Readable error message in chat, never a blank screen
      const errorMsg: ChatMessage = {
        id: "err-" + Date.now(),
        role: "error",
        content: err.message || "An unexpected error occurred.",
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const resetSession = () => {
    window.location.reload();
  };

  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="app-header">
        <div className="header-left">
          <div className="logo-badge">
            <Bot size={22} className="logo-icon" />
            <span className="logo-title">Lyftr LLM Gateway</span>
          </div>
          <span className="session-tag" title="Session ID">
            {sessionId}
          </span>
        </div>

        <div className="header-right">
          {health && (
            <div className="health-badges">
              <span className="pill pill-green" title="Keys in pool">
                <ShieldAlert size={14} />
                {health.keys_configured} Keys
              </span>
              <span className="pill pill-blue" title="LiteLLM Caching">
                <Database size={14} />
                Cache Active
              </span>
            </div>
          )}

          <button
            type="button"
            className={`icon-btn ${showSystemPrompt ? "active" : ""}`}
            onClick={() => setShowSystemPrompt(!showSystemPrompt)}
            title="Configure System Prompt"
          >
            <Settings size={18} />
          </button>

          <button
            type="button"
            className="icon-btn"
            onClick={resetSession}
            title="Start New Session"
          >
            <RefreshCw size={18} />
          </button>
        </div>
      </header>

      {/* Optional System Prompt Field */}
      {showSystemPrompt && (
        <div className="system-prompt-drawer">
          <label className="drawer-label">
            System Prompt Override:
            <input
              type="text"
              data-testid="system-prompt-input"
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="e.g. You are a pirate who explains concepts in rhyme."
              className="system-prompt-field"
            />
          </label>
        </div>
      )}

      {/* Failure Simulation Banner / Toggle for Demo */}
      <div className="simulation-toolbar">
        <span className="sim-label">
          <Activity size={14} /> Failover Hook:
        </span>
        <button
          type="button"
          className={`sim-chip ${simulateFailure === "" ? "selected" : ""}`}
          onClick={() => setSimulateFailure("")}
        >
          Normal (Auto)
        </button>
        <button
          type="button"
          className={`sim-chip ${simulateFailure === "key_1=429" ? "selected" : ""}`}
          onClick={() => setSimulateFailure("key_1=429")}
          title="Simulate Rate Limit on key_1 -> fails over to key_2"
        >
          Simulate key_1=429
        </button>
        <button
          type="button"
          className={`sim-chip ${simulateFailure === "key_1=500" ? "selected" : ""}`}
          onClick={() => setSimulateFailure("key_1=500")}
          title="Simulate 500 error on key_1 -> fails over to key_2"
        >
          Simulate key_1=500
        </button>
        <button
          type="button"
          className={`sim-chip ${simulateFailure === "*=429" ? "selected" : ""}`}
          onClick={() => setSimulateFailure("*=429")}
          title="Simulate all keys failing -> returns clean 503"
        >
          Simulate *=429 (503)
        </button>
      </div>

      {/* Chat Messages Area */}
      <main className="chat-area">
        {messages.length === 0 ? (
          <div className="empty-state">
            <Bot size={48} className="empty-icon" />
            <h2>Multi-Turn LLM Chatbot</h2>
            <p>
              Equipped with <strong>LiteLLM Key Failover</strong> and{" "}
              <strong>Response Caching</strong>.
            </p>
            <div className="starter-chips">
              <button
                type="button"
                className="starter-chip"
                onClick={() => setInputMessage("What is the capital of France?")}
              >
                What is the capital of France?
              </button>
              <button
                type="button"
                className="starter-chip"
                onClick={() => setInputMessage("Explain quantum computing in two sentences.")}
              >
                Explain quantum computing in two sentences.
              </button>
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`message-row ${msg.role}`}>
              {msg.role === "user" && (
                <div className="user-message">
                  <div className="avatar user-avatar">
                    <User size={16} />
                  </div>
                  <div className="message-content">{msg.content}</div>
                </div>
              )}

              {msg.role === "assistant" && (
                <div className="assistant-message" data-testid="assistant-message">
                  <div className="assistant-header">
                    <div className="avatar bot-avatar">
                      <Bot size={16} />
                    </div>
                    <span className="bot-name">Assistant</span>
                  </div>

                  <div className="message-body">{msg.content}</div>

                  {/* Metadata display satisfying contract */}
                  {msg.metadata && (
                    <div className="metadata-container">
                      <div className="meta-badge-group">
                        {/* Resolution Source: exactly LIVE_INFERENCE or LLM_CACHE */}
                        <span
                          className={`meta-badge ${
                            msg.metadata.resolution_source === "LLM_CACHE"
                              ? "badge-cache"
                              : "badge-live"
                          }`}
                          data-testid="meta-source"
                        >
                          {msg.metadata.resolution_source === "LLM_CACHE" ? (
                            <Database size={12} />
                          ) : (
                            <Zap size={12} />
                          )}
                          {msg.metadata.resolution_source}
                        </span>

                        {/* Model name */}
                        <span className="meta-badge badge-neutral" data-testid="meta-model">
                          <Cpu size={12} />
                          {msg.metadata.model}
                        </span>

                        {/* Latency: e.g. 812 ms */}
                        <span className="meta-badge badge-neutral" data-testid="meta-latency">
                          {msg.metadata.latency_ms} ms
                        </span>

                        {/* Token breakdown */}
                        <span className="meta-badge badge-neutral">
                          In:{" "}
                          <span data-testid="meta-input-tokens">
                            {msg.metadata.input_tokens}
                          </span>
                          {" / "}
                          Out:{" "}
                          <span data-testid="meta-output-tokens">
                            {msg.metadata.output_tokens}
                          </span>
                        </span>

                        {/* Key & Fallback Indicator */}
                        {msg.metadata.key_id && (
                          <span className="meta-badge badge-key" title="Key that responded">
                            {msg.metadata.key_id}
                          </span>
                        )}

                        {msg.metadata.fallback_attempts > 0 && (
                          <span className="meta-badge badge-warn" title="Failovers occurred">
                            {msg.metadata.fallback_attempts} fallback(s)
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {msg.role === "error" && (
                <div className="error-message">
                  <AlertTriangle size={18} className="error-icon" />
                  <div className="error-content">
                    <strong>Error:</strong> {msg.content}
                  </div>
                </div>
              )}
            </div>
          ))
        )}

        {loading && (
          <div className="message-row assistant">
            <div className="assistant-message loading">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <span className="loading-label">Generating response...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </main>

      {/* Input Form satisfying contract */}
      <footer className="input-footer">
        <form onSubmit={handleSend} className="input-form">
          <textarea
            data-testid="chat-input"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
            rows={1}
            className="chat-textarea"
            disabled={loading}
          />
          <button
            type="submit"
            data-testid="send-button"
            className="send-button"
            disabled={!inputMessage.trim() || loading}
            title="Send Message"
          >
            <Send size={18} />
          </button>
        </form>
      </footer>
    </div>
  );
}
