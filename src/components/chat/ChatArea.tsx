import React, { useRef, useEffect, useState } from 'react';
import { ChevronDown, FileText, X, FileUp } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { WelcomeScreen } from './WelcomeScreen';
import { MessageItem } from '../message/MessageItem';
import { ChatInput } from '../input/ChatInput';
import { Button } from '../ui/Button';

export const ChatArea: React.FC = () => {
  const {
    messages,
    documents,
    removeDocument,
    uploadDocument,
    isGenerating,
    sendMessage,
    stopGeneration,
    regenerateLastResponse,
    settings,
  } = useApp();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [isDragOverChat, setIsDragOverChat] = useState(false);

  // Auto-scroll on new messages or during generation
  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  };

  useEffect(() => {
    // Only auto scroll if user is already near bottom
    if (scrollContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 150;
      if (isNearBottom || isGenerating) {
        scrollToBottom(isGenerating ? 'auto' : 'smooth');
      }
    }
  }, [messages, isGenerating]);

  // Monitor scroll position to show/hide the scroll-to-bottom button
  const handleScroll = () => {
    if (scrollContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
      const isScrolledUp = scrollHeight - scrollTop - clientHeight > 200;
      setShowScrollButton(isScrolledUp);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOverChat(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    // Only deactivate if leaving the container boundary
    if (e.currentTarget.contains(e.relatedTarget as Node)) return;
    setIsDragOverChat(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOverChat(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      await uploadDocument(file);
    }
  };

  return (
    <div
      onDragOver={handleDragOver}
      onDragEnter={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className="flex-1 flex flex-col h-full overflow-hidden bg-moso-950 relative"
    >
      {/* Drag Overlay for entire Chat Area */}
      {isDragOverChat && (
        <div className="absolute inset-0 bg-moso-950/85 backdrop-blur-sm z-30 flex flex-col items-center justify-center border-2 border-dashed border-moso-accent m-3 rounded-2xl pointer-events-none">
          <FileUp className="h-10 w-10 text-moso-accent animate-bounce mb-2" />
          <p className="text-sm font-semibold text-white">Drop PDF to attach to this conversation</p>
          <p className="text-xs text-moso-400 mt-1">Up to 20 MB • Local extraction & SQLite index</p>
        </div>
      )}

      {/* Active Attached Documents Banner */}
      {documents.length > 0 && (
        <div className="border-b border-moso-800/60 bg-moso-900/60 backdrop-blur-sm px-4 py-2 sm:px-6 md:px-8 z-10 shrink-0">
          <div className="max-w-3xl mx-auto flex items-center justify-between text-xs gap-3">
            <div className="flex items-center gap-2 text-moso-300 font-medium shrink-0">
              <FileText className="h-3.5 w-3.5 text-moso-accent" />
              <span>Active Document Context ({documents.length}):</span>
            </div>
            <div className="flex items-center gap-2 overflow-x-auto py-0.5 scrollbar-thin">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-moso-850 border border-moso-750 text-[11px] text-moso-300 hover:border-moso-650 transition-colors shrink-0"
                >
                  <span className="font-semibold text-rose-400 text-[9px] px-1 py-0.2 rounded bg-rose-500/10 border border-rose-500/20">
                    PDF
                  </span>
                  <span className="font-medium text-white truncate max-w-[140px] sm:max-w-[200px]" title={doc.filename}>
                    {doc.filename}
                  </span>
                  <span className="text-moso-500 text-[10px]">
                    ({doc.page_count}p)
                  </span>
                  <button
                    type="button"
                    onClick={() => removeDocument(doc.id)}
                    className="p-0.5 text-moso-400 hover:text-white rounded hover:bg-moso-700 transition-colors ml-0.5"
                    title={`Remove ${doc.filename}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Scrollable messages container */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 md:px-8 space-y-2"
      >
        {messages.length === 0 ? (
          <WelcomeScreen onSelectPrompt={(prompt) => sendMessage(prompt)} />
        ) : (
          <div className="max-w-3xl mx-auto space-y-4">
            {messages.map((message, index) => {
              const isLatest = index === messages.length - 1;
              return (
                <MessageItem
                  key={message.id}
                  message={message}
                  isLatest={isLatest}
                  onRegenerate={regenerateLastResponse}
                  showTimestamp={settings.appearance.showTimestamps}
                />
              );
            })}
            <div ref={messagesEndRef} className="h-4" />
          </div>
        )}
      </div>

      {/* Floating Scroll-to-Bottom Button */}
      {showScrollButton && (
        <div className="absolute bottom-24 right-8 z-20 animate-fade-in">
          <Button
            variant="secondary"
            size="icon-sm"
            onClick={() => scrollToBottom('smooth')}
            className="rounded-full shadow-lg bg-moso-850 hover:bg-moso-800 border-moso-700"
            aria-label="Scroll to bottom"
          >
            <ChevronDown className="h-4 w-4 text-moso-200" />
          </Button>
        </div>
      )}

      {/* Persistent Chat Input at bottom */}
      <ChatInput
        onSendMessage={sendMessage}
        isGenerating={isGenerating}
        onStopGeneration={stopGeneration}
      />
    </div>
  );
};
