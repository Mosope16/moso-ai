import { Conversation, DocumentInfo, HealthResponse, ModelInfo } from '../types';

export interface ChatStreamCallbacks {
  onToken: (token: string) => void;
  onComplete: (fullText: string) => void;
  onError: (error: Error) => void;
}

export interface ChatStreamPayload {
  conversation_id?: string;
  model: string;
  messages: { role: string; content: string }[];
  max_tokens?: number;
  temperature?: number;
}

export class FastApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = '/api/v1') {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  public setBaseUrl(url: string) {
    this.baseUrl = url.replace(/\/+$/, '');
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }

  /**
   * Check FastAPI backend health and Ollama connection status
   * GET /api/v1/health
   */
  async checkHealth(): Promise<HealthResponse> {
    const startTime = performance.now();
    const response = await fetch(`${this.baseUrl}/health`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      const errText = await response.text().catch(() => '');
      throw new Error(`Health check failed: HTTP ${response.status} ${errText || response.statusText}`);
    }

    const data = await response.json();
    const latency_ms = Math.round(performance.now() - startTime);

    return {
      status: data.status || 'ok',
      ollama_connected: Boolean(data.ollama_connected ?? data.ollama ?? true),
      active_model: data.active_model || 'qwen3.5:2b',
      version: data.version || '0.1.0',
      models_available: data.models_count ?? (Array.isArray(data.models) ? data.models.length : 1),
      uptime_seconds: data.uptime_seconds,
      latency_ms,
    };
  }

  /**
   * Fetch available models dynamically from backend/Ollama
   * GET /api/v1/models
   */
  async getModels(): Promise<ModelInfo[]> {
    const response = await fetch(`${this.baseUrl}/models`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch models: HTTP ${response.status}`);
    }

    const data = await response.json();
    const modelsList = Array.isArray(data) ? data : data.models || [];

    return modelsList.map((m: any) => ({
      id: m.id || m.name,
      name: m.name || m.id,
      description: m.description || (m.is_local ? 'Local Ollama Model' : 'Cloud Provider'),
      size: m.size || '1.9 GB',
      parameters: m.parameters || m.details?.parameter_size || '2B',
      family: m.family || m.details?.family || 'qwen35',
      provider: m.provider || (m.is_local !== false ? 'ollama' : 'cloud'),
      is_local: m.is_local ?? true,
      is_default: m.is_default || m.id === 'qwen3.5:2b',
      context_length: m.context_length || 262144,
    }));
  }

  /**
   * Fetch all conversations from SQLite
   * GET /api/v1/conversations
   */
  async getConversations(): Promise<Conversation[]> {
    const response = await fetch(`${this.baseUrl}/conversations`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch conversations: HTTP ${response.status}`);
    }

    const data = await response.json();
    const list = Array.isArray(data) ? data : data.conversations || [];

    return list.map((c: any) => ({
      id: String(c.id),
      title: c.title || 'Untitled Conversation',
      created_at: c.created_at || new Date().toISOString(),
      updated_at: c.updated_at || c.created_at || new Date().toISOString(),
      model: c.model || 'qwen3.5:2b',
      message_count: c.message_count ?? (Array.isArray(c.messages) ? c.messages.length : 0),
    }));
  }

  /**
   * Create a new conversation in SQLite
   * POST /api/v1/conversations
   */
  async createConversation(title: string = 'New Conversation', model: string = 'qwen3.5:2b'): Promise<Conversation> {
    const response = await fetch(`${this.baseUrl}/conversations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ title, model }),
    });

    if (!response.ok) {
      const errText = await response.text().catch(() => '');
      throw new Error(`Failed to create conversation: HTTP ${response.status} ${errText}`);
    }

    const data = await response.json();
    return {
      id: String(data.id),
      title: data.title || title,
      created_at: data.created_at || new Date().toISOString(),
      updated_at: data.updated_at || new Date().toISOString(),
      model: data.model || model,
      message_count: 0,
      messages: data.messages || [],
      documents: [],
    };
  }

  /**
   * Get single conversation by ID with messages and attached documents
   * GET /api/v1/conversations/{id}
   */
  async getConversation(id: string): Promise<Conversation> {
    const response = await fetch(`${this.baseUrl}/conversations/${encodeURIComponent(id)}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch conversation: HTTP ${response.status}`);
    }

    const data = await response.json();
    return {
      id: String(data.id),
      title: data.title,
      created_at: data.created_at,
      updated_at: data.updated_at,
      model: data.model || 'qwen3.5:2b',
      message_count: data.message_count ?? (data.messages?.length || 0),
      messages: (data.messages || []).map((m: any) => ({
        id: String(m.id),
        conversation_id: String(id),
        role: m.role,
        content: m.content,
        created_at: m.created_at || new Date().toISOString(),
        model: m.model,
      })),
      documents: (data.documents || []).map((d: any) => ({
        id: String(d.id),
        conversation_id: String(d.conversation_id),
        filename: d.filename,
        file_size: d.file_size,
        page_count: d.page_count,
        char_count: d.char_count,
        created_at: d.created_at,
        status: 'ready',
      })),
    };
  }

  /**
   * Rename / update conversation title
   * PATCH /api/v1/conversations/{id}
   */
  async renameConversation(id: string, title: string): Promise<Conversation> {
    const response = await fetch(`${this.baseUrl}/conversations/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ title }),
    });

    if (!response.ok) {
      throw new Error(`Failed to rename conversation: HTTP ${response.status}`);
    }

    const data = await response.json();
    return {
      id: String(data.id),
      title: data.title,
      created_at: data.created_at,
      updated_at: data.updated_at,
      model: data.model || 'qwen3.5:2b',
    };
  }

  /**
   * Delete a conversation from SQLite
   * DELETE /api/v1/conversations/{id}
   */
  async deleteConversation(id: string): Promise<boolean> {
    const response = await fetch(`${this.baseUrl}/conversations/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      headers: {
        'Accept': 'application/json',
      },
    });

    return response.ok;
  }

  /**
   * Upload PDF Document to conversation
   * POST /api/v1/documents
   */
  async uploadDocument(file: File, conversationId?: string): Promise<DocumentInfo> {
    const formData = new FormData();
    formData.append('file', file);
    if (conversationId) {
      formData.append('conversation_id', conversationId);
    }

    const response = await fetch(`${this.baseUrl}/documents`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      let errorMsg = `Upload failed: HTTP ${response.status}`;
      try {
        const errJson = await response.json();
        errorMsg = errJson.detail || errJson.error || errorMsg;
      } catch {
        const text = await response.text().catch(() => '');
        if (text) errorMsg = text;
      }
      throw new Error(errorMsg);
    }

    const data = await response.json();
    return {
      id: String(data.id),
      conversation_id: String(data.conversation_id),
      filename: data.filename,
      file_size: data.file_size,
      page_count: data.page_count,
      char_count: data.char_count,
      created_at: data.created_at,
      status: data.status || 'ready',
    };
  }

  /**
   * Get all documents attached to a conversation
   * GET /api/v1/conversations/{conv_id}/documents
   */
  async getConversationDocuments(conversationId: string): Promise<DocumentInfo[]> {
    const response = await fetch(`${this.baseUrl}/conversations/${encodeURIComponent(conversationId)}/documents`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch documents: HTTP ${response.status}`);
    }

    const data = await response.json();
    return (data || []).map((d: any) => ({
      id: String(d.id),
      conversation_id: String(d.conversation_id),
      filename: d.filename,
      file_size: d.file_size,
      page_count: d.page_count,
      created_at: d.created_at,
      status: 'ready',
    }));
  }

  /**
   * Delete document by ID
   * DELETE /api/v1/documents/{doc_id}
   */
  async deleteDocument(documentId: string): Promise<boolean> {
    const response = await fetch(`${this.baseUrl}/documents/${encodeURIComponent(documentId)}`, {
      method: 'DELETE',
      headers: {
        'Accept': 'application/json',
      },
    });

    return response.ok;
  }

  /**
   * Stream chat completion via Server-Sent Events (SSE)
   * POST /api/v1/chat
   */
  async streamChat(
    payload: ChatStreamPayload,
    callbacks: ChatStreamCallbacks,
    signal?: AbortSignal
  ): Promise<void> {
    try {
      const response = await fetch(`${this.baseUrl}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream, application/json',
        },
        body: JSON.stringify({
          conversation_id: payload.conversation_id,
          model: payload.model,
          messages: payload.messages,
          stream: true,
          max_tokens: payload.max_tokens ?? 256,
          temperature: payload.temperature ?? 0.7,
        }),
        signal,
      });

      if (!response.ok) {
        let errorMsg = `HTTP ${response.status} ${response.statusText}`;
        try {
          const errJson = await response.json();
          errorMsg = errJson.detail || errJson.error || errorMsg;
        } catch {
          const rawText = await response.text().catch(() => '');
          if (rawText) errorMsg = rawText;
        }
        throw new Error(errorMsg);
      }

      if (!response.body) {
        throw new Error('Response body is empty, cannot establish SSE stream');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let accumulatedResponse = '';
      let currentEvent = 'message';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith(':')) {
            currentEvent = 'message';
            continue;
          }

          if (trimmed.startsWith('event:')) {
            currentEvent = trimmed.slice(6).trim();
            continue;
          }

          if (trimmed.startsWith('data:')) {
            const dataStr = trimmed.slice(5).trim();

            if (dataStr === '[DONE]' || currentEvent === 'done') {
              callbacks.onComplete(accumulatedResponse);
              return;
            }

            if (currentEvent === 'error') {
              let errMsg = dataStr;
              try {
                const parsedErr = JSON.parse(dataStr);
                errMsg = parsedErr.error || parsedErr.detail || errMsg;
              } catch {
                // raw string
              }
              callbacks.onError(new Error(errMsg));
              return;
            }

            try {
              const parsed = JSON.parse(dataStr);
              if (parsed.error) {
                callbacks.onError(new Error(parsed.error));
                return;
              }

              const chunk =
                parsed.token ??
                parsed.chunk ??
                parsed.text ??
                parsed.delta?.content ??
                parsed.content ??
                '';

              if (chunk) {
                accumulatedResponse += chunk;
                callbacks.onToken(chunk);
              }
            } catch {
              accumulatedResponse += dataStr;
              callbacks.onToken(dataStr);
            }
          }
        }
      }

      callbacks.onComplete(accumulatedResponse);
    } catch (err: any) {
      if (err.name === 'AbortError' || signal?.aborted) {
        return;
      }
      callbacks.onError(err instanceof Error ? err : new Error(String(err)));
    }
  }
}

export const api = new FastApiClient();
