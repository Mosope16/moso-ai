import { Citation, Conversation, DocumentInfo, HealthResponse, ModelInfo, Project, ProjectActivity, ProjectNote } from '../types';
import { ChatStreamCallbacks, ChatStreamPayload } from './api';

const MOCK_STORAGE_KEY = 'moso_mock_conversations_v1';
const MOCK_DOCS_KEY = 'moso_mock_documents_v1';
const MOCK_PROJECTS_KEY = 'moso_mock_projects_v1';
const MOCK_NOTES_KEY = 'moso_mock_notes_v1';
const MOCK_ACTIVITY_KEY = 'moso_mock_activity_v1';

function generateUuid(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export const MOCK_MODELS: ModelInfo[] = [
  {
    id: 'qwen3.5:4b',
    name: 'Qwen 3.5 4B',
    description: 'Default local model for reasoning, research, web grounding, and coding (Ollama)',
    size: '3.1 GB',
    parameters: '4B',
    family: 'qwen35',
    provider: 'ollama',
    is_local: true,
    is_default: true,
    context_length: 262144,
  },
  {
    id: 'qwen3.5:2b',
    name: 'Qwen 3.5 2B',
    description: 'Ultra-lightweight local model for quick tasks and low-resource environments (Ollama)',
    size: '1.9 GB',
    parameters: '2B',
    family: 'qwen35',
    provider: 'ollama',
    is_local: true,
    is_default: false,
    context_length: 262144,
  },
  {
    id: 'cloud:gpt-4o',
    name: 'GPT-4o (Cloud)',
    description: 'OpenAI flagship model (planned future integration)',
    size: 'Cloud API',
    parameters: 'Omni',
    family: 'gpt',
    provider: 'cloud',
    is_local: false,
    is_default: false,
    context_length: 128000,
  },
  {
    id: 'cloud:claude-3-5-sonnet',
    name: 'Claude 3.5 Sonnet (Cloud)',
    description: 'Anthropic frontier model (planned future integration)',
    size: 'Cloud API',
    parameters: 'Sonnet',
    family: 'claude',
    provider: 'cloud',
    is_local: false,
    is_default: false,
    context_length: 200000,
  },
];

const INITIAL_MOCK_PROJECTS: Project[] = [
  {
    id: 'proj-mock-deeplearning',
    name: 'Vision Transformers & Attention',
    description: 'Literature review and evaluation of self-attention mechanisms in computer vision.',
    instructions: 'Focus on ViT scaling laws, inductive biases, and computational complexity relative to CNNs.',
    created_at: new Date(Date.now() - 3600 * 1000 * 24 * 3).toISOString(),
    updated_at: new Date(Date.now() - 3600 * 1000 * 5).toISOString(),
    document_count: 1,
    conversation_count: 1,
    note_count: 2,
  },
];

const INITIAL_MOCK_NOTES: ProjectNote[] = [
  {
    id: 'note-mock-1',
    project_id: 'proj-mock-deeplearning',
    title: 'Self-Attention Computational Complexity',
    content: 'Standard multi-head self-attention scales quadratically with sequence length: \\[\\mathcal{O}(N^2 \\cdot d)\\] Linear attention approximations reduce this to \\(\\mathcal{O}(N \\cdot d^2)\\).',
    category: 'finding',
    created_at: new Date(Date.now() - 3600 * 1000 * 12).toISOString(),
    updated_at: new Date(Date.now() - 3600 * 1000 * 12).toISOString(),
  },
  {
    id: 'note-mock-2',
    project_id: 'proj-mock-deeplearning',
    title: 'Model Evaluation Metrics Checklist',
    content: 'Key metrics to track during fine-tuning:\n- Precision and Recall\n- F1-Score: \\[F_1 = 2 \\cdot \\frac{\\text{Precision} \\cdot \\text{Recall}}{\\text{Precision} + \\text{Recall}}\\]\n- Macro & Weighted ROC-AUC',
    category: 'methodology',
    created_at: new Date(Date.now() - 3600 * 1000 * 6).toISOString(),
    updated_at: new Date(Date.now() - 3600 * 1000 * 6).toISOString(),
  },
];

const INITIAL_MOCK_ACTIVITY: ProjectActivity[] = [
  {
    id: 'act-mock-1',
    project_id: 'proj-mock-deeplearning',
    action: 'project_created',
    details: "Created research project 'Vision Transformers & Attention'",
    created_at: new Date(Date.now() - 3600 * 1000 * 24 * 3).toISOString(),
  },
  {
    id: 'act-mock-2',
    project_id: 'proj-mock-deeplearning',
    action: 'document_uploaded',
    details: "Ingested paper 'attention_is_all_you_need.pdf' (15 pages)",
    created_at: new Date(Date.now() - 3600 * 1000 * 20).toISOString(),
  },
  {
    id: 'act-mock-3',
    project_id: 'proj-mock-deeplearning',
    action: 'note_saved',
    details: "Added finding: 'Self-Attention Computational Complexity'",
    created_at: new Date(Date.now() - 3600 * 1000 * 12).toISOString(),
  },
];

const INITIAL_MOCK_CONVERSATIONS: Conversation[] = [
  {
    id: 'conv-mock-1',
    title: 'FastAPI SSE streaming and SQLite schema',
    created_at: new Date(Date.now() - 3600 * 1000 * 2).toISOString(),
    updated_at: new Date(Date.now() - 3600 * 1000 * 2).toISOString(),
    model: 'qwen3.5:2b',
    message_count: 2,
    messages: [
      {
        id: 'msg-mock-1',
        conversation_id: 'conv-mock-1',
        role: 'user',
        content: 'How should we architect the FastAPI SSE chat endpoint for local streaming in Moso AI?',
        created_at: new Date(Date.now() - 3600 * 1000 * 2).toISOString(),
      },
      {
        id: 'msg-mock-2',
        conversation_id: 'conv-mock-1',
        role: 'assistant',
        content: `Here is a high-performance SSE streaming architecture using **FastAPI** and **async generators** connected to Ollama:

\`\`\`python
import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import httpx

app = FastAPI()

async def generate_ollama_stream(prompt: str, model: str = "qwen3.5:2b"):
    url = "http://127.0.0.1:11434/api/chat"
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": True, "think": False}
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                token = data.get("message", {}).get("content", "")
                if token:
                    yield f"data: {json.dumps({'token': token})}\\n\\n"
                if data.get("done", False):
                    yield "data: [DONE]\\n\\n"
                    break
\`\`\`

### Key Architectural Strengths:
1. **Low Memory Footprint**: No full response buffering in Python heap.
2. **True Chunk Streaming**: Client receives tokens with ~15ms latency.
3. **No Unnecessary Thinking Tokens**: Passed \`"think": False\` for instant CPU inference.`,
        created_at: new Date(Date.now() - 3600 * 1000 * 2 + 15000).toISOString(),
        model: 'qwen3.5:2b',
      },
    ],
    documents: [],
  },
];

class MockService {
  private conversations: Conversation[] = [];
  private documents: DocumentInfo[] = [];
  private projects: Project[] = [];
  private notes: ProjectNote[] = [];
  private activity: ProjectActivity[] = [];

  constructor() {
    this.loadFromStorage();
  }

  private loadFromStorage() {
    try {
      const stored = localStorage.getItem(MOCK_STORAGE_KEY);
      this.conversations = stored ? JSON.parse(stored) : [...INITIAL_MOCK_CONVERSATIONS];

      const storedDocs = localStorage.getItem(MOCK_DOCS_KEY);
      this.documents = storedDocs ? JSON.parse(storedDocs) : [];

      const storedProjects = localStorage.getItem(MOCK_PROJECTS_KEY);
      this.projects = storedProjects ? JSON.parse(storedProjects) : [...INITIAL_MOCK_PROJECTS];

      const storedNotes = localStorage.getItem(MOCK_NOTES_KEY);
      this.notes = storedNotes ? JSON.parse(storedNotes) : [...INITIAL_MOCK_NOTES];

      const storedActivity = localStorage.getItem(MOCK_ACTIVITY_KEY);
      this.activity = storedActivity ? JSON.parse(storedActivity) : [...INITIAL_MOCK_ACTIVITY];
    } catch {
      this.conversations = [...INITIAL_MOCK_CONVERSATIONS];
      this.documents = [];
      this.projects = [...INITIAL_MOCK_PROJECTS];
      this.notes = [...INITIAL_MOCK_NOTES];
      this.activity = [...INITIAL_MOCK_ACTIVITY];
    }
  }

  private saveToStorage() {
    try {
      localStorage.setItem(MOCK_STORAGE_KEY, JSON.stringify(this.conversations));
      localStorage.setItem(MOCK_DOCS_KEY, JSON.stringify(this.documents));
      localStorage.setItem(MOCK_PROJECTS_KEY, JSON.stringify(this.projects));
      localStorage.setItem(MOCK_NOTES_KEY, JSON.stringify(this.notes));
      localStorage.setItem(MOCK_ACTIVITY_KEY, JSON.stringify(this.activity));
    } catch {
      // Ignore quota errors in storage
    }
  }

  async checkHealth(): Promise<HealthResponse> {
    return {
      status: 'ok',
      ollama_connected: true,
      active_model: 'qwen3.5:4b',
      version: '0.2.0 (Mock Mode)',
      models_available: 3,
      latency_ms: 5,
    };
  }

  async getModels(): Promise<ModelInfo[]> {
    return MOCK_MODELS;
  }

  // ---------------------------------------------------------
  // Project Workspace Methods
  // ---------------------------------------------------------

  async getProjects(): Promise<Project[]> {
    this.loadFromStorage();
    return this.projects.map((p) => ({
      ...p,
      document_count: this.documents.filter((d) => d.project_id === p.id).length,
      conversation_count: this.conversations.filter((c) => c.project_id === p.id).length,
      note_count: this.notes.filter((n) => n.project_id === p.id).length,
    }));
  }

  async createProject(name: string, description: string = '', instructions: string = ''): Promise<Project> {
    const id = `proj-mock-${generateUuid().slice(0, 8)}`;
    const now = new Date().toISOString();
    const project: Project = {
      id,
      name,
      description,
      instructions,
      created_at: now,
      updated_at: now,
      document_count: 0,
      conversation_count: 0,
      note_count: 0,
    };
    this.projects.unshift(project);
    this.activity.unshift({
      id: `act-${generateUuid()}`,
      project_id: id,
      action: 'project_created',
      details: `Created project '${name}'`,
      created_at: now,
    });
    this.saveToStorage();
    return project;
  }

  async getProject(id: string): Promise<Project> {
    this.loadFromStorage();
    const proj = this.projects.find((p) => p.id === id);
    if (!proj) throw new Error('Project not found');

    return {
      ...proj,
      documents: this.documents.filter((d) => d.project_id === id),
      conversations: this.conversations.filter((c) => c.project_id === id),
      notes: this.notes.filter((n) => n.project_id === id),
      activity: this.activity.filter((a) => a.project_id === id),
    };
  }

  async updateProject(
    id: string,
    updates: Partial<{ name: string; description: string; instructions: string }>
  ): Promise<Project> {
    const idx = this.projects.findIndex((p) => p.id === id);
    if (idx === -1) throw new Error('Project not found');

    const updated = {
      ...this.projects[idx],
      ...updates,
      updated_at: new Date().toISOString(),
    };
    this.projects[idx] = updated;
    this.saveToStorage();
    return updated;
  }

  async deleteProject(id: string): Promise<boolean> {
    this.projects = this.projects.filter((p) => p.id !== id);
    this.conversations = this.conversations.filter((c) => c.project_id !== id);
    this.documents = this.documents.filter((d) => d.project_id !== id);
    this.notes = this.notes.filter((n) => n.project_id !== id);
    this.activity = this.activity.filter((a) => a.project_id !== id);
    this.saveToStorage();
    return true;
  }

  async getProjectNotes(projectId: string): Promise<ProjectNote[]> {
    this.loadFromStorage();
    return this.notes.filter((n) => n.project_id === projectId);
  }

  async createProjectNote(
    projectId: string,
    title: string,
    content: string,
    category: string = 'note'
  ): Promise<ProjectNote> {
    const note: ProjectNote = {
      id: `note-${generateUuid()}`,
      project_id: projectId,
      title,
      content,
      category: category as any,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    this.notes.unshift(note);
    this.activity.unshift({
      id: `act-${generateUuid()}`,
      project_id: projectId,
      action: 'note_saved',
      details: `Added ${category}: '${title}'`,
      created_at: new Date().toISOString(),
    });
    this.saveToStorage();
    return note;
  }

  async updateProjectNote(
    projectId: string,
    noteId: string,
    updates: Partial<{ title: string; content: string; category: string }>
  ): Promise<ProjectNote> {
    const idx = this.notes.findIndex((n) => n.id === noteId && n.project_id === projectId);
    if (idx === -1) throw new Error('Note not found');

    const updated = {
      ...this.notes[idx],
      ...updates,
      category: (updates.category as any) || this.notes[idx].category,
      updated_at: new Date().toISOString(),
    };
    this.notes[idx] = updated;
    this.saveToStorage();
    return updated;
  }

  async deleteProjectNote(projectId: string, noteId: string): Promise<boolean> {
    this.notes = this.notes.filter((n) => !(n.id === noteId && n.project_id === projectId));
    this.saveToStorage();
    return true;
  }

  async getProjectActivity(projectId: string): Promise<ProjectActivity[]> {
    this.loadFromStorage();
    return this.activity.filter((a) => a.project_id === projectId);
  }

  async getProjectDocuments(projectId: string): Promise<DocumentInfo[]> {
    this.loadFromStorage();
    return this.documents.filter((d) => d.project_id === projectId);
  }

  // ---------------------------------------------------------
  // Conversation Methods
  // ---------------------------------------------------------

  async getConversations(projectId?: string): Promise<Conversation[]> {
    this.loadFromStorage();
    if (projectId) {
      return this.conversations.filter((c) => c.project_id === projectId);
    }
    return this.conversations.filter((c) => !c.project_id);
  }

  async createConversation(
    title: string = 'New Conversation',
    model: string = 'qwen3.5:4b',
    projectId?: string
  ): Promise<Conversation> {
    const newConv: Conversation = {
      id: `conv-mock-${generateUuid().slice(0, 8)}`,
      title,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      model,
      project_id: projectId,
      message_count: 0,
      messages: [],
      documents: [],
    };
    this.conversations.unshift(newConv);
    this.saveToStorage();
    return newConv;
  }

  async getConversation(id: string): Promise<Conversation> {
    this.loadFromStorage();
    const conv = this.conversations.find((c) => c.id === id);
    if (!conv) throw new Error('Conversation not found');
    const docs = this.documents.filter((d) => d.conversation_id === id);
    return { ...conv, documents: docs };
  }

  async renameConversation(id: string, title: string): Promise<Conversation> {
    const conv = this.conversations.find((c) => c.id === id);
    if (!conv) throw new Error('Conversation not found');
    conv.title = title;
    conv.updated_at = new Date().toISOString();
    this.saveToStorage();
    return conv;
  }

  async deleteConversation(id: string): Promise<boolean> {
    this.conversations = this.conversations.filter((c) => c.id !== id);
    this.documents = this.documents.filter((d) => d.conversation_id !== id);
    this.saveToStorage();
    return true;
  }

  async uploadDocument(file: File, conversationId?: string, projectId?: string): Promise<DocumentInfo> {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      throw new Error('Invalid file format. Only PDF files (.pdf) are supported.');
    }
    if (file.size > 20 * 1024 * 1024) {
      throw new Error('File size exceeds the 20 MB limit.');
    }
    if (file.size === 0) {
      throw new Error('The uploaded file is empty (0 bytes).');
    }

    const doc: DocumentInfo = {
      id: `doc-mock-${generateUuid().slice(0, 8)}`,
      conversation_id: conversationId,
      project_id: projectId,
      filename: file.name,
      file_size: file.size,
      page_count: Math.max(1, Math.ceil(file.size / 50000)),
      char_count: file.size * 2,
      created_at: new Date().toISOString(),
      status: 'ready',
      extraction_status: 'success',
    };

    this.documents.push(doc);
    if (projectId) {
      this.activity.unshift({
        id: `act-${generateUuid()}`,
        project_id: projectId,
        action: 'document_uploaded',
        details: `Ingested paper '${file.name}'`,
        created_at: new Date().toISOString(),
      });
    }
    this.saveToStorage();
    return doc;
  }

  async getConversationDocuments(conversationId: string): Promise<DocumentInfo[]> {
    return this.documents.filter((d) => d.conversation_id === conversationId);
  }

  async deleteDocument(documentId: string): Promise<boolean> {
    this.documents = this.documents.filter((d) => d.id !== documentId);
    this.saveToStorage();
    return true;
  }

  async streamChat(
    payload: ChatStreamPayload,
    callbacks: ChatStreamCallbacks,
    signal?: AbortSignal
  ): Promise<void> {
    const userPrompt = payload.messages[payload.messages.length - 1]?.content || '';
    const docs = payload.project_id
      ? this.documents.filter((d) => d.project_id === payload.project_id || d.conversation_id === payload.conversation_id)
      : payload.conversation_id
      ? this.documents.filter((d) => d.conversation_id === payload.conversation_id)
      : [];

    // Simulate citations if documents are attached
    if (docs.length > 0) {
      const citations: Citation[] = docs.map((doc, i) => ({
        id: `cit-${i + 1}`,
        document_id: doc.id,
        filename: doc.filename,
        page_number: 1,
        excerpt: `Key finding from ${doc.filename}: Experimental methodology evaluated on Iris Xe and Core i5-1155G7 shows linear speedup under CPU quantization.`,
      }));
      callbacks.onCitations?.(citations);
    }

    const responseText = this.generateResponse(userPrompt, payload.model, docs, Boolean(payload.project_id));
    const tokens = responseText.match(/(\s+|\S+)/g) || [responseText];
    let accumulated = '';

    for (let i = 0; i < tokens.length; i++) {
      if (signal?.aborted) return;
      const token = tokens[i];
      accumulated += token;
      callbacks.onToken(token);

      const delay = token.includes('\n') ? 30 : token.match(/[.,!?:;]/) ? 25 : 12;
      await new Promise((resolve) => setTimeout(resolve, delay));
    }

    callbacks.onComplete(accumulated);
  }

  private generateResponse(
    prompt: string,
    model: string,
    attachedDocs: DocumentInfo[] = [],
    isResearchProject: boolean = false
  ): string {
    const lower = prompt.toLowerCase();

    if (isResearchProject && attachedDocs.length > 0) {
      const doc = attachedDocs[0];
      return `### Academic Evaluation & Synthesis

Based on the uploaded research paper **${doc.filename}** (p. 1):

1. **Empirical Evidence**:
   The methodology establishes robust convergence when optimizing with cross-entropy loss:
   \\[
   \\mathcal{L}_{\\text{CE}} = -\\sum_{i=1}^{C} y_i \\log(\\hat{y}_i)
   \\]
   where \\(C\\) is the number of target classes and \\(\\hat{y}_i\\) is the Softmax output distribution.

2. **Methodological Assumptions**:
   The authors assume identically and independently distributed (i.i.d.) validation samples without distribution shift.

3. **Performance Metrics**:
   Evaluation on balanced test splits reports an \\(F_1\\)-score of \\(0.924\\), defined as:
   \\[
   F_1 = 2 \\cdot \\frac{\\text{Precision} \\cdot \\text{Recall}}{\\text{Precision} + \\text{Recall}}
   \\]

*Citation: [1] ${doc.filename}, Page 1.*`;
    }

    if (attachedDocs.length > 0) {
      const doc = attachedDocs[0];
      if (lower.includes('unknown') || lower.includes('absent')) {
        return `The attached document(s) do not contain sufficient evidence to answer this question.`;
      }
      return `According to **${doc.filename}** (Page 1):
The document details local preprocessing and factual guidelines. All analysis was conducted privately on your device.`;
    }

    if (lower.includes('roc') || lower.includes('confusion') || lower.includes('evaluation')) {
      return `### Model Evaluation & Confusion Matrix Breakdown

In deep learning and statistical classification:

- **Precision**: \\(\\frac{\\text{TP}}{\\text{TP} + \\text{FP}}\\) (measures exactness of positive calls)
- **Recall**: \\(\\frac{\\text{TP}}{\\text{TP} + \\text{FN}}\\) (measures sensitivity or coverage)
- **ROC-AUC**: Area under the Receiver Operating Characteristic curve, measuring True Positive Rate versus False Positive Rate across all discrimination thresholds.`;
    }

    return `This is a simulated Dev Mock response for **${model}**. 
In real backend mode, Moso AI executes this request via **Qwen 3.5 2B** running on your local CPU with Ollama and saves your messages and citations to SQLite (\`backend/moso.db\`).`;
  }
}

export const mockService = new MockService();
