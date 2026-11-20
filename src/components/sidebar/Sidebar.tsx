import React, { useState, useMemo } from 'react';
import {
  MessageSquare,
  Plus,
  Search,
  Settings,
  Trash2,
  Edit2,
  Check,
  X,
  ChevronLeft,
  BookOpen,
  FolderPlus,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { groupConversationsByDate, DateGroup } from '../../utils/date';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Modal } from '../ui/Modal';
import { cn } from '../../utils/cn';

export const Sidebar: React.FC = () => {
  const {
    conversations,
    activeConversationId,
    selectConversation,
    createNewConversation,
    deleteConversation,
    renameConversation,
    isSidebarOpen,
    toggleSidebar,
    setSidebarOpen,
    openSettings,
    selectedModel,
    availableModels,
    connectionState,
    isMockMode,
    searchQuery,
    setSearchQuery,
    workspaceMode,
    setWorkspaceMode,
    projects,
    activeProjectId,
    selectProject,
    createProject,
    deleteProject,
  } = useApp();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Project state
  const [isNewProjectModalOpen, setIsNewProjectModalOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDesc, setNewProjectDesc] = useState('');
  const [deletingProjectId, setDeletingProjectId] = useState<string | null>(null);

  // Filter conversations by search query
  const filteredConversations = useMemo(() => {
    if (!searchQuery.trim()) return conversations;
    const q = searchQuery.toLowerCase();
    return conversations.filter((c) => c.title.toLowerCase().includes(q));
  }, [conversations, searchQuery]);

  // Group conversations by relative date
  const grouped = useMemo(() => {
    return groupConversationsByDate(filteredConversations);
  }, [filteredConversations]);

  const currentModel = availableModels.find((m) => m.id === selectedModel);

  const startEditing = (e: React.MouseEvent, id: string, currentTitle: string) => {
    e.stopPropagation();
    setEditingId(id);
    setEditingTitle(currentTitle);
  };

  const saveEditing = (id: string) => {
    if (editingTitle.trim()) {
      renameConversation(id, editingTitle.trim());
    }
    setEditingId(null);
  };

  const cancelEditing = () => {
    setEditingId(null);
  };

  const confirmDelete = async () => {
    if (deletingId) {
      await deleteConversation(deletingId);
      setDeletingId(null);
    }
  };

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) return;
    await createProject(
      newProjectName.trim(),
      newProjectDesc.trim() || undefined
    );
    setNewProjectName('');
    setNewProjectDesc('');
    setIsNewProjectModalOpen(false);
  };

  const confirmDeleteProject = async () => {
    if (deletingProjectId) {
      await deleteProject(deletingProjectId);
      setDeletingProjectId(null);
    }
  };

  const dateGroups: DateGroup[] = ['Today', 'Yesterday', 'Previous 7 Days', 'Previous 30 Days', 'Older'];

  // Mobile drawer: Lock body scroll & Escape key handler
  React.useEffect(() => {
    if (!isSidebarOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && window.innerWidth < 768) {
        setSidebarOpen(false);
      }
    };

    if (window.innerWidth < 768) {
      document.body.style.overflow = 'hidden';
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = '';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isSidebarOpen, setSidebarOpen]);

  if (!isSidebarOpen) {
    return null;
  }

  return (
    <>
      {/* Mobile Navigation Drawer Backdrop */}
      <div
        className="fixed inset-0 bg-black/65 backdrop-blur-xs z-40 md:hidden transition-opacity duration-200"
        onClick={() => setSidebarOpen(false)}
        aria-hidden="true"
      />

      {/* Sidebar (Desktop) / Sliding Overlay Drawer (Mobile) */}
      <aside
        className={cn(
          'bg-moso-side border-r border-moso-750/60 flex flex-col h-full select-none shrink-0 transition-all duration-200',
          'fixed inset-y-0 left-0 z-50 w-[85vw] max-w-[320px] shadow-2xl animate-slide-right',
          'md:relative md:inset-auto md:w-72 md:shadow-none md:animate-none md:z-30'
        )}
      >
        {/* Brand & Collapse Header */}
        <div className="px-4 pt-4 pb-2 flex items-center justify-between">
          <div
            onClick={() => {
              createNewConversation();
              if (window.innerWidth < 768) setSidebarOpen(false);
            }}
            className="flex items-center gap-2.5 cursor-pointer hover:opacity-80 transition-opacity"
            title="Start new conversation"
          >
            <img src="/logo.svg" alt="Moso AI" className="h-7 w-7 rounded-lg" />
            <span className="font-serif text-[21px] leading-none tracking-tight text-white">Moso AI</span>
          </div>

          <Button
            variant="ghost"
            size="icon-sm"
            onClick={toggleSidebar}
            aria-label="Close sidebar"
            className="text-moso-400 hover:text-white"
          >
            <X className="h-4 w-4 md:hidden" />
            <ChevronLeft className="hidden md:block h-4 w-4" />
          </Button>
        </div>

        {/* Workspace Mode Switcher (Chats vs Research Projects) */}
        <div className="px-3 pt-2.5 pb-1">
          <div className="grid grid-cols-2 p-0.5 rounded-lg bg-moso-800/60 text-xs">
            <button
              type="button"
              onClick={() => setWorkspaceMode('chat')}
              className={cn(
                'flex items-center justify-center gap-1.5 py-1.5 rounded-md font-medium transition-all cursor-pointer',
                workspaceMode === 'chat'
                  ? 'bg-moso-900 text-white shadow-sm'
                  : 'text-moso-400 hover:text-moso-200'
              )}
            >
              <MessageSquare className="h-3.5 w-3.5" />
              <span>Chats</span>
            </button>
            <button
              type="button"
              onClick={() => setWorkspaceMode('project')}
              className={cn(
                'flex items-center justify-center gap-1.5 py-1.5 rounded-md font-medium transition-all cursor-pointer',
                workspaceMode === 'project'
                  ? 'bg-moso-900 text-white shadow-sm'
                  : 'text-moso-400 hover:text-moso-200'
              )}
            >
              <BookOpen className="h-3.5 w-3.5" />
              <span>Projects</span>
            </button>
          </div>
        </div>

        {/* MODE: CHATS */}
        {workspaceMode === 'chat' ? (
          <>
            {/* New Conversation Button */}
            <div className="px-2 pt-2 pb-1">
              <button
                type="button"
                onClick={() => createNewConversation()}
                className="w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-[14px] font-medium text-moso-100 hover:bg-moso-800/70 transition-colors cursor-pointer"
              >
                <span className="flex items-center gap-2.5">
                  <span className="h-6 w-6 rounded-full bg-moso-accent text-moso-950 flex items-center justify-center">
                    <Plus className="h-3.5 w-3.5 stroke-[2.75]" />
                  </span>
                  <span>New chat</span>
                </span>
                <kbd className="hidden sm:inline-block text-[11px] font-sans text-moso-500">Ctrl+N</kbd>
              </button>
            </div>

            {/* Search Conversations Input */}
            <div className="px-3 py-1.5">
              <Input
                icon={<Search className="h-3.5 w-3.5" />}
                placeholder="Search conversations..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="text-[13px] py-1.5 bg-moso-900/70 border-moso-750"
              />
            </div>

            {/* Conversation History List */}
            <div className="flex-1 overflow-y-auto px-2 py-2 space-y-4">
              {conversations.length === 0 ? (
                <div className="p-6 text-center text-xs text-moso-500">
                  <MessageSquare className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p>No conversations yet.</p>
                  <p className="mt-1 text-[11px] text-moso-600">Start typing below to begin.</p>
                </div>
              ) : filteredConversations.length === 0 ? (
                <div className="p-6 text-center text-xs text-moso-500">
                  <p>No matches for &ldquo;{searchQuery}&rdquo;</p>
                </div>
              ) : (
                dateGroups.map((group) => {
                  const items = grouped[group];
                  if (!items || items.length === 0) return null;

                  return (
                    <div key={group} className="space-y-0.5">
                      <div className="px-2.5 pt-2 pb-1 text-[12px] font-medium text-moso-500">
                        {group}
                      </div>
                      {items.map((conv) => {
                        const isActive = conv.id === activeConversationId;
                        const isEditing = conv.id === editingId;

                        return (
                          <div
                            key={conv.id}
                            onClick={() => !isEditing && selectConversation(conv.id)}
                            className={cn(
                              'group relative flex items-center justify-between px-2.5 py-2 rounded-lg text-[14px] cursor-pointer transition-colors duration-150',
                              isActive
                                ? 'bg-moso-800 text-white'
                                : 'text-moso-200 hover:bg-moso-800/60 hover:text-white'
                            )}
                          >
                            {isEditing ? (
                              <div className="flex items-center gap-1 w-full" onClick={(e) => e.stopPropagation()}>
                                <input
                                  type="text"
                                  value={editingTitle}
                                  onChange={(e) => setEditingTitle(e.target.value)}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter') saveEditing(conv.id);
                                    if (e.key === 'Escape') cancelEditing();
                                  }}
                                  autoFocus
                                  className="w-full bg-moso-900 border border-moso-600 rounded px-1.5 py-0.5 text-xs text-white focus:outline-none focus:border-moso-accent"
                                />
                                <button
                                  type="button"
                                  onClick={() => saveEditing(conv.id)}
                                  className="text-accent-400 hover:text-accent-300 p-0.5"
                                >
                                  <Check className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  type="button"
                                  onClick={cancelEditing}
                                  className="text-rose-400 hover:text-rose-300 p-0.5"
                                >
                                  <X className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            ) : (
                              <>
                                <div className="flex items-center gap-2 min-w-0 pr-2">
                                  <span className="truncate">{conv.title}</span>
                                  {conv.documents && conv.documents.length > 0 && (
                                    <span
                                      className="text-[9px] font-bold text-rose-400/90 bg-rose-500/10 border border-rose-500/20 px-1 py-0.2 rounded shrink-0 tracking-wider"
                                      title={`${conv.documents.length} PDF attached`}
                                    >
                                      PDF
                                    </span>
                                  )}
                                </div>

                                {/* Hover Actions: Rename, Delete */}
                                <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                                  <button
                                    type="button"
                                    onClick={(e) => startEditing(e, conv.id, conv.title)}
                                    className="p-1 text-moso-400 hover:text-white rounded hover:bg-moso-700/60"
                                    title="Rename conversation"
                                  >
                                    <Edit2 className="h-3 w-3" />
                                  </button>
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setDeletingId(conv.id);
                                    }}
                                    className="p-1 text-moso-400 hover:text-rose-400 rounded hover:bg-moso-700/60"
                                    title="Delete conversation"
                                  >
                                    <Trash2 className="h-3 w-3" />
                                  </button>
                                </div>
                              </>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  );
                })
              )}
            </div>
          </>
        ) : (
          /* MODE: PROJECTS */
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="p-3 pb-2">
              <Button
                variant="primary"
                onClick={() => setIsNewProjectModalOpen(true)}
                className="w-full justify-between shadow-sm bg-accent-600 hover:bg-accent-500"
              >
                <span className="flex items-center gap-2">
                  <FolderPlus className="h-4 w-4 stroke-[2.5]" />
                  <span>New Research Project</span>
                </span>
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1.5">
              {projects.length === 0 ? (
                <div className="p-6 text-center text-xs text-moso-500">
                  <BookOpen className="h-8 w-8 mx-auto mb-2 opacity-30 text-accent-400" />
                  <p>No research projects yet.</p>
                  <p className="mt-1 text-[11px] text-moso-600">
                    Create a dedicated workspace for academic papers and mathematical analysis.
                  </p>
                </div>
              ) : (
                projects.map((project) => {
                  const isActive = project.id === activeProjectId;
                  return (
                    <div
                      key={project.id}
                      onClick={() => selectProject(project.id)}
                      className={cn(
                        'group relative flex items-center justify-between px-3 py-2.5 rounded-xl text-[13.5px] cursor-pointer transition-all duration-150',
                        isActive
                          ? 'bg-accent-950/40 border border-accent-500/30 text-white font-medium shadow-xs'
                          : 'text-moso-300 hover:bg-moso-850 hover:text-white border border-transparent'
                      )}
                    >
                      <div className="flex items-center gap-2.5 min-w-0 pr-2">
                        <BookOpen
                          className={cn(
                            'h-4 w-4 shrink-0',
                            isActive ? 'text-accent-400' : 'text-moso-500 group-hover:text-accent-400'
                          )}
                        />
                        <div className="truncate">
                          <p className="truncate font-medium text-white text-[13.5px]">{project.name}</p>
                          {project.description && (
                            <p className="text-[11px] text-moso-400 truncate">{project.description}</p>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeletingProjectId(project.id);
                          }}
                          className="p-1 text-moso-400 hover:text-rose-400 rounded hover:bg-moso-700/60"
                          title="Delete project"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}

        {/* Footer: connection status and settings */}
        <div className="p-2 border-t border-moso-750/60">
          <div
            className="flex items-center gap-2 px-2.5 py-1.5 text-[12px] text-moso-500"
            title={`Model: ${currentModel?.name || selectedModel}`}
          >
            <span
              className={cn(
                'h-1.5 w-1.5 rounded-full shrink-0',
                connectionState === 'connected' && 'bg-moso-accent',
                connectionState === 'connecting' && 'bg-amber-500 animate-pulse',
                connectionState === 'generating' && 'bg-moso-accent animate-pulse',
                connectionState === 'disconnected' && 'bg-rose-500'
              )}
            />
            <span className="truncate">
              {connectionState === 'connected'
                ? isMockMode
                  ? 'Mock server'
                  : 'Running on this device'
                : connectionState === 'generating'
                ? 'Generating'
                : connectionState === 'connecting'
                ? 'Connecting'
                : 'Disconnected'}
            </span>
            {isMockMode && <span className="font-mono text-[10px] text-cyan-400">dev mock</span>}
          </div>

          <button
            type="button"
            onClick={() => {
              openSettings();
              if (window.innerWidth < 768) setSidebarOpen(false);
            }}
            className="w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-[13.5px] text-moso-300 hover:text-white hover:bg-moso-800/60 transition-colors cursor-pointer"
          >
            <span className="flex items-center gap-2.5">
              <Settings className="h-4 w-4" />
              <span>Settings</span>
            </span>
            <kbd className="text-[11px] font-sans text-moso-500">Ctrl+,</kbd>
          </button>
        </div>
      </aside>

      {/* Delete Conversation Confirmation Modal */}
      <Modal
        isOpen={Boolean(deletingId)}
        onClose={() => setDeletingId(null)}
        title="Delete conversation?"
        description="This will permanently delete this conversation and its stored messages from your local SQLite storage."
        maxWidth="sm"
      >
        <div className="flex justify-end gap-2.5 pt-3">
          <Button variant="ghost" onClick={() => setDeletingId(null)}>
            Cancel
          </Button>
          <Button variant="danger" onClick={confirmDelete}>
            Delete
          </Button>
        </div>
      </Modal>

      {/* New Project Modal */}
      <Modal
        isOpen={isNewProjectModalOpen}
        onClose={() => setIsNewProjectModalOpen(false)}
        title="Create Research Project"
        description="Create an isolated workspace for papers, mathematical derivations, and research notes."
        maxWidth="sm"
      >
        <div className="space-y-3 pt-2">
          <div>
            <label className="block text-[11px] font-semibold text-moso-300 mb-1">
              Project Title
            </label>
            <input
              type="text"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              placeholder="e.g. Deep Learning Image Segmentation"
              className="w-full bg-moso-850 border border-moso-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-accent-500"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-moso-300 mb-1">
              Description / Research Goals (optional)
            </label>
            <textarea
              value={newProjectDesc}
              onChange={(e) => setNewProjectDesc(e.target.value)}
              placeholder="e.g. Evaluating convolutional vs transformer backbones on biomedical benchmarks."
              rows={3}
              className="w-full bg-moso-850 border border-moso-700 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-accent-500"
            />
          </div>
          <div className="flex justify-end gap-2 pt-3 border-t border-moso-800">
            <Button variant="ghost" onClick={() => setIsNewProjectModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleCreateProject}>
              Create Project
            </Button>
          </div>
        </div>
      </Modal>

      {/* Delete Project Confirmation Modal */}
      <Modal
        isOpen={Boolean(deletingProjectId)}
        onClose={() => setDeletingProjectId(null)}
        title="Delete research project?"
        description="This will permanently delete the project, all its uploaded research papers, notes, and activity history from SQLite storage."
        maxWidth="sm"
      >
        <div className="flex justify-end gap-2.5 pt-3">
          <Button variant="ghost" onClick={() => setDeletingProjectId(null)}>
            Cancel
          </Button>
          <Button variant="danger" onClick={confirmDeleteProject}>
            Delete Project
          </Button>
        </div>
      </Modal>
    </>
  );
};