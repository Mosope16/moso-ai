import { Citation, Conversation, DocumentInfo, HealthResponse, ModelInfo, Project, ProjectActivity, ProjectNote, RetrievalDiagnostic, StreamStatus, VerificationReport } from '../types';

export interface ChatStreamCallbacks {
  onToken: (token: string) => void;
  onCitations?: (citations: Citation[]) => void;
  onVerification?: (verification: VerificationReport) => void;
  onStatus?: (status: StreamStatus) => void;
  onDiagnostics?: (diagnostics: RetrievalDiagnostic[]) => void;
  onComplete: (fullText: string) => void;
  onError: (error: Error) => void;
}

export interface ChatStreamPayload {
  conversation_id?: string;
  project_id?: string;
  model: string;
  messages: { role: string; content: string }[];
  max_tokens?: number;
  temperature?: number;
  enable_web_search?: boolean;
}

export class FastApiClient {
  private baseUrl: string;
  private token: string | null = null;
  private onUnauthorizedCallback?: () => void;

  constructor(baseUrl: string = '/api/v1') {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    try {
      this.token = localStorage.getItem('moso_tester_token') || null;
    } catch {
      this.token = null;
    }
  }

  public setToken(token: string | null) {
    this.token = token;
    try {
      if (token) {
        localStorage.setItem('moso_tester_token', token);
      } else {
        localStorage.removeItem('moso_tester_token');
      }
    } catch {}
  }

  public getToken(): string | null {
    return this.token;
  }

  public setOnUnauthorized(cb: () => void) {
    this.onUnauthorizedCallback = cb;
  }

  public setBaseUrl(url: string) {
    let clean = url.trim().replace(/\/+$/, '');
    // Automatically sanitize legacy or hardcoded localhost URLs to relative proxy paths
    if (clean.startsWith('http://localhost:8000') || clean.startsWith('http://127.0.0.1:8000')) {
      clean = clean.replace(/^http:\/\/(localhost|127\.0\.0\.1):8000/, '');
      if (!clean) clean = '/api/v1';
    }
    this.baseUrl = clean;
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }

  private async fetchWithAuth(input: string, init?: RequestInit): Promise<Response> {
    const headers = new Headers(init?.headers);
    if (this.token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${this.token}`);
      headers.set('X-Moso-Access-Token', this.token);
    }
    const response = await fetch(input, {
      ...init,
      headers,
      credentials: 'include',
    });

    if (response.status === 401) {
      this.onUnauthorizedCallback?.();
    }

    return response;
  }

  // ---------------------------------------------------------
  // Authentication & Tester Access API
  // ---------------------------------------------------------

  /**
   * Check if tester access password authentication is required
   * GET /api/v1/auth/status
   */
  async getAuthStatus(): Promise<{ auth_required: boolean; authenticated: boolean }> {
    const response = await this.fetchWithAuth(`${this.baseUrl}/auth/status`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Auth status check failed: HTTP ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Authenticate with tester access password
   * POST /api/v1/auth/login
   */
  async login(password: string): Promise<{ status: string; token: string }> {
    const response = await fetch(`${this.baseUrl}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({ password }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Incorrect access password.' }));
      throw new Error(err.error || err.detail?.error || 'Authentication failed');
    }

    const data = await response.json();
    if (data.token && data.token !== 'not_required') {
      this.setToken(data.token);
    }
    return data;
  }

  /**
   * Invalidate current session and clear token
   * POST /api/v1/auth/logout
   */
  async logout(): Promise<void> {
    try {
      await this.fetchWithAuth(`${this.baseUrl}/auth/logout`, {
        method: 'POST',
      });
    } finally {
      this.setToken(null);
    }
  }

  // ---------------------------------------------------------
  // Core Health & Models API
  // ---------------------------------------------------------

  /**
   * Check FastAPI backend health and Ollama connection status
   * GET /api/v1/health
   */
  async checkHealth(): Promise<HealthResponse> {
    const startTime = performance.now();
    const response = await this.fetchWithAuth(`${this.baseUrl}/health`, {
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
      active_model: data.active_model || 'qwen3.5:4b',
      version: data.version || '0.2.0',
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
    const response = await this.fetchWithAuth(`${this.baseUrl}/models`, {
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
      is_default: m.is_default || m.id === 'qwen3.5:4b',
      context_length: m.context_length || 262144,
    }));
  }

  // ---------------------------------------------------------
  // Project Workspace API
  // ---------------------------------------------------------

  /**
   * List all research projects
   * GET /api/v1/projects
   */
  async getProjects(): Promise<Project[]> {
    const response = await this.fetchWithAuth(`${this.baseUrl}/projects`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch projects: HTTP ${response.status}`);
    }

    const data = await response.json();
    return (data || []).map((p: any) => ({
      id: String(p.id),
      name: p.name,
      description: p.description || '',
      instructions: p.instructions || '',
      created_at: p.created_at,
      updated_at: p.updated_at,
      document_count: p.document_count || 0,
      conversation_count: p.conversation_count || 0,
      note_count: p.note_count || 0,
    }));
  }

  /**
   * Create a new research project
   * POST /api/v1/projects
   */
  async createProject(name: string, description: string = '', instructions: string = ''): Promise<Project> {
    const response = await this.fetchWithAuth(`${this.baseUrl}/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ name, description, instructions }),
    });

    if (!response.ok) {
      const errText = await response.text().catch(() => '');
      throw new Error(`Failed to create project: HTTP ${response.status} ${errText}`);
    }

    return await response.json();
  }

  /**
   * Get single project details including its documents, conversations, notes, and activity
   * GET /api/v1/projects/{id}
   */
  async getProject(id: string): Promise<Project> {
    const response = await this.fetchWithAuth(`${this.baseUrl}/projects/${encodeURIComponent(id)}`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch project: HTTP ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Update project settings
   * PATCH /api/v1/projects/{id}
   */
  async updateProject(
    id: string,
    updates: Partial<{ name: string; description: string; instructions: string }>
  ): Promise<Project> {
    const response = await this.fetchWithAuth(`${this.baseUrl}/projects/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(updates),
    });

    if (!response.ok) {
      throw new Error(`Failed to update project: HTTP ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Delete project and cascade all its data
   * DELETE /api/v1/projects/{id}
   */
  async deleteProject(id: string): Promise<boolean> {
    const response = await this.fetchWithAuth(`${this.baseUrl}/projects/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      headers: { 'Accept': 'application/json' },
    });

    return response.ok;
  }

  /**
   * List research notes for a project
   * GET /api/v1/projects/{id}/notes
   */
  async getProjectNotes(projectId: string): Promise<ProjectNote[]> {
    const response = await this.fetchWithAuth(`${this.baseUrl}/projects/${encodeURIComponent(projectId)}/notes`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch notes: HTTP ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Create a research note or finding
   * POST /api/v1/projects/{id}/notes
   */
  async createProjectNote(
    projectId: string,
    title: string,
    content: string,
    category: string = 'note'
  ): Promise<ProjectNote> {
    const response = await this.fetchWithAuth(`${this.baseUrl}/projects/${encodeURIComponent(projectId)}/notes`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ title, content, category }),
    });

    if (!response.ok) {
      throw new Error(`Failed to save note: HTTP ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Update a research note
   * PATCH /api/v1/projects/{id}/notes/{noteId}
   */
  async updateProjectNote(
    projectId: string,
    noteId: string,
    updates: Partial<{ title: string; content: string; category: string }>
  ): Promise<ProjectNote> {
    const response = await this.fetchWithAuth(
      `${this.baseUrl}/projects/${encodeURIComponent(projectId)}/notes/${encodeURIComponent(noteId)}`,
      {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify(updates),
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to update note: HTTP ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Delete a research note
   * DELETE /api/v1/projects/{id}/notes/{noteId}
   */
  async deleteProjectNote(projectId: string, noteId: string): Promise<boolean> {
    const response = await this.fetchWithAuth(
      `${this.baseUrl}/projects/${encodeURIComponent(projectId)}/notes/${encodeURIComponent(noteId)}`,
      {
        method: 'DELETE',
        headers: { 'Accept': 'application/json' },
      }
    );

    return response.ok;
  }

  /**
   * Get project activity log
   * GET /api/v1/projects/{id}/activity
   */
  async getProjectActivity(projectId: string): Promise<ProjectActivity[]> {
    const response = await this.fetchWithAuth(`${this.baseUrl}/projects/${encodeURIComponent(projectId)}/activity`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch activity: HTTP ${response.status}`);
    }

    return await response.json();
  }

  // ---------------------------------------------------------
  // Conversations API
  // ---------------------------------------------------------

  /**
   * Fetch conversations from SQLite, optionally filtered by project_id
   * GET /api/v1/conversations
   */
  async getConversations(projectId?: string): Promise<Conversation[]> {
    const url = projectId
      ? `${this.baseUrl}/conversations?project_id=${encodeURIComponent(projectId)}`
      : `${this.baseUrl}/conversations`;

    const response = await this.fetchWithAuth(url, {
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
      model: c.model || 'qwen3.5:4b',
      project_id: c.project_id || undefined,
      message_count: c.message_count ?? (Array.isArray(c.messages) ? c.messages.length : 0),
      document_count: c.document_count || 0,
      documents: (c.documents || []).map((d: any) => ({
        id: String(d.id),
        conversation_id: String(c.id),
        filename: d.filename,
        file_size: d.file_size,
        page_count: d.page_count,
        created_at: d.created_at,
        status: 'ready',
      })),
    }));
  }

  /**
   * Create a new conversation in SQLite
   * POST /api/v1/conversations
   */
  async createConversation(
    title: string = 'New Conversation',
    model: string = 'qwen3.5:4b',
    projectId?: string
  ): Promise<Conversation> {
    const response = await this.fetchWithAuth(`${this.baseUrl}/conversations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ title, model, project_id: projectId }),
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
      project_id: data.project_id || projectId,
      message_count: 0,
      messages: data.messages || [],
      documents: [],
    };
  }

  /**
   * Get single conversation by ID with messages, citations, and attached documents
   * GET /api/v1/conversations/{id}
   */
  async getConversation(id: string): Promise<Conversation> {
    const response = await this.fetchWithAuth(`${this.baseUrl}/conversations/${encodeURIComponent(id)}`, {
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
      model: data.model || 'qwen3.5:4b',
      project_id: data.project_id || undefined,
      message_count: data.message_count ?? (data.messages?.length || 0),
      messages: (data.messages || []).map((m: any) => ({
        id: String(m.id),
        conversation_id: String(id),
        role: m.role,
        content: m.content,
        citations: Array.isArray(m.citations) ? m.citations : [],
        created_at: m.created_at || new Date().toISOString(),
        model: m.model,
      })),
      documents: (data.documents || []).map((d: any) => ({
        id: String(d.id),
        conversation_id: String(d.conversation_id),
        project_id: d.project_id || undefined,
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
    const response = await this.fetchWithAuth(`${this.baseUrl}/conversations/${encodeURIComponent(id)}`, {
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
      model: data.model || 'qwen3.5:4b',
      project_id: data.project_id,
    };
  }

  /**
   * Update active model for an existing conversation
   * PATCH /api/v1/conversations/{id}
   */
  async updateConversationModel(id: string, model: string): Promise<void> {
    await this.fetchWithAuth(`${this.baseUrl}/conversations/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ model }),
    }).catch(() => {});
  }

  /**
   * Delete a conversation from SQLite
   * DELETE /api/v1/conversations/{id}
   */
  async deleteConversation(id: string): Promise<boolean> {
    const response = await this.fetchWithAuth(`${this.baseUrl}/conversations/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      headers: {
        'Accept': 'application/json',
      },
    });

    return response.ok;
  }

  /**
   * Upload PDF Document to conversation or project
   * POST /api/v1/documents
   */
  async uploadDocument(file: File, conversationId?: string, projectId?: string): Promise<DocumentInfo> {
    const formData = new FormData();
    formData.append('file', file);
    if (conversationId) {
      formData.append('conversation_id', conversationId);
    }
    if (projectId) {
      formData.append('project_id', projectId);
    }

    const response = await this.fetchWithAuth(`${this.baseUrl}/documents`, {
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
      conversation_id: data.conversation_id ? String(data.conversation_id) : undefined,
      project_id: data.project_id ? String(data.project_id) : undefined,
      filename: data.filename,
      file_size: data.file_size,
      page_count: data.page_count,
      char_count: data.char_count,
      chunk_count: data.chunk_count,
      created_at: data.created_at,
      status: data.status || 'ready',
      extraction_status: data.extraction_status || 'success',
    };
  }

  /**
   * Get all documents attached to a conversation
   * GET /api/v1/conversations/{conv_id}/documents
   */
  async getConversationDocuments(conversationId: string): Promise<DocumentInfo[]> {
    const response = await this.fetchWithAuth(`${this.baseUrl}/conversations/${encodeURIComponent(conversationId)}/documents`, {
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
      project_id: d.project_id || undefined,
      filename: d.filename,
      file_size: d.file_size,
      page_count: d.page_count,
      created_at: d.created_at,
      status: 'ready',
    }));
  }

  /**
   * Get all documents in a project library
   * GET /api/v1/projects/{project_id}/documents
   */
  async getProjectDocuments(projectId: string): Promise<DocumentInfo[]> {
    const response = await this.fetchWithAuth(`${this.baseUrl}/projects/${encodeURIComponent(projectId)}/documents`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch project documents: HTTP ${response.status}`);
    }

    const data = await response.json();
    return (data || []).map((d: any) => ({
      id: String(d.id),
      project_id: String(d.project_id || projectId),
      conversation_id: d.conversation_id ? String(d.conversation_id) : undefined,
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
    const response = await this.fetchWithAuth(`${this.baseUrl}/documents/${encodeURIComponent(documentId)}`, {
      method: 'DELETE',
      headers: {
        'Accept': 'application/json',
      },
    });

    return response.ok;
  }

  /**
   * Perform direct web search
   * POST /api/v1/tools/web-search
   */
  async searchWeb(query: string, maxResults: number = 5): Promise<any> {
    const response = await this.fetchWithAuth(`${this.baseUrl}/tools/web-search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ query, max_results: maxResults }),
    });
    if (!response.ok) {
      throw new Error(`Web search failed with status ${response.status}`);
    }
    return response.json();
  }

  /**
   * Safely fetch external web page or PDF content
   * POST /api/v1/tools/web-fetch
   */
  async fetchWebUrl(url: string): Promise<any> {
    const response = await this.fetchWithAuth(`${this.baseUrl}/tools/web-fetch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ url }),
    });
    if (!response.ok) {
      throw new Error(`Web fetch failed with status ${response.status}`);
    }
    return response.json();
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
      const response = await this.fetchWithAuth(`${this.baseUrl}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream, application/json',
        },
        body: JSON.stringify({
          conversation_id: payload.conversation_id,
          project_id: payload.project_id,
          model: payload.model,
          messages: payload.messages,
          max_tokens: payload.max_tokens,
          temperature: payload.temperature,
          enable_web_search: payload.enable_web_search,
          stream: true,
        }),
        signal,
      });

      if (!response.ok) {
        let errDetail = `HTTP ${response.status}`;
        try {
          const errData = await response.json();
          errDetail = errData.detail || errData.error || errDetail;
        } catch {
          const text = await response.text().catch(() => '');
          if (text) errDetail = text;
        }
        throw new Error(`Generation failed: ${errDetail}`);
      }

      if (!response.body) {
        throw new Error('ReadableStream not supported by browser environment.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let accumulatedText = '';
      let isDone = false;

      while (!isDone) {
        const { value, done } = await reader.read();
        if (done) {
          isDone = true;
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let currentEvent = 'message';

        for (const line of lines) {
          const trimmed = line.trim();

          if (trimmed.startsWith('event:')) {
            currentEvent = trimmed.slice(6).trim();
            continue;
          }

          if (trimmed.startsWith('data:')) {
            const dataStr = trimmed.slice(5).trim();

            if (dataStr === '[DONE]') {
              isDone = true;
              callbacks.onComplete(accumulatedText);
              return;
            }

            try {
              const parsed = JSON.parse(dataStr);

              // 1. Token chunk event
              if (currentEvent === 'token' || parsed.token !== undefined) {
                const token = parsed.token || '';
                accumulatedText += token;
                callbacks.onToken(token);
              }
              // 2. Status / tool execution event
              else if (currentEvent === 'status' || parsed.status) {
                if (callbacks.onStatus && (parsed.message || parsed.tool)) {
                  callbacks.onStatus(parsed);
                }
              }
              // 3. Citations payload event
              else if (currentEvent === 'citations' || parsed.citations) {
                if (callbacks.onCitations && Array.isArray(parsed.citations)) {
                  callbacks.onCitations(parsed.citations);
                }
              }
              // 4. Diagnostics event
              else if (currentEvent === 'diagnostic' || parsed.diagnostics) {
                if (callbacks.onDiagnostics && parsed.diagnostics) {
                  callbacks.onDiagnostics(parsed.diagnostics);
                }
              }
              // 5. Verification report event
              else if (currentEvent === 'verification' || parsed.verification) {
                if (callbacks.onVerification && parsed.verification) {
                  callbacks.onVerification(parsed.verification);
                }
              }
              // 6. Inference error event
              else if (currentEvent === 'error' || parsed.error) {
                throw new Error(parsed.error || 'Unknown streaming inference error');
              }
              // 7. Final completion summary event
              else if (currentEvent === 'done') {
                if (parsed.citations && callbacks.onCitations) {
                  callbacks.onCitations(parsed.citations);
                }
                if (parsed.verification && callbacks.onVerification) {
                  callbacks.onVerification(parsed.verification);
                }
                if (parsed.diagnostics && callbacks.onDiagnostics) {
                  callbacks.onDiagnostics(parsed.diagnostics);
                }
                isDone = true;
                callbacks.onComplete(accumulatedText);
                return;
              }
            } catch (jsonErr: any) {
              if (jsonErr.message && !jsonErr.message.includes('JSON')) {
                throw jsonErr;
              }
            }
          }
        }
      }

      if (!isDone) {
        callbacks.onComplete(accumulatedText);
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        return;
      }
      callbacks.onError(err instanceof Error ? err : new Error(String(err)));
    }
  }
}

export const api = new FastApiClient();
