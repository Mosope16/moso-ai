export type ConnectionState = 'connected' | 'connecting' | 'disconnected' | 'generating';
export type WorkspaceMode = 'chat' | 'project';
export type VerificationStatus = 'verified' | 'partially_verified' | 'unverified' | 'none';

export interface QuotationCheckDetail {
  quote: string;
  overlap_score: number;
  verified: boolean;
}

export interface QuotationCheck {
  has_quotes: boolean;
  quotes_count?: number;
  all_quotes_verified: boolean;
  details?: QuotationCheckDetail[];
}

export interface VerificationReport {
  status: VerificationStatus;
  is_factual: boolean;
  category: string;
  tier?: number;
  tier_name?: string;
  sources_consulted?: Array<{
    type?: string;
    title?: string;
    page_number?: number;
    source_name?: string;
    excerpt?: string;
  }>;
  verified_claims?: string[];
  unverified_claims?: string[];
  disclaimer?: string | null;
  quotation_check?: QuotationCheck;
  appropriate_abstention?: boolean;
}

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

export interface Citation {
  id?: string;
  document_id: string;
  filename: string;
  document_name?: string;
  page_number: number;
  excerpt: string;
}

export interface DocumentInfo {
  id: string;
  conversation_id?: string;
  project_id?: string;
  filename: string;
  file_size: number;
  page_count: number;
  char_count?: number;
  chunk_count?: number;
  created_at: string;
  status?: string;
  extraction_status?: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  citations?: Citation[];
  verification?: VerificationReport;
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
  project_id?: string;
  message_count?: number;
  document_count?: number;
  messages?: Message[];
  documents?: DocumentInfo[];
}

export interface ProjectNote {
  id: string;
  project_id: string;
  title: string;
  content: string;
  category: 'note' | 'finding' | 'experiment' | 'methodology';
  created_at: string;
  updated_at: string;
}

export interface ProjectActivity {
  id: string;
  project_id: string;
  action_type?: string;
  description?: string;
  action?: string;
  details?: string;
  created_at: string;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  instructions?: string;
  custom_instructions?: string;
  created_at: string;
  updated_at: string;
  document_count?: number;
  conversation_count?: number;
  note_count?: number;
  documents?: DocumentInfo[];
  conversations?: Conversation[];
  notes?: ProjectNote[];
  activity?: ProjectActivity[];
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

export interface AuthStatusResponse {
  auth_required: boolean;
  authenticated: boolean;
}

