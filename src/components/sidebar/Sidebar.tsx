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
  Cpu,
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
    openSettings,
    selectedModel,
    availableModels,
    connectionState,
    isMockMode,
    searchQuery,
    setSearchQuery,
  } = useApp();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);

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

  const dateGroups: DateGroup[] = ['Today', 'Yesterday', 'Previous 7 Days', 'Previous 30 Days', 'Older'];

  if (!isSidebarOpen) {
    return null;
  }

  return (
    <>
      <aside className="w-72 sm:w-64 md:w-72 bg-moso-900 border-r border-moso-800/80 flex flex-col h-full select-none shrink-0 transition-all duration-200 z-30">
        {/* Brand & Collapse Header */}
        <div className="p-3.5 border-b border-moso-800/60 flex items-center justify-between">
          <div
            onClick={createNewConversation}
            className="flex items-center gap-2.5 cursor-pointer group hover:opacity-90 transition-opacity"
            title="Start new conversation"
          >
            <img src="/logo.svg" alt="Moso AI" className="h-7 w-7 rounded-lg shadow-sm" />
            <div className="flex flex-col">
              <span className="font-semibold text-sm tracking-tight text-white flex items-center gap-1.5">
                Moso AI
                <span className="text-[10px] font-mono font-medium px-1.5 py-0.2 rounded bg-moso-800 text-moso-accent border border-moso-700/60">
                  v0.1
                </span>
              </span>
              <span className="text-[10px] text-moso-400 font-normal">Local-First Assistant</span>
            </div>
          </div>

          <Button
            variant="ghost"
            size="icon-sm"
            onClick={toggleSidebar}
            aria-label="Collapse sidebar"
            className="text-moso-400 hover:text-white"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>

        {/* New Conversation Button */}
        <div className="p-3 pb-2">
          <Button
            variant="primary"
            onClick={createNewConversation}
            className="w-full justify-between shadow-sm group"
          >
            <span className="flex items-center gap-2">
              <Plus className="h-4 w-4 stroke-[2.5]" />
              <span>New Conversation</span>
            </span>
            <kbd className="hidden sm:inline-block text-[10px] font-mono bg-moso-950/30 text-moso-950 px-1.5 py-0.5 rounded border border-moso-950/20">
              Ctrl+N
            </kbd>
          </Button>
        </div>

        {/* Search Conversations Input */}
        <div className="px-3 py-1.5">
          <Input
            icon={<Search className="h-3.5 w-3.5" />}
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="text-xs py-1.5 bg-moso-950/60 border-moso-800"
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
                  <div className="px-2.5 py-1 text-[10px] font-semibold tracking-wider text-moso-500 uppercase">
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
                          'group relative flex items-center justify-between px-2.5 py-2 rounded-lg text-xs cursor-pointer transition-all duration-150',
                          isActive
                            ? 'bg-moso-800 text-white font-medium shadow-xs'
                            : 'text-moso-300 hover:bg-moso-850 hover:text-white'
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
                              className="text-emerald-400 hover:text-emerald-300 p-0.5"
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
                              <MessageSquare
                                className={cn(
                                  'h-3.5 w-3.5 shrink-0',
                                  isActive ? 'text-moso-accent' : 'text-moso-500 group-hover:text-moso-400'
                                )}
                              />
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

        {/* Footer: Model & Connection Status & Settings */}
        <div className="p-3 border-t border-moso-800/80 bg-moso-950/40 space-y-2">
          {/* Active Model Indicator */}
          <div className="flex items-center justify-between text-xs px-2 py-1.5 rounded-lg bg-moso-850/70 border border-moso-800">
            <div className="flex items-center gap-2 truncate">
              <Cpu className="h-3.5 w-3.5 text-moso-accent shrink-0" />
              <span className="text-moso-300 truncate font-medium">
                {currentModel?.name || selectedModel}
              </span>
            </div>
            <span className="text-[10px] text-moso-500 font-mono shrink-0">
              {currentModel?.size || '2B'}
            </span>
          </div>

          {/* Connection Status Pill */}
          <div className="flex items-center justify-between px-2 text-xs">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  'h-2 w-2 rounded-full',
                  connectionState === 'connected' && 'bg-emerald-500',
                  connectionState === 'connecting' && 'bg-amber-500 animate-pulse',
                  connectionState === 'generating' && 'bg-moso-accent animate-ping',
                  connectionState === 'disconnected' && 'bg-rose-500'
                )}
              />
              <span className="text-[11px] text-moso-400 capitalize">
                {connectionState === 'connected'
                  ? isMockMode
                    ? 'Mock Local Server'
                    : 'Backend Online'
                  : connectionState}
              </span>
            </div>
            {isMockMode && (
              <span className="text-[9px] text-cyan-400 font-mono bg-cyan-950/40 px-1 rounded border border-cyan-800/40">
                DEV MOCK
              </span>
            )}
          </div>

          {/* Settings Trigger */}
          <button
            type="button"
            onClick={openSettings}
            className="w-full flex items-center justify-between px-2 py-1.5 rounded-lg text-xs text-moso-400 hover:text-white hover:bg-moso-850 transition-colors cursor-pointer"
          >
            <span className="flex items-center gap-2">
              <Settings className="h-3.5 w-3.5" />
              <span>Settings</span>
            </span>
            <kbd className="text-[10px] font-mono text-moso-500">Ctrl+,</kbd>
          </button>
        </div>
      </aside>

      {/* Delete Confirmation Modal */}
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
    </>
  );
};
