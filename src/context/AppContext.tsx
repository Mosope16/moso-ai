import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { AppSettings, ConnectionState, Conversation, DocumentInfo, HealthResponse, Message, ModelInfo } from '../types';
import { api } from '../services/api';
import { mockService, MOCK_MODELS } from '../services/mockService';

interface AppContextType {
  // State
  conversations: Conversation[];
  activeConversationId: string | null;
  activeConversation: Conversation | null;
  messages: Message[];
  documents: DocumentInfo[];
  isGenerating: boolean;
  isUploadingDocument: boolean;
  uploadError: string | null;
  selectedModel: string;
  availableModels: ModelInfo[];
  connectionState: ConnectionState;
  healthInfo: HealthResponse | null;
  isMockMode: boolean;
  isSidebarOpen: boolean;
  isSettingsOpen: boolean;
  settings: AppSettings;
  searchQuery: string;
  errorNotification: string | null;

  // Actions
  sendMessage: (content: string) => Promise<void>;
  stopGeneration: () => void;
  regenerateLastResponse: () => Promise<void>;
  selectConversation: (id: string) => Promise<void>;
  createNewConversation: () => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;
  renameConversation: (id: string, title: string) => Promise<void>;
  uploadDocument: (file: File) => Promise<DocumentInfo | null>;
  removeDocument: (documentId: string) => Promise<void>;
  clearUploadError: () => void;
  setSelectedModel: (modelId: string) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  openSettings: () => void;
  closeSettings: () => void;
  updateSettings: (newSettings: Partial<AppSettings>) => void;
  toggleMockMode: () => void;
  checkConnection: () => Promise<void>;
  setSearchQuery: (query: string) => void;
  clearErrorNotification: () => void;
  clearAllHistory: () => Promise<void>;
}

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

const DEFAULT_SETTINGS: AppSettings = {
  general: {
    username: 'Developer',
    systemPrompt: 'You are Moso AI, a helpful, precise, and private personal AI assistant running locally.',
    sendShortcut: 'enter',
  },
  appearance: {
    theme: 'dark',
    fontSize: 'medium',
    codeLigatures: true,
    compactMessages: false,
    showTimestamps: true,
  },
  models: {
    defaultModel: 'qwen3.5:2b',
    temperature: 0.7,
    topP: 0.9,
    maxTokens: 256,
    contextWindow: 262144,
  },
  localAi: {
    apiEndpoint: '/api/v1',
    ollamaEndpoint: 'http://127.0.0.1:11434',
    autoDetect: true,
  },
  privacy: {
    zeroTelemetry: true,
    localStorageOnly: true,
  },
};

const SETTINGS_KEY = 'moso_app_settings_v1';
const MOCK_MODE_KEY = 'moso_dev_mock_mode_v1';

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Saved settings
  const [settings, setSettings] = useState<AppSettings>(() => {
    try {
      const saved = localStorage.getItem(SETTINGS_KEY);
      return saved ? { ...DEFAULT_SETTINGS, ...JSON.parse(saved) } : DEFAULT_SETTINGS;
    } catch {
      return DEFAULT_SETTINGS;
    }
  });

  // Mock mode preference: defaults to false so real backend & SQLite are used
  const [isMockMode, setIsMockMode] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem(MOCK_MODE_KEY);
      return saved !== null ? JSON.parse(saved) : false;
    } catch {
      return false;
    }
  });

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isUploadingDocument, setIsUploadingDocument] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('qwen3.5:2b');
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>(MOCK_MODELS);
  const [connectionState, setConnectionState] = useState<ConnectionState>('connecting');
  const [healthInfo, setHealthInfo] = useState<HealthResponse | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [errorNotification, setErrorNotification] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Sync settings
  useEffect(() => {
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    } catch (e) {
      console.warn('Failed to save settings to localStorage', e);
    }
  }, [settings]);

  // Sync mock mode preference
  useEffect(() => {
    try {
      localStorage.setItem(MOCK_MODE_KEY, JSON.stringify(isMockMode));
    } catch (e) {
      console.warn('Failed to save mock mode to localStorage', e);
    }
  }, [isMockMode]);

  // Active conversation object
  const activeConversation = conversations.find((c) => c.id === activeConversationId) || null;

  // Check backend connection or fall back to mock
  const checkConnection = useCallback(async () => {
    setConnectionState('connecting');

    if (isMockMode) {
      try {
        const mockHealth = await mockService.checkHealth();
        setHealthInfo(mockHealth);
        setConnectionState('connected');
        const models = await mockService.getModels();
        setAvailableModels(models);
        setErrorNotification(null);
      } catch {
        setConnectionState('disconnected');
      }
      return;
    }

    // Live backend check
    try {
      api.setBaseUrl(settings.localAi.apiEndpoint);
      const health = await api.checkHealth();
      setHealthInfo(health);

      if (health.status === 'ok') {
        setConnectionState('connected');
        setErrorNotification(null);
      } else if (health.ollama_connected === false) {
        setConnectionState('disconnected');
        setErrorNotification('Ollama is unreachable at ' + settings.localAi.ollamaEndpoint);
      } else {
        setConnectionState('connected');
      }

      const models = await api.getModels();
      if (models.length > 0) {
        setAvailableModels(models);
        if (!models.some((m) => m.id === selectedModel)) {
          setSelectedModel(models[0].id);
        }
      }
    } catch (err: any) {
      setConnectionState('disconnected');
      setHealthInfo({
        status: 'error',
        ollama_connected: false,
      });
      setErrorNotification('Backend unreachable at ' + settings.localAi.apiEndpoint);
    }
  }, [isMockMode, settings.localAi.apiEndpoint, settings.localAi.ollamaEndpoint, selectedModel]);

  // Load conversations on mount or mode change
  const loadConversations = useCallback(async () => {
    try {
      if (isMockMode) {
        const convs = await mockService.getConversations();
        setConversations(convs);
      } else {
        const convs = await api.getConversations();
        setConversations(convs);
      }
    } catch (err: any) {
      console.warn('Error loading conversations:', err);
    }
  }, [isMockMode]);

  // Initial load
  useEffect(() => {
    checkConnection();
    loadConversations();
  }, [checkConnection, loadConversations]);

  // Select conversation and load its messages and attached documents
  const selectConversation = async (id: string) => {
    if (isGenerating) {
      stopGeneration();
    }
    setActiveConversationId(id);
    setUploadError(null);
    try {
      if (isMockMode) {
        const conv = await mockService.getConversation(id);
        setMessages(conv.messages || []);
        setDocuments(conv.documents || []);
        if (conv.model) setSelectedModel(conv.model);
      } else {
        const conv = await api.getConversation(id);
        setMessages(conv.messages || []);
        setDocuments(conv.documents || []);
        if (conv.model) setSelectedModel(conv.model);
      }
    } catch (err: any) {
      setErrorNotification('Failed to load conversation: ' + (err.message || 'Unknown error'));
      setMessages([]);
      setDocuments([]);
    }
  };

  // Create new conversation
  const createNewConversation = async () => {
    if (isGenerating) {
      stopGeneration();
    }
    setActiveConversationId(null);
    setMessages([]);
    setDocuments([]);
    setUploadError(null);
  };

  // Upload and attach PDF document
  const uploadDocument = async (file: File): Promise<DocumentInfo | null> => {
    setIsUploadingDocument(true);
    setUploadError(null);

    // 1. Client-side extension check
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      const err = 'Invalid file format. Only PDF files (.pdf) are supported.';
      setUploadError(err);
      setErrorNotification(err);
      setIsUploadingDocument(false);
      return null;
    }

    // 2. Client-side size check (20 MB limit)
    if (file.size > 20 * 1024 * 1024) {
      const err = 'File size exceeds the 20 MB limit.';
      setUploadError(err);
      setErrorNotification(err);
      setIsUploadingDocument(false);
      return null;
    }

    if (file.size === 0) {
      const err = 'The selected file is empty (0 bytes).';
      setUploadError(err);
      setErrorNotification(err);
      setIsUploadingDocument(false);
      return null;
    }

    try {
      const service = isMockMode ? mockService : api;
      const doc = await service.uploadDocument(file, activeConversationId || undefined);

      // If backend created a new conversation for this document
      if (!activeConversationId && doc.conversation_id) {
        setActiveConversationId(doc.conversation_id);
        await loadConversations();
      }

      setDocuments((prev) => [...prev.filter((d) => d.id !== doc.id), doc]);
      setIsUploadingDocument(false);
      return doc;
    } catch (err: any) {
      const msg = err.message || 'Failed to upload and process PDF.';
      setUploadError(msg);
      setErrorNotification(msg);
      setIsUploadingDocument(false);
      return null;
    }
  };

  // Remove attached document
  const removeDocument = async (documentId: string): Promise<void> => {
    try {
      const service = isMockMode ? mockService : api;
      await service.deleteDocument(documentId);
      setDocuments((prev) => prev.filter((d) => d.id !== documentId));
      setConversations((prev) =>
        prev.map((c) =>
          c.id === activeConversationId
            ? { ...c, documents: (c.documents || []).filter((d) => d.id !== documentId) }
            : c
        )
      );
    } catch (err: any) {
      setErrorNotification('Failed to delete document: ' + (err.message || 'Error'));
    }
  };

  const clearUploadError = () => setUploadError(null);

  // Delete conversation
  const deleteConversation = async (id: string) => {
    try {
      if (isMockMode) {
        await mockService.deleteConversation(id);
      } else {
        await api.deleteConversation(id);
      }
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeConversationId === id) {
        setActiveConversationId(null);
        setMessages([]);
        setDocuments([]);
      }
    } catch (err: any) {
      setErrorNotification('Failed to delete conversation: ' + (err.message || 'Error'));
    }
  };

  // Rename conversation
  const renameConversation = async (id: string, newTitle: string) => {
    const trimmed = newTitle.trim();
    if (!trimmed) return;

    try {
      if (isMockMode) {
        await mockService.renameConversation(id, trimmed);
      } else {
        await api.renameConversation(id, trimmed);
      }
      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, title: trimmed, updated_at: new Date().toISOString() } : c))
      );
    } catch (err: any) {
      setErrorNotification('Failed to update title: ' + (err.message || 'Error'));
    }
  };

  // Stop active generation
  const stopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsGenerating(false);
    setConnectionState((prev) => (prev === 'generating' ? 'connected' : prev));
  };

  // Send message
  const sendMessage = async (content: string) => {
    const trimmed = content.trim();
    if (!trimmed || isGenerating) return;

    let targetConvId = activeConversationId;

    // Create conversation on first message if none active
    if (!targetConvId) {
      const generatedTitle = trimmed.slice(0, 36) + (trimmed.length > 36 ? '...' : '');
      try {
        let created: Conversation;
        if (isMockMode) {
          created = await mockService.createConversation(generatedTitle, selectedModel);
        } else {
          created = await api.createConversation(generatedTitle, selectedModel);
        }
        targetConvId = created.id;
        setActiveConversationId(created.id);
        setConversations((prev) => [created, ...prev]);
      } catch (err: any) {
        // Fallback local UUID
        targetConvId = `conv_${generateUuid()}`;
        const localConv: Conversation = {
          id: targetConvId,
          title: generatedTitle,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          model: selectedModel,
          messages: [],
          documents: [],
        };
        setActiveConversationId(targetConvId);
        setConversations((prev) => [localConv, ...prev]);
      }
    }

    const userMsgId = `msg_${generateUuid()}`;
    const assistantMsgId = `msg_${generateUuid()}`;
    const nowIso = new Date().toISOString();

    const userMsg: Message = {
      id: userMsgId,
      conversation_id: targetConvId!,
      role: 'user',
      content: trimmed,
      created_at: nowIso,
    };

    const assistantMsgPlaceholder: Message = {
      id: assistantMsgId,
      conversation_id: targetConvId!,
      role: 'assistant',
      content: '',
      created_at: nowIso,
      is_streaming: true,
      model: selectedModel,
    };

    const updatedMessages = [...messages, userMsg, assistantMsgPlaceholder];
    setMessages(updatedMessages);
    setIsGenerating(true);
    setConnectionState('generating');

    // Save user message in mock mode
    if (isMockMode && targetConvId) {
      await mockService.saveMessage(targetConvId, userMsg);
    }

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    const streamService = isMockMode ? mockService : api;

    const chatHistory = updatedMessages
      .filter((m) => m.id !== assistantMsgPlaceholder.id)
      .map((m) => ({ role: m.role, content: m.content }));

    let streamedText = '';

    await streamService.streamChat(
      {
        conversation_id: targetConvId,
        model: selectedModel,
        messages: chatHistory,
        max_tokens: settings.models.maxTokens || 256,
        temperature: settings.models.temperature ?? 0.7,
      },
      {
        onToken: (token: string) => {
          streamedText += token;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgPlaceholder.id
                ? { ...msg, content: streamedText, is_streaming: true }
                : msg
            )
          );
        },
        onComplete: async (fullText: string) => {
          setIsGenerating(false);
          setConnectionState('connected');
          const finalAssistantMsg: Message = {
            ...assistantMsgPlaceholder,
            content: fullText,
            is_streaming: false,
          };

          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgPlaceholder.id ? finalAssistantMsg : msg
            )
          );

          if (isMockMode && targetConvId) {
            await mockService.saveMessage(targetConvId, finalAssistantMsg);
          }

          // Update conversation timestamp & title
          setConversations((prev) =>
            prev.map((c) =>
              c.id === targetConvId
                ? {
                    ...c,
                    updated_at: new Date().toISOString(),
                    title:
                      c.title === 'New Conversation'
                        ? trimmed.slice(0, 36) + (trimmed.length > 36 ? '...' : '')
                        : c.title,
                  }
                : c
            )
          );

          abortControllerRef.current = null;
        },
        onError: (err: Error) => {
          setIsGenerating(false);
          setConnectionState(isMockMode ? 'connected' : 'disconnected');
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgPlaceholder.id
                ? {
                    ...msg,
                    content: msg.content || '',
                    is_streaming: false,
                    error: err.message || 'Stream interrupted',
                  }
                : msg
            )
          );
          setErrorNotification(err.message);
          abortControllerRef.current = null;
        },
      },
      abortController.signal
    );
  };

  // Regenerate last assistant response
  const regenerateLastResponse = async () => {
    if (isGenerating || messages.length === 0) return;

    let lastUserIndex = -1;
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        lastUserIndex = i;
        break;
      }
    }

    if (lastUserIndex === -1) return;

    const userPrompt = messages[lastUserIndex].content;
    const trimmedMessages = messages.slice(0, lastUserIndex);
    setMessages(trimmedMessages);

    await sendMessage(userPrompt);
  };

  const toggleSidebar = () => setIsSidebarOpen((prev) => !prev);
  const openSettings = () => setIsSettingsOpen(true);
  const closeSettings = () => setIsSettingsOpen(false);

  const updateSettings = (partial: Partial<AppSettings>) => {
    setSettings((prev) => ({
      ...prev,
      ...partial,
      general: { ...prev.general, ...partial.general },
      appearance: { ...prev.appearance, ...partial.appearance },
      models: { ...prev.models, ...partial.models },
      localAi: { ...prev.localAi, ...partial.localAi },
      privacy: { ...prev.privacy, ...partial.privacy },
    }));
  };

  const toggleMockMode = () => {
    setIsMockMode((prev) => !prev);
  };

  const clearErrorNotification = () => setErrorNotification(null);

  const clearAllHistory = async () => {
    if (isMockMode) {
      await mockService.clearAllConversations();
    } else {
      for (const conv of conversations) {
        try {
          await api.deleteConversation(conv.id);
        } catch {
          // continue
        }
      }
    }
    setConversations([]);
    setActiveConversationId(null);
    setMessages([]);
    setDocuments([]);
  };

  return (
    <AppContext.Provider
      value={{
        conversations,
        activeConversationId,
        activeConversation,
        messages,
        documents,
        isGenerating,
        isUploadingDocument,
        uploadError,
        selectedModel,
        availableModels,
        connectionState,
        healthInfo,
        isMockMode,
        isSidebarOpen,
        isSettingsOpen,
        settings,
        searchQuery,
        errorNotification,
        sendMessage,
        stopGeneration,
        regenerateLastResponse,
        selectConversation,
        createNewConversation,
        deleteConversation,
        renameConversation,
        uploadDocument,
        removeDocument,
        clearUploadError,
        setSelectedModel,
        toggleSidebar,
        setSidebarOpen: setIsSidebarOpen,
        openSettings,
        closeSettings,
        updateSettings,
        toggleMockMode,
        checkConnection,
        setSearchQuery,
        clearErrorNotification,
        clearAllHistory,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
