import { Conversation, DocumentInfo, HealthResponse, Message, ModelInfo } from '../types';
import { ChatStreamCallbacks, ChatStreamPayload } from './api';

const MOCK_STORAGE_KEY = 'moso_mock_conversations_v1';
const MOCK_DOCS_KEY = 'moso_mock_documents_v1';

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
    id: 'qwen3.5:2b',
    name: 'Qwen 3.5 2B',
    description: 'Default local model for everyday assistance and coding (Ollama)',
    size: '1.9 GB',
    parameters: '2B',
    family: 'qwen35',
    provider: 'ollama',
    is_local: true,
    is_default: true,
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

  constructor() {
    this.loadFromStorage();
  }

  private loadFromStorage() {
    try {
      const stored = localStorage.getItem(MOCK_STORAGE_KEY);
      if (stored) {
        this.conversations = JSON.parse(stored);
      } else {
        this.conversations = [...INITIAL_MOCK_CONVERSATIONS];
        this.saveToStorage();
      }

      const storedDocs = localStorage.getItem(MOCK_DOCS_KEY);
      if (storedDocs) {
        this.documents = JSON.parse(storedDocs);
      } else {
        this.documents = [];
      }
    } catch {
      this.conversations = [...INITIAL_MOCK_CONVERSATIONS];
      this.documents = [];
    }
  }

  private saveToStorage() {
    try {
      localStorage.setItem(MOCK_STORAGE_KEY, JSON.stringify(this.conversations));
      localStorage.setItem(MOCK_DOCS_KEY, JSON.stringify(this.documents));
    } catch (e) {
      console.warn('Failed to persist mock data to localStorage', e);
    }
  }

  async checkHealth(): Promise<HealthResponse> {
    return {
      status: 'ok',
      ollama_connected: true,
      active_model: 'qwen3.5:2b',
      version: '0.1.0-mock',
      models_available: 1,
      uptime_seconds: 3420,
      latency_ms: 8,
    };
  }

  async getModels(): Promise<ModelInfo[]> {
    return [...MOCK_MODELS];
  }

  async getConversations(): Promise<Conversation[]> {
    this.loadFromStorage();
    return this.conversations.map((c) => ({
      ...c,
      message_count: c.messages?.length || 0,
      documents: this.documents.filter((d) => d.conversation_id === c.id),
    }));
  }

  async getConversation(id: string): Promise<Conversation> {
    this.loadFromStorage();
    const found = this.conversations.find((c) => c.id === id);
    if (!found) {
      throw new Error(`Conversation not found in mock store: ${id}`);
    }
    const convCopy: Conversation = JSON.parse(JSON.stringify(found));
    convCopy.documents = this.documents.filter((d) => d.conversation_id === id);
    return convCopy;
  }

  async createConversation(title: string = 'New Conversation', model: string = 'qwen3.5:2b'): Promise<Conversation> {
    this.loadFromStorage();
    const newConv: Conversation = {
      id: `conv_${generateUuid()}`,
      title: title || 'New Conversation',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      model,
      message_count: 0,
      messages: [],
      documents: [],
    };
    this.conversations.unshift(newConv);
    this.saveToStorage();
    return newConv;
  }

  async updateConversationTitle(id: string, title: string): Promise<Conversation> {
    this.loadFromStorage();
    const conv = this.conversations.find((c) => c.id === id);
    if (conv) {
      conv.title = title;
      conv.updated_at = new Date().toISOString();
      this.saveToStorage();
      return { ...conv };
    }
    throw new Error('Conversation not found');
  }

  async renameConversation(id: string, title: string): Promise<Conversation> {
    return this.updateConversationTitle(id, title);
  }

  async saveMessage(conversationId: string, message: Message): Promise<void> {
    this.loadFromStorage();
    const conv = this.conversations.find((c) => c.id === conversationId);
    if (conv) {
      if (!conv.messages) conv.messages = [];
      conv.messages.push(message);
      conv.updated_at = new Date().toISOString();
      if (conv.title === 'New Conversation' && message.role === 'user') {
        conv.title = message.content.slice(0, 36) + (message.content.length > 36 ? '...' : '');
      }
      this.saveToStorage();
    }
  }

  async deleteConversation(id: string): Promise<boolean> {
    this.loadFromStorage();
    this.conversations = this.conversations.filter((c) => c.id !== id);
    this.documents = this.documents.filter((d) => d.conversation_id !== id);
    this.saveToStorage();
    return true;
  }

  async clearAllConversations(): Promise<void> {
    this.conversations = [];
    this.documents = [];
    this.saveToStorage();
  }

  async uploadDocument(file: File, conversationId?: string): Promise<DocumentInfo> {
    this.loadFromStorage();

    // Validate size and format in mock
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      throw new Error('Invalid file format. Only PDF files (.pdf) are supported.');
    }
    if (file.size > 20 * 1024 * 1024) {
      throw new Error('File size exceeds the 20 MB limit.');
    }

    let targetConvId = conversationId;
    if (!targetConvId) {
      const newConv = await this.createConversation(`Doc: ${file.name.slice(0, 30)}`);
      targetConvId = newConv.id;
    }

    const docInfo: DocumentInfo = {
      id: `doc_${generateUuid()}`,
      conversation_id: targetConvId,
      filename: file.name,
      file_size: file.size,
      page_count: Math.max(1, Math.ceil(file.size / (100 * 1024))),
      char_count: file.size * 2,
      created_at: new Date().toISOString(),
      status: 'ready',
    };

    this.documents.push(docInfo);
    this.saveToStorage();
    return docInfo;
  }

  async getConversationDocuments(conversationId: string): Promise<DocumentInfo[]> {
    this.loadFromStorage();
    return this.documents.filter((d) => d.conversation_id === conversationId);
  }

  async deleteDocument(documentId: string): Promise<boolean> {
    this.loadFromStorage();
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
    const docs = payload.conversation_id
      ? this.documents.filter((d) => d.conversation_id === payload.conversation_id)
      : [];

    const responseText = this.generateResponse(userPrompt, payload.model, docs);

    const tokens = responseText.match(/(\s+|\S+)/g) || [responseText];
    let accumulated = '';

    for (let i = 0; i < tokens.length; i++) {
      if (signal?.aborted) {
        return;
      }
      const token = tokens[i];
      accumulated += token;
      callbacks.onToken(token);

      const delay = token.includes('\n') ? 35 : token.match(/[.,!?:;]/) ? 30 : 15;
      await new Promise((resolve) => setTimeout(resolve, delay));
    }

    callbacks.onComplete(accumulated);
  }

  private generateResponse(prompt: string, model: string, attachedDocs: DocumentInfo[] = []): string {
    const lower = prompt.toLowerCase();

    if (attachedDocs.length > 0) {
      const doc = attachedDocs[0];
      if (lower.includes('summary') || lower.includes('what is') || lower.includes('about')) {
        return `Based on the attached document **${doc.filename}** (Page 1):

The document outlines key principles and data relevant to your query. All processing for this document occurred entirely locally on your machine with zero external network transmission.

Is there a specific section or topic from **${doc.filename}** you would like to explore further?`;
      }
      if (lower.includes('unknown') || lower.includes('absent') || lower.includes('xyz123')) {
        return `The attached document does not contain this information.`;
      }
      return `According to **${doc.filename}** (Page 1):

The document addresses this with specific guidelines and structured analysis. If you require further clarification from specific sections, let me know!`;
    }

    if (lower.includes('code') || lower.includes('typescript') || lower.includes('python')) {
      return `Here is a clean implementation:

\`\`\`python
# Local SQLite message insertion
import sqlite3
import uuid

def save_message(db_path: str, conv_id: str, role: str, content: str):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    msg_id = f"msg_{uuid.uuid4()}"
    c.execute(
        "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
        (msg_id, conv_id, role, content)
    )
    conn.commit()
    conn.close()
    return msg_id
\`\`\`

- **Reliable UUIDs**: Prevents collision.
- **Ordered schema**: Indexed on \`(conversation_id, created_at, rowid)\`.`;
    }

    return `This is a simulated Dev Mock response for **${model}**. 

In real backend mode, Moso AI executes this request via **Qwen 3.5 2B** running on your local CPU with Ollama and saves your messages to SQLite (\`backend/moso.db\`).`;
  }
}

export const mockService = new MockService();
