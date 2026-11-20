import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import {
  AppSettings,
  Citation,
  ConnectionState,
  Conversation,
  DocumentInfo,
  HealthResponse,
  Message,
  ModelInfo,
  Project,
  ProjectActivity,
  ProjectNote,
  StreamStatus,
  VerificationReport,
  WorkspaceMode,
} from '../types';
import { api } from '../services/api';
import { mockService, MOCK_MODELS } from '../services/mockService';

interface AppContextType {
  // State
  workspaceMode: WorkspaceMode;
  setWorkspaceMode: (mode: WorkspaceMode) => void;
  conversations: Conversation[];
  activeConversationId: string | null;
  activeConversation: Conversation | null;
  messages: Message[];
  documents: DocumentInfo[];
  projects: Project[];
  activeProjectId: string | null;
  activeProject: Project | null;
  projectNotes: ProjectNote[];
  projectActivity: ProjectActivity[];
  projectDocuments: DocumentInfo[];
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
  webSearchEnabled: boolean;
  setWebSearchEnabled: (enabled: boolean) => void;
  activeStreamStatus: StreamStatus | null;

  // Actions
  sendMessage: (content: string) => Promise<void>;
  stopGeneration: () => void;
  regenerateLastResponse: () => Promise<void>;
  selectConversation: (id: string) => Promise<void>;
  createNewConversation: (projectId?: string) => Promise<void>;
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

  // Project Actions
  selectProject: (id: string | null) => Promise<void>;
  createProject: (name: string, description?: string, instructions?: string) => Promise<Project | null>;
  updateProject: (id: string, updates: Partial<{ name: string; description: string; instructions: string }>) => Promise<void>;
  deleteProject: (id: string) => Promise<void>;
  saveProjectNote: (title: string, content: string, category?: string) => Promise<void>;
  deleteProjectNote: (noteId: string) => Promise<void>;
  uploadProjectDocument: (file: File) => Promise<DocumentInfo | null>;
  loadProjects: () => Promise<void>;
  loadProjectDetails: (projectId: string) => Promise<void>;

  // Public Tester Authentication
  isAuthRequired: boolean;
  isAuthenticated: boolean;
  loginWithPassword: (password: string) => Promise<boolean>;
  logoutSession: () => Promise<void>;
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
    username: 'Researcher',
    systemPrompt: 'You are Moso AI, a helpful, precise, and private personal AI assistant running locally.',
    sendShortcut: 'enter',
  },
  appearance: {
    theme: 'system',
    fontSize: 'medium',
    codeLigatures: true,
    compactMessages: false,
    showTimestamps: true,
  },
  models: {
    defaultModel: 'qwen3.5:4b',
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
const WORKSPACE_MODE_KEY = 'moso_workspace_mode_v1';

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [workspaceMode, setWorkspaceModeState] = useState<WorkspaceMode>(() => {
    try {
      const saved = localStorage.getItem(WORKSPACE_MODE_KEY);
      return saved === 'project' ? 'project' : 'chat';
    } catch {
      return 'chat';
    }
  });

  const setWorkspaceMode = (mode: WorkspaceMode) => {
    setWorkspaceModeState(mode);
    try {
      localStorage.setItem(WORKSPACE_MODE_KEY, mode);
    } catch {}
  };

  // Saved settings
  const [settings, setSettings] = useState<AppSettings>(() => {
    try {
      const saved = localStorage.getItem(SETTINGS_KEY);
      return saved ? { ...DEFAULT_SETTINGS, ...JSON.parse(saved) } : DEFAULT_SETTINGS;
    } catch {
      return DEFAULT_SETTINGS;
    }
  });

  // Apply the chosen theme to <html>. "system" follows the OS and updates live.
  useEffect(() => {
    const pref = settings.appearance.theme;
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const apply = () => {
      const dark =
        pref === 'light' ? false : pref === 'dark' || pref === 'oled' || pref === 'zinc' ? true : media.matches;
      document.documentElement.classList.toggle('dark', dark);
      document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
    };
    apply();
    media.addEventListener('change', apply);
    return () => media.removeEventListener('change', apply);
  }, [settings.appearance.theme]);

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

  // Project Workspace State
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [projectNotes, setProjectNotes] = useState<ProjectNote[]>([]);
  const [projectActivity, setProjectActivity] = useState<ProjectActivity[]>([]);
  const [projectDocuments, setProjectDocuments] = useState<DocumentInfo[]>([]);

  const [isGenerating, setIsGenerating] = useState(false);
  const [isUploadingDocument, setIsUploadingDocument] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('qwen3.5:4b');
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>(MOCK_MODELS);
  const [connectionState, setConnectionState] = useState<ConnectionState>('connecting');
  const [healthInfo, setHealthInfo] = useState<HealthResponse | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth >= 768;
    }
    return false;
  });
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [errorNotification, setErrorNotification] = useState<string | null>(null);

  // Web Retrieval State
  const [webSearchEnabled, setWebSearchEnabledState] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem('moso_web_search_enabled');
      return saved !== null ? JSON.parse(saved) : true;
    } catch {
      return true;
    }
  });

  const handleSetSelectedModel = useCallback(
    (modelId: string) => {
      setSelectedModel(modelId);
      if (activeConversationId) {
        setConversations((prev) =>
          prev.map((c) => (c.id === activeConversationId ? { ...c, model: modelId } : c))
        );
        if (!isMockMode) {
          api.updateConversationModel(activeConversationId, modelId).catch(() => {});
        }
      }
    },
    [activeConversationId, isMockMode]
  );

  const setWebSearchEnabled = (enabled: boolean) => {
    setWebSearchEnabledState(enabled);
    try {
      localStorage.setItem('moso_web_search_enabled', JSON.stringify(enabled));
    } catch {}
  };

  const [activeStreamStatus, setActiveStreamStatus] = useState<StreamStatus | null>(null);

  // Tester Authentication State
  const [isAuthRequired, setIsAuthRequired] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(true);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Register unauthorized callback from api service
  useEffect(() => {
    api.setOnUnauthorized(() => {
      setIsAuthRequired(true);
      setIsAuthenticated(false);
    });
  }, []);

  // Handle responsive viewport transitions between mobile (< 768px) and desktop (>= 768px)
  useEffect(() => {
    let lastWidth = typeof window !== 'undefined' ? window.innerWidth : 1024;
    const handleResize = () => {
      const currentWidth = window.innerWidth;
      if (lastWidth >= 768 && currentWidth < 768) {
        // Transitioning from desktop to mobile: ensure drawer starts closed
        setIsSidebarOpen(false);
      } else if (lastWidth < 768 && currentWidth >= 768) {
        // Transitioning from mobile to desktop: restore sidebar in normal layout
        setIsSidebarOpen(true);
      }
      lastWidth = currentWidth;
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Active conversation object
  const activeConversation = conversations.find((c) => c.id === activeConversationId) || null;
  // Active project object
  const activeProject = projects.find((p) => p.id === activeProjectId) || null;

  // Load conversations from SQLite or MockService
  const loadConversations = useCallback(
    async (projId?: string | null) => {
      try {
        const service = isMockMode ? mockService : api;
        const convList = await service.getConversations(projId || undefined);
        setConversations(convList);
      } catch (err: any) {
        console.warn('Failed to load conversations:', err);
      }
    },
    [isMockMode]
  );

  // Load projects from SQLite or MockService
  const loadProjects = useCallback(async () => {
    try {
      const service = isMockMode ? mockService : api;
      const projList = await service.getProjects();
      setProjects(projList);
    } catch (err: any) {
      console.warn('Failed to load projects:', err);
    }
  }, [isMockMode]);

  // Load project details (notes, documents, activity)
  const loadProjectDetails = useCallback(
    async (projId: string) => {
      try {
        const service = isMockMode ? mockService : api;
        const projData = await service.getProject(projId);
        setProjectNotes(projData.notes || []);
        setProjectDocuments(projData.documents || []);
        setProjectActivity(projData.activity || []);
      } catch (err: any) {
        console.warn('Failed to load project details:', err);
      }
    },
    [isMockMode]
  );

  // Check health, auth status, and models
  const checkConnection = useCallback(async () => {
    setConnectionState('connecting');
    try {
      if (isMockMode) {
        const health = await mockService.checkHealth();
        setHealthInfo(health);
        setAvailableModels(MOCK_MODELS);
        setConnectionState('connected');
        return;
      }

      // Check tester auth status
      try {
        const authStatus = await api.getAuthStatus();
        setIsAuthRequired(authStatus.auth_required);
        setIsAuthenticated(authStatus.authenticated);
        if (authStatus.auth_required && !authStatus.authenticated) {
          setConnectionState('connected');
          return;
        }
      } catch (authErr) {
        // If auth status endpoint fails, fall through to health check
      }

      const health = await api.checkHealth();
      setHealthInfo(health);

      const models = await api.getModels();
      if (models.length > 0) {
        setAvailableModels(models);
        if (!models.some((m) => m.id === selectedModel)) {
          const def = models.find((m) => m.is_default) || models[0];
          setSelectedModel(def.id);
        }
      }

      setConnectionState(health.ollama_connected ? 'connected' : 'disconnected');
      if (!health.ollama_connected) {
        setErrorNotification('Ollama is unreachable at http://127.0.0.1:11434. Ensure Ollama is running.');
      }
    } catch (err: any) {
      setConnectionState('disconnected');
      setErrorNotification(`Backend connection failed: ${err.message || 'Cannot reach API'}`);
    }
  }, [isMockMode, selectedModel]);

  // Login with tester password
  const loginWithPassword = async (password: string): Promise<boolean> => {
    try {
      const res = await api.login(password);
      if (res.status === 'ok') {
        setIsAuthenticated(true);
        setErrorNotification(null);
        await checkConnection();
        await loadConversations(activeProjectId);
        await loadProjects();
        return true;
      }
      return false;
    } catch (err: any) {
      throw err;
    }
  };

  // Logout session
  const logoutSession = async () => {
    try {
      await api.logout();
    } finally {
      setIsAuthenticated(false);
      setIsAuthRequired(true);
    }
  };

  // Initial mount
  useEffect(() => {
    checkConnection();
    loadConversations(activeProjectId);
    loadProjects();
  }, [checkConnection, loadConversations, loadProjects, activeProjectId]);

  // Periodic health check
  useEffect(() => {
    if (isMockMode) return;
    const interval = setInterval(() => {
      if (!isGenerating) {
        checkConnection();
      }
    }, 15000);
    return () => clearInterval(interval);
  }, [checkConnection, isGenerating, isMockMode]);

  // Select conversation and load its messages, citations, and attached documents
  const selectConversation = async (id: string) => {
    if (isGenerating) {
      stopGeneration();
    }
    setActiveConversationId(id);
    setUploadError(null);
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setIsSidebarOpen(false);
    }
    try {
      const service = isMockMode ? mockService : api;
      const conv = await service.getConversation(id);
      setMessages(conv.messages || []);
      setDocuments(conv.documents || []);
      if (conv.model) setSelectedModel(conv.model);
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
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setIsSidebarOpen(false);
    }
  };

  // Upload and attach PDF document to conversation or project
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
      const doc = await service.uploadDocument(
        file,
        activeConversationId || undefined,
        activeProjectId || undefined
      );

      // If backend created a new conversation for this document
      if (!activeConversationId && doc.conversation_id) {
        setActiveConversationId(doc.conversation_id);
        await loadConversations(activeProjectId);
      }

      setDocuments((prev) => [...prev.filter((d) => d.id !== doc.id), doc]);
      if (activeProjectId) {
        setProjectDocuments((prev) => [...prev.filter((d) => d.id !== doc.id), doc]);
        await loadProjectDetails(activeProjectId);
      }

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

  // Upload document directly to active project
  const uploadProjectDocument = async (file: File): Promise<DocumentInfo | null> => {
    if (!activeProjectId) return null;
    return await uploadDocument(file);
  };

  // Remove attached document
  const removeDocument = async (documentId: string): Promise<void> => {
    try {
      const service = isMockMode ? mockService : api;
      await service.deleteDocument(documentId);
      setDocuments((prev) => prev.filter((d) => d.id !== documentId));
      setProjectDocuments((prev) => prev.filter((d) => d.id !== documentId));
      setConversations((prev) =>
        prev.map((c) =>
          c.id === activeConversationId
            ? { ...c, documents: (c.documents || []).filter((d) => d.id !== documentId) }
            : c
        )
      );
      if (activeProjectId) {
        await loadProjectDetails(activeProjectId);
      }
    } catch (err: any) {
      setErrorNotification('Failed to delete document: ' + (err.message || 'Error'));
    }
  };

  const clearUploadError = () => setUploadError(null);

  // Delete conversation
  const deleteConversation = async (id: string) => {
    try {
      const service = isMockMode ? mockService : api;
      await service.deleteConversation(id);
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
  const renameConversation = async (id: string, title: string) => {
    const trimmed = title.trim();
    if (!trimmed) return;
    try {
      const service = isMockMode ? mockService : api;
      await service.renameConversation(id, trimmed);
      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, title: trimmed, updated_at: new Date().toISOString() } : c))
      );
    } catch (err: any) {
      setErrorNotification('Failed to update title: ' + (err.message || 'Error'));
    }
  };

  // Project Workspace Actions
  const selectProject = async (id: string | null) => {
    setActiveProjectId(id);
    setActiveConversationId(null);
    setMessages([]);
    setDocuments([]);
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setIsSidebarOpen(false);
    }
    if (id) {
      setWorkspaceMode('project');
      await loadProjectDetails(id);
      await loadConversations(id);
    } else {
      setWorkspaceMode('chat');
      setProjectNotes([]);
      setProjectActivity([]);
      setProjectDocuments([]);
      await loadConversations(null);
    }
  };

  const createProject = async (name: string, description: string = '', instructions: string = ''): Promise<Project | null> => {
    try {
      const service = isMockMode ? mockService : api;
      const proj = await service.createProject(name, description, instructions);
      setProjects((prev) => [proj, ...prev]);
      await selectProject(proj.id);
      return proj;
    } catch (err: any) {
      setErrorNotification('Failed to create project: ' + (err.message || 'Error'));
      return null;
    }
  };

  const updateProject = async (
    id: string,
    updates: Partial<{ name: string; description: string; instructions: string }>
  ): Promise<void> => {
    try {
      const service = isMockMode ? mockService : api;
      const updated = await service.updateProject(id, updates);
      setProjects((prev) => prev.map((p) => (p.id === id ? { ...p, ...updated } : p)));
    } catch (err: any) {
      setErrorNotification('Failed to update project: ' + (err.message || 'Error'));
    }
  };

  const deleteProject = async (id: string): Promise<void> => {
    try {
      const service = isMockMode ? mockService : api;
      await service.deleteProject(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
      if (activeProjectId === id) {
        await selectProject(null);
      }
    } catch (err: any) {
      setErrorNotification('Failed to delete project: ' + (err.message || 'Error'));
    }
  };

  const saveProjectNote = async (title: string, content: string, category: string = 'note'): Promise<void> => {
    if (!activeProjectId) return;
    try {
      const service = isMockMode ? mockService : api;
      const note = await service.createProjectNote(activeProjectId, title, content, category);
      setProjectNotes((prev) => [note, ...prev]);
      await loadProjectDetails(activeProjectId);
    } catch (err: any) {
      setErrorNotification('Failed to save note: ' + (err.message || 'Error'));
    }
  };

  const deleteProjectNote = async (noteId: string): Promise<void> => {
    if (!activeProjectId) return;
    try {
      const service = isMockMode ? mockService : api;
      await service.deleteProjectNote(activeProjectId, noteId);
      setProjectNotes((prev) => prev.filter((n) => n.id !== noteId));
      await loadProjectDetails(activeProjectId);
    } catch (err: any) {
      setErrorNotification('Failed to delete note: ' + (err.message || 'Error'));
    }
  };

  // Stop active generation
  const stopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setActiveStreamStatus(null);
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
        const service = isMockMode ? mockService : api;
        const created = await service.createConversation(generatedTitle, selectedModel, activeProjectId || undefined);
        targetConvId = created.id;
        setActiveConversationId(created.id);
        setConversations((prev) => [created, ...prev]);
      } catch (err: any) {
        targetConvId = `conv_${generateUuid()}`;
        const localConv: Conversation = {
          id: targetConvId,
          title: generatedTitle,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          model: selectedModel,
          project_id: activeProjectId || undefined,
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
      conversation_id: targetConvId,
      role: 'user',
      content: trimmed,
      created_at: nowIso,
    };

    const assistantMsgPlaceholder: Message = {
      id: assistantMsgId,
      conversation_id: targetConvId,
      role: 'assistant',
      content: '',
      is_streaming: true,
      created_at: nowIso,
      model: selectedModel,
      citations: [],
    };

    const updatedMessages = [...messages, userMsg, assistantMsgPlaceholder];
    setMessages(updatedMessages);
    setIsGenerating(true);
    setConnectionState('generating');

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    const streamService = isMockMode ? mockService : api;
    const chatHistory = updatedMessages
      .filter((m) => m.id !== assistantMsgPlaceholder.id)
      .map((m) => ({ role: m.role, content: m.content }));

    let streamedText = '';
    let currentCitations: Citation[] = [];
    let currentVerification: VerificationReport | undefined = undefined;
    let currentDiagnostics: any[] = [];

    await streamService.streamChat(
      {
        conversation_id: targetConvId,
        project_id: activeProjectId || undefined,
        model: selectedModel,
        messages: chatHistory,
        max_tokens: settings.models.maxTokens || 256,
        temperature: settings.models.temperature ?? 0.7,
        enable_web_search: webSearchEnabled,
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
        onStatus: (status: StreamStatus) => {
          setActiveStreamStatus(status);
        },
        onCitations: (citations: Citation[]) => {
          currentCitations = citations;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgPlaceholder.id
                ? { ...msg, citations }
                : msg
            )
          );
        },
        onDiagnostics: (diagnostics: any[]) => {
          currentDiagnostics = diagnostics;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgPlaceholder.id
                ? { ...msg, diagnostics }
                : msg
            )
          );
        },
        onVerification: (verification: VerificationReport) => {
          currentVerification = verification;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgPlaceholder.id
                ? { ...msg, verification }
                : msg
            )
          );
        },
        onComplete: async (fullText: string) => {
          setActiveStreamStatus(null);
          setIsGenerating(false);
          setConnectionState('connected');
          const finalAssistantMsg: Message = {
            ...assistantMsgPlaceholder,
            content: fullText,
            citations: currentCitations,
            verification: currentVerification,
            diagnostics: currentDiagnostics,
            is_streaming: false,
          };

          setMessages((prev) =>
            prev.map((msg) => (msg.id === assistantMsgPlaceholder.id ? finalAssistantMsg : msg))
          );

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

          if (activeProjectId) {
            await loadProjectDetails(activeProjectId);
          }

          abortControllerRef.current = null;
        },
        onError: (err: Error) => {
          setActiveStreamStatus(null);
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
    const lastUserIdx = [...messages].reverse().findIndex((m) => m.role === 'user');
    if (lastUserIdx === -1) return;
    const actualIndex = messages.length - 1 - lastUserIdx;
    const lastUserMsg = messages[actualIndex];
    setMessages((prev) => prev.slice(0, actualIndex + 1));
    await sendMessage(lastUserMsg.content);
  };

  const toggleSidebar = () => setIsSidebarOpen((prev) => !prev);
  const openSettings = () => setIsSettingsOpen(true);
  const closeSettings = () => setIsSettingsOpen(false);

  const updateSettings = (newSettings: Partial<AppSettings>) => {
    setSettings((prev) => {
      const merged: AppSettings = {
        general: { ...prev.general, ...newSettings.general },
        appearance: { ...prev.appearance, ...newSettings.appearance },
        models: { ...prev.models, ...newSettings.models },
        localAi: { ...prev.localAi, ...newSettings.localAi },
        privacy: { ...prev.privacy, ...newSettings.privacy },
      };
      try {
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(merged));
      } catch {}
      return merged;
    });
  };

  const toggleMockMode = () => {
    const next = !isMockMode;
    setIsMockMode(next);
    try {
      localStorage.setItem(MOCK_MODE_KEY, JSON.stringify(next));
    } catch {}
    setMessages([]);
    setDocuments([]);
    setActiveConversationId(null);
    setActiveProjectId(null);
    loadConversations(null);
    loadProjects();
    checkConnection();
  };

  const clearErrorNotification = () => setErrorNotification(null);

  const clearAllHistory = async () => {
    try {
      for (const conv of conversations) {
        await deleteConversation(conv.id);
      }
      setConversations([]);
      setMessages([]);
      setDocuments([]);
      setActiveConversationId(null);
    } catch (err: any) {
      setErrorNotification('Failed to clear history: ' + err.message);
    }
  };

  return (
    <AppContext.Provider
      value={{
        workspaceMode,
        setWorkspaceMode,
        conversations,
        activeConversationId,
        activeConversation,
        messages,
        documents,
        projects,
        activeProjectId,
        activeProject,
        projectNotes,
        projectActivity,
        projectDocuments,
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
        webSearchEnabled,
        setWebSearchEnabled,
        activeStreamStatus,
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
        setSelectedModel: handleSetSelectedModel,
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
        selectProject,
        createProject,
        updateProject,
        deleteProject,
        saveProjectNote,
        deleteProjectNote,
        uploadProjectDocument,
        loadProjects,
        loadProjectDetails,
        isAuthRequired,
        isAuthenticated,
        loginWithPassword,
        logoutSession,
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
