import React, { useRef, useEffect, useState } from 'react';
import { ChevronDown, FileText, X, FileUp, Globe, Compass, Loader2, GitBranch } from 'lucide-react';
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
    activeStreamStatus,
  } = useApp();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [isDragOverChat, setIsDragOverChat] = useState(false);

  // "Follow the stream" mode. True while the user is at the bottom. Scrolling up turns it off
  // so arriving tokens don't yank the view back down; reaching the bottom again turns it on.
  const stickToBottomRef = useRef(true);
  const lastScrollTopRef = useRef(0);

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    const el = scrollContainerRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior });
  };

  // Opening a different conversation: start following the bottom again.
  const firstMessageId = messages[0]?.id;
  useEffect(() => {
    stickToBottomRef.current = true;
  }, [firstMessageId]);

  const prevMessageCountRef = useRef(0);
  useEffect(() => {
    // Sending a message always jumps to the bottom. A send adds the user message and an empty
    // assistant message in one update, so look at everything that was just added.
    const prevCount = prevMessageCountRef.current;
    prevMessageCountRef.current = messages.length;
    if (messages.length > prevCount && messages.slice(prevCount).some((m) => m.role === 'user')) {
      stickToBottomRef.current = true;
    }
    if (stickToBottomRef.current) {
      scrollToBottom(isGenerating ? 'auto' : 'smooth');
    }
  }, [messages, isGenerating]);

  // Track where the user is: show/hide the scroll-to-bottom button and decide whether to follow.
  const handleScroll = () => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const { scrollTop, scrollHeight, clientHeight } = el;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    const movedUp = scrollTop < lastScrollTopRef.current - 1;
    lastScrollTopRef.current = scrollTop;

    if (distanceFromBottom <= 24) {
      stickToBottomRef.current = true; // back at the bottom: follow the stream again
    } else if (movedUp) {
      stickToBottomRef.current = false; // the user scrolled up: stop following
    }
    setShowScrollButton(distanceFromBottom > 200);
  };

  // Wheel-up is the earliest signal the user wants out, before the scroll event even fires.
  const handleWheel = (e: React.WheelEvent) => {
    if (e.deltaY < 0) stickToBottomRef.current = false;
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
        <div className="border-b border-moso-800/60 bg-moso-900/60 backdrop-blur-sm px-3 py-2 sm:px-6 md:px-8 z-10 shrink-0">
          <div className="w-full max-w-[760px] mx-auto flex items-center justify-between text-xs gap-2 sm:gap-3">
            <div className="flex items-center gap-1.5 sm:gap-2 text-moso-300 font-medium shrink-0">
              <FileText className="h-3.5 w-3.5 text-moso-accent" />
              <span className="hidden sm:inline">Active Document Context ({documents.length}):</span>
              <span className="sm:hidden text-[11px]">Docs ({documents.length}):</span>
            </div>
            <div className="flex items-center gap-1.5 sm:gap-2 overflow-x-auto py-0.5 scrollbar-thin">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center gap-1.5 px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-lg bg-moso-850 border border-moso-750 text-[11px] text-moso-300 hover:border-moso-650 transition-colors shrink-0"
                >
                  <span className="font-semibold text-rose-400 text-[9px] px-1 py-0.2 rounded bg-rose-500/10 border border-rose-500/20">
                    PDF
                  </span>
                  <span className="font-medium text-white truncate max-w-[120px] sm:max-w-[200px]" title={doc.filename}>
                    {doc.filename}
                  </span>
                  <span className="text-moso-500 text-[10px]">
                    ({doc.page_count}p)
                  </span>
                  <button
                    type="button"
                    onClick={() => removeDocument(doc.id)}
                    className="p-0.5 text-moso-400 hover:text-white rounded hover:bg-moso-700 transition-colors ml-0.5 cursor-pointer"
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
        onWheel={handleWheel}
        className="flex-1 flex flex-col overflow-y-auto px-3 sm:px-6 md:px-8 py-3 sm:py-4"
      >
        {messages.length === 0 ? (
          <WelcomeScreen onSelectPrompt={(prompt) => sendMessage(prompt)}>
            <ChatInput
              variant="hero"
              onSendMessage={sendMessage}
              isGenerating={isGenerating}
              onStopGeneration={stopGeneration}
            />
          </WelcomeScreen>
        ) : (
          <div className="w-full max-w-[760px] mx-auto space-y-1 sm:space-y-2">
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

            {/* Live Web & Tool Activity Indicator */}
            {isGenerating && activeStreamStatus && (
              <div className="flex items-center gap-2.5 py-1 text-[13px] text-moso-400 w-fit max-w-full animate-fade-in">
                {activeStreamStatus.tool === 'github_inspect' ? (
                  <GitBranch className="h-4 w-4 text-purple-400 shrink-0 animate-pulse" />
                ) : activeStreamStatus.tool === 'web_search' ? (
                  <Globe className="h-4 w-4 text-accent-400 shrink-0 animate-spin" />
                ) : activeStreamStatus.tool === 'web_fetch' ? (
                  <Compass className="h-4 w-4 text-sky-400 shrink-0 animate-pulse" />
                ) : (
                  <Loader2 className="h-4 w-4 text-accent-400 shrink-0 animate-spin" />
                )}
                <span className="font-medium text-moso-200 truncate">
                  {activeStreamStatus.message}
                </span>
              </div>
            )}

            <div ref={messagesEndRef} className="h-4" />
          </div>
        )}
      </div>

      {/* Floating Scroll-to-Bottom Button */}
      {showScrollButton && (
        <div className="absolute bottom-32 sm:bottom-36 right-4 sm:right-8 z-20 animate-fade-in">
          <Button
            variant="secondary"
            size="icon-sm"
            onClick={() => {
              stickToBottomRef.current = true;
              scrollToBottom('smooth');
            }}
            className="rounded-full shadow-md bg-moso-900 hover:bg-moso-850 border-moso-750"
            aria-label="Scroll to bottom"
          >
            <ChevronDown className="h-4 w-4 text-moso-200" />
          </Button>
        </div>
      )}

      {/* Composer pinned at the bottom once a conversation has started */}
      {messages.length > 0 && (
        <ChatInput
          onSendMessage={sendMessage}
          isGenerating={isGenerating}
          onStopGeneration={stopGeneration}
        />
      )}
    </div>
  );
};
