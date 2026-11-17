import React, { useEffect } from 'react';
import { AppProvider, useApp } from './context/AppContext';
import { Sidebar } from './components/sidebar/Sidebar';
import { Header } from './components/header/Header';
import { ChatArea } from './components/chat/ChatArea';
import { SettingsModal } from './components/settings/SettingsModal';
import { AlertCircle, X } from 'lucide-react';

const AppContent: React.FC = () => {
  const {
    toggleSidebar,
    createNewConversation,
    openSettings,
    errorNotification,
    clearErrorNotification,
    isMockMode,
    toggleMockMode,
  } = useApp();

  // Global Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+N or Cmd+N: New conversation
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'n') {
        e.preventDefault();
        createNewConversation();
      }
      // Ctrl+B or Cmd+B or Ctrl+\: Toggle Sidebar
      if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === 'b' || e.key === '\\')) {
        e.preventDefault();
        toggleSidebar();
      }
      // Ctrl+, or Cmd+,: Open settings
      if ((e.ctrlKey || e.metaKey) && e.key === ',') {
        e.preventDefault();
        openSettings();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [createNewConversation, toggleSidebar, openSettings]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-moso-950 text-moso-100 select-none">
      {/* Collapsible Sidebar */}
      <Sidebar />

      {/* Main View Area */}
      <main className="flex-1 flex flex-col h-full min-w-0 overflow-hidden relative">
        {/* Top Header */}
        <Header />

        {/* Global Connection / Mode Banner (if backend error and mock mode is off) */}
        {errorNotification && !isMockMode && (
          <div className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-2 flex items-center justify-between text-xs text-amber-300 z-10 animate-fade-in">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-amber-400" />
              <span>{errorNotification}</span>
              <button
                type="button"
                onClick={toggleMockMode}
                className="underline font-semibold hover:text-white cursor-pointer ml-2"
              >
                Enable Dev Mock Mode
              </button>
            </div>
            <button
              type="button"
              onClick={clearErrorNotification}
              className="p-1 hover:text-white rounded"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* Chat Conversation Area */}
        <ChatArea />

        {/* Settings Dialog */}
        <SettingsModal />
      </main>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
};

export default App;
