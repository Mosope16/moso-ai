import React, { useState, useRef, useEffect } from 'react';
import {
  Menu,
  ChevronDown,
  Settings,
  Plus,
  Radio,
  Check,
  Cpu,
  Lock,
  MoreVertical,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { cn } from '../../utils/cn';

export const Header: React.FC = () => {
  const {
    activeConversation,
    activeConversationId,
    selectedModel,
    availableModels,
    setSelectedModel,
    connectionState,
    healthInfo,
    isMockMode,
    toggleMockMode,
    isSidebarOpen,
    toggleSidebar,
    openSettings,
    createNewConversation,
    renameConversation,
    workspaceMode,
    activeProject,
    isAuthRequired,
    isAuthenticated,
    logoutSession,
  } = useApp();

  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);
  const [isOverflowMenuOpen, setIsOverflowMenuOpen] = useState(false);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);
  const overflowRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsModelDropdownOpen(false);
      }
      if (overflowRef.current && !overflowRef.current.contains(e.target as Node)) {
        setIsOverflowMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const currentModelInfo = availableModels.find((m) => m.id === selectedModel);

  const handleStartRename = () => {
    if (activeConversation) {
      setTitleInput(activeConversation.title);
      setIsEditingTitle(true);
    }
  };

  const handleFinishRename = () => {
    if (activeConversationId && titleInput.trim()) {
      renameConversation(activeConversationId, titleInput.trim());
    }
    setIsEditingTitle(false);
  };

  // Connection indicator badge content
  const renderConnectionPill = () => {
    switch (connectionState) {
      case 'connected':
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="font-medium">Ollama Local</span>
            {healthInfo?.latency_ms && (
              <span className="text-[10px] text-emerald-500/70 border-l border-emerald-500/20 pl-1.5 ml-0.5">
                {healthInfo.latency_ms}ms
              </span>
            )}
          </div>
        );
      case 'connecting':
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs">
            <span className="relative flex h-2 w-2">
              <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500 animate-pulse"></span>
            </span>
            <span className="font-medium">Connecting...</span>
          </div>
        );
      case 'generating':
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-moso-accent/15 border border-moso-accent/30 text-moso-accent text-xs">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-moso-accent opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-moso-accent"></span>
            </span>
            <span className="font-medium">Generating</span>
          </div>
        );
      case 'disconnected':
      default:
        return (
          <div
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs cursor-pointer hover:bg-rose-500/15 transition-colors"
            onClick={openSettings}
            title="Backend disconnected. Click to check settings."
          >
            <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
            <span className="font-medium">Disconnected</span>
          </div>
        );
    }
  };

  // Compact Mobile Connection Indicator Dot
  const renderMobileConnectionDot = () => {
    switch (connectionState) {
      case 'connected':
        return (
          <span
            className="relative flex h-2.5 w-2.5 cursor-pointer"
            onClick={openSettings}
            title={`Ollama Local Connected${healthInfo?.latency_ms ? ` (${healthInfo.latency_ms}ms)` : ''}`}
          >
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
          </span>
        );
      case 'connecting':
        return (
          <span className="relative flex h-2.5 w-2.5" title="Connecting...">
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-500 animate-pulse"></span>
          </span>
        );
      case 'generating':
        return (
          <span className="relative flex h-2.5 w-2.5" title="Generating...">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-moso-accent opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-moso-accent"></span>
          </span>
        );
      case 'disconnected':
      default:
        return (
          <span
            className="relative flex h-2.5 w-2.5 cursor-pointer"
            onClick={openSettings}
            title="Disconnected"
          >
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-rose-500"></span>
          </span>
        );
    }
  };

  return (
    <header
      data-tauri-drag-region
      className="h-14 border-b border-moso-800/80 bg-moso-900/90 backdrop-blur-md px-3 sm:px-4 flex items-center justify-between select-none z-20 shrink-0"
    >
      {/* Mobile Left: Menu Toggle + Logo + Compact Title */}
      <div className="flex md:hidden items-center gap-2 min-w-0 flex-1 pr-2" data-tauri-no-drag>
        <button
          type="button"
          onClick={toggleSidebar}
          aria-label="Open navigation drawer"
          className="p-1.5 -ml-1 text-moso-300 hover:text-white rounded-lg active:bg-moso-800 shrink-0 cursor-pointer"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="flex items-center gap-2 min-w-0">
          <img src="/logo.svg" alt="Moso AI" className="h-6 w-6 rounded-md shrink-0 shadow-xs" />
          <span className="text-[13.5px] font-semibold text-white truncate max-w-[140px] sm:max-w-[200px]">
            {activeConversation?.title || (workspaceMode === 'project' && activeProject?.name ? activeProject.name : 'Moso AI')}
          </span>
        </div>
      </div>

      {/* Desktop Left: Sidebar toggle, New chat, and Title */}
      <div className="hidden md:flex items-center gap-3 min-w-0" data-tauri-no-drag>
        {!isSidebarOpen && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={toggleSidebar}
            aria-label="Open sidebar"
            className="text-moso-300 hover:text-white"
          >
            <Menu className="h-4 w-4" />
          </Button>
        )}

        {!isSidebarOpen && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => createNewConversation()}
            aria-label="New chat"
            className="text-moso-300 hover:text-white"
          >
            <Plus className="h-4 w-4" />
          </Button>
        )}

        {/* Conversation / Project Title */}
        <div className="flex items-center gap-2 min-w-0">
          {workspaceMode === 'project' ? (
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-white truncate max-w-[200px] sm:max-w-xs md:max-w-md">
                {activeProject ? activeProject.name : 'Research Workspace'}
              </h2>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.2 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                Workspace
              </span>
            </div>
          ) : isEditingTitle ? (
            <input
              type="text"
              value={titleInput}
              onChange={(e) => setTitleInput(e.target.value)}
              onBlur={handleFinishRename}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleFinishRename();
                if (e.key === 'Escape') setIsEditingTitle(false);
              }}
              autoFocus
              className="bg-moso-800 border border-moso-600 rounded px-2 py-0.5 text-sm text-white focus:outline-none focus:ring-1 focus:ring-moso-accent"
            />
          ) : (
            <h2
              onClick={handleStartRename}
              className={cn(
                'text-[14.5px] font-semibold text-white truncate cursor-pointer hover:text-emerald-400 transition-colors max-w-[200px] sm:max-w-xs md:max-w-md',
                !activeConversation && 'text-moso-400 font-normal italic'
              )}
              title={activeConversation?.title || 'New Session'}
            >
              {activeConversation?.title || 'New Session'}
            </h2>
          )}
        </div>
      </div>

      {/* Mobile Right: Quick Chat, Compact Model, Dot, Overflow Menu */}
      <div className="flex md:hidden items-center gap-2 shrink-0" data-tauri-no-drag>
        {/* Quick New Chat Button */}
        <button
          type="button"
          onClick={() => createNewConversation()}
          aria-label="New chat"
          title="New chat"
          className="p-1.5 text-moso-300 hover:text-white rounded-lg active:bg-moso-800 cursor-pointer"
        >
          <Plus className="h-4.5 w-4.5" />
        </button>

        {/* Compact Model Selector */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setIsModelDropdownOpen((prev) => !prev)}
            className="flex items-center gap-1 px-2 py-1 rounded-md bg-moso-800/80 border border-moso-700/60 text-xs text-moso-200 cursor-pointer"
          >
            <Cpu className="h-3 w-3 text-moso-accent" />
            <span className="font-semibold text-[11px] max-w-[70px] truncate">
              {currentModelInfo?.name.replace(/^(Qwen|Ollama)\s*/i, '') || '2B'}
            </span>
            <ChevronDown
              className={cn(
                'h-2.5 w-2.5 text-moso-400 transition-transform',
                isModelDropdownOpen && 'rotate-180'
              )}
            />
          </button>

          {/* Mobile Model Dropdown Menu */}
          {isModelDropdownOpen && (
            <div className="absolute right-0 mt-2 w-64 rounded-xl bg-moso-900 border border-moso-700 shadow-2xl p-1.5 z-50 animate-slide-up">
              <div className="px-2.5 py-1.5 text-[10px] font-semibold text-moso-400 uppercase tracking-wider border-b border-moso-800">
                Local Models (Ollama)
              </div>
              <div className="py-1 max-h-60 overflow-y-auto">
                {availableModels
                  .filter((m) => m.is_local)
                  .map((model) => (
                    <button
                      key={model.id}
                      onClick={() => {
                        setSelectedModel(model.id);
                        setIsModelDropdownOpen(false);
                      }}
                      className={cn(
                        'w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-left text-xs transition-colors cursor-pointer',
                        selectedModel === model.id
                          ? 'bg-moso-800 text-white font-medium'
                          : 'text-moso-300 hover:bg-moso-800/50 hover:text-white'
                      )}
                    >
                      <div className="min-w-0 pr-2">
                        <span className="font-medium text-xs">{model.name}</span>
                        <span className="block text-[10px] text-moso-500 font-mono">{model.size}</span>
                      </div>
                      {selectedModel === model.id && (
                        <Check className="h-3.5 w-3.5 text-moso-accent shrink-0" />
                      )}
                    </button>
                  ))}
              </div>
            </div>
          )}
        </div>

        {/* Compact Connection Dot */}
        <div className="px-1 flex items-center">
          {renderMobileConnectionDot()}
        </div>

        {/* Mobile Overflow Menu */}
        <div className="relative" ref={overflowRef}>
          <button
            type="button"
            onClick={() => setIsOverflowMenuOpen((prev) => !prev)}
            aria-label="More options"
            className="p-1.5 text-moso-300 hover:text-white rounded-lg active:bg-moso-800 cursor-pointer"
          >
            <MoreVertical className="h-4.5 w-4.5" />
          </button>

          {isOverflowMenuOpen && (
            <div className="absolute right-0 mt-2 w-48 rounded-xl bg-moso-900 border border-moso-700 shadow-2xl p-1.5 z-50 animate-slide-up">
              <button
                type="button"
                onClick={() => {
                  openSettings();
                  setIsOverflowMenuOpen(false);
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-xs text-moso-200 hover:bg-moso-800 hover:text-white transition-colors cursor-pointer"
              >
                <Settings className="h-3.5 w-3.5 text-moso-400" />
                <span>Settings</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  toggleMockMode();
                  setIsOverflowMenuOpen(false);
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-xs text-moso-200 hover:bg-moso-800 hover:text-white transition-colors cursor-pointer"
              >
                <Radio className={cn('h-3.5 w-3.5', isMockMode ? 'text-cyan-400' : 'text-moso-500')} />
                <span>{isMockMode ? 'Switch to Live Mode' : 'Switch to Mock Mode'}</span>
              </button>

              {isAuthRequired && isAuthenticated && (
                <button
                  type="button"
                  onClick={() => {
                    logoutSession();
                    setIsOverflowMenuOpen(false);
                  }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-xs text-amber-400 hover:bg-moso-800 transition-colors border-t border-moso-800/80 mt-1 pt-1.5 cursor-pointer"
                >
                  <Lock className="h-3.5 w-3.5" />
                  <span>Lock Session</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Desktop Right side: Model selector, connection pill, mock mode badge, settings */}
      <div className="hidden md:flex items-center gap-2.5 shrink-0" data-tauri-no-drag>
        {/* Model Selector Dropdown */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setIsModelDropdownOpen((prev) => !prev)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-moso-800/80 hover:bg-moso-750 border border-moso-700/60 transition-all text-[13px] text-moso-200 hover:text-white cursor-pointer"
          >
            <Cpu className="h-3.5 w-3.5 text-moso-accent" />
            <span className="font-semibold">{currentModelInfo?.name || selectedModel}</span>
            <ChevronDown
              className={cn(
                'h-3 w-3 text-moso-400 transition-transform duration-150',
                isModelDropdownOpen && 'rotate-180'
              )}
            />
          </button>

          {/* Desktop Dropdown Menu */}
          {isModelDropdownOpen && (
            <div className="absolute right-0 mt-2 w-72 rounded-xl bg-moso-900 border border-moso-700/80 shadow-2xl p-1.5 z-50 animate-slide-up">
              <div className="px-2.5 py-1.5 text-[11px] font-semibold text-moso-400 uppercase tracking-wider border-b border-moso-800">
                Local Models (Ollama)
              </div>
              <div className="py-1">
                {availableModels
                  .filter((m) => m.is_local)
                  .map((model) => (
                    <button
                      key={model.id}
                      onClick={() => {
                        setSelectedModel(model.id);
                        setIsModelDropdownOpen(false);
                      }}
                      className={cn(
                        'w-full flex items-start justify-between px-2.5 py-2 rounded-lg text-left text-xs transition-colors cursor-pointer group',
                        selectedModel === model.id
                          ? 'bg-moso-800 text-white'
                          : 'text-moso-200 hover:bg-moso-800/50 hover:text-white'
                      )}
                    >
                      <div className="min-w-0 pr-2">
                        <div className="flex items-center gap-1.5">
                          <span className="font-medium">{model.name}</span>
                          {model.is_default && (
                            <Badge variant="accent" size="sm">
                              Default
                            </Badge>
                          )}
                        </div>
                        <p className="text-[11px] text-moso-400 truncate mt-0.5">
                          {model.description}
                        </p>
                      </div>
                      <div className="shrink-0 flex items-center gap-1.5 text-right">
                        <span className="text-[10px] text-moso-500 font-mono">{model.size}</span>
                        {selectedModel === model.id && (
                          <Check className="h-3.5 w-3.5 text-moso-accent" />
                        )}
                      </div>
                    </button>
                  ))}
              </div>

              <div className="px-2.5 py-1.5 text-[11px] font-semibold text-moso-400 uppercase tracking-wider border-t border-b border-moso-800 mt-1">
                Cloud Providers (Future)
              </div>
              <div className="py-1 opacity-60">
                {availableModels
                  .filter((m) => !m.is_local)
                  .map((model) => (
                    <div
                      key={model.id}
                      className="px-2.5 py-1.5 text-xs text-moso-400 flex items-center justify-between cursor-not-allowed"
                    >
                      <span>{model.name}</span>
                      <span className="text-[10px] bg-moso-800 px-1.5 py-0.5 rounded text-moso-400">
                        Planned
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>

        {/* Local / Cloud Status */}
        <div className="flex items-center gap-1.5 text-xs text-moso-300">
          {renderConnectionPill()}
        </div>

        {/* Dev Mock Mode Indicator / Toggle */}
        <button
          onClick={toggleMockMode}
          title={
            isMockMode
              ? 'Dev Mock Mode is ON: Simulates local backend responses without requiring active Ollama process. Click to switch to Live Backend.'
              : 'Live Backend Mode: Connected to local FastAPI / Ollama service. Click to switch to Dev Mock Simulator.'
          }
          className={cn(
            'flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium border transition-colors cursor-pointer',
            isMockMode
              ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/20'
              : 'bg-moso-850 border-moso-750 text-moso-400 hover:text-moso-200'
          )}
        >
          <Radio className={cn('h-3 w-3', isMockMode ? 'text-cyan-400' : 'text-moso-500')} />
          <span>{isMockMode ? 'Dev Mock Mode' : 'Live Mode'}</span>
        </button>

        {/* Settings Button */}
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={openSettings}
          aria-label="Settings"
          className="text-moso-300 hover:text-white"
        >
          <Settings className="h-4 w-4" />
        </Button>

        {/* Lock / Sign Out Button for Protected Remote Sessions */}
        {isAuthRequired && isAuthenticated && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={logoutSession}
            aria-label="Lock Session"
            title="Lock Session / Sign Out"
            className="text-moso-300 hover:text-amber-400"
          >
            <Lock className="h-4 w-4" />
          </Button>
        )}
      </div>
    </header>
  );
};
