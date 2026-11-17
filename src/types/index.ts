export type ConnectionState = 'connected' | 'connecting' | 'disconnected' | 'generating';

export interface ModelInfo {
  id: string;
  name: string;
  description?: string;
  size?: string;
  parameters?: string;
  family?: string;
  provider: 'ollama' | 'cloud' | 'custom';
  is_local: boolean;
  is_default?: boolean;
  context_length?: number;
}

export interface DocumentInfo {
  id: string;
  conversation_id: string;
  filename: string;
  file_size: number;
  page_count: number;
  char_count?: number;
  created_at: string;
  status?: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
  is_streaming?: boolean;
  error?: string;
  model?: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  model: string;
  message_count?: number;
  messages?: Message[];
  documents?: DocumentInfo[];
}

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error';
  ollama_connected: boolean;
  active_model?: string;
  version?: string;
  models_available?: number;
  uptime_seconds?: number;
  latency_ms?: number;
}

export interface AppSettings {
  general: {
    username: string;
    systemPrompt: string;
    sendShortcut: 'enter' | 'cmd_enter';
  };
  appearance: {
    theme: 'dark' | 'oled' | 'zinc';
    fontSize: 'small' | 'medium' | 'large';
    codeLigatures: boolean;
    compactMessages: boolean;
    showTimestamps: boolean;
  };
  models: {
    defaultModel: string;
    temperature: number;
    topP: number;
    maxTokens: number;
    contextWindow: number;
  };
  localAi: {
    apiEndpoint: string;
    ollamaEndpoint: string;
    autoDetect: boolean;
  };
  privacy: {
    zeroTelemetry: boolean;
    localStorageOnly: boolean;
  };
}

export interface PromptSuggestion {
  id: string;
  category: string;
  title: string;
  prompt: string;
  icon: string;
}
