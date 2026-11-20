import React, { useState, useRef, useEffect } from 'react';
import {
  ArrowUp,
  Square,
  Paperclip,
  Plus,
  X,
  AlertCircle,
  Loader2,
  FileUp,
  Globe,
  ChevronDown,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { cn } from '../../utils/cn';

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  isGenerating: boolean;
  onStopGeneration: () => void;
  /** 'hero' = centered on the empty screen, 'dock' = pinned under a conversation */
  variant?: 'hero' | 'dock';
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSendMessage,
  isGenerating,
  onStopGeneration,
  variant = 'dock',
}) => {
  const {
    selectedModel,
    availableModels,
    documents,
    isUploadingDocument,
    uploadError,
    uploadDocument,
    removeDocument,
    clearUploadError,
    openSettings,
    webSearchEnabled,
    setWebSearchEnabled,
  } = useApp();

  const [input, setInput] = useState('');
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const currentModel = availableModels.find((m) => m.id === selectedModel);

  // Start typing right away on desktop (skip on touch screens so the keyboard doesn't pop up)
  useEffect(() => {
    if (window.matchMedia('(pointer: fine)').matches) textareaRef.current?.focus();
  }, []);

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(scrollHeight, 180)}px`;
    }
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // On desktop, Enter sends and Shift+Enter creates a newline.
    // On mobile touchscreens (<768px), Enter creates a newline so user can type multiline naturally, and taps the Send button to submit.
    if (e.key === 'Enter' && !e.shiftKey) {
      if (typeof window !== 'undefined' && window.innerWidth >= 768) {
        e.preventDefault();
        handleSend();
      }
    }
  };

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || isGenerating) return;
    onSendMessage(trimmed);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await uploadDocument(file);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(false);

    const file = e.dataTransfer.files?.[0];
    if (file) {
      await uploadDocument(file);
    }
  };

  const hasAttachments = documents.length > 0 || isUploadingDocument;

  return (
    <div
      className={cn(
        'w-full mx-auto select-none',
        variant === 'hero'
          ? 'max-w-[720px]'
          : 'max-w-[760px] px-3 sm:px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-1'
      )}
    >
      {/* Upload Error Banner */}
      {uploadError && (
        <div className="flex items-center justify-between px-3.5 py-2 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 mb-2 shadow-sm animate-fade-in">
          <div className="flex items-center gap-2 min-w-0 pr-2">
            <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
            <span className="truncate">{uploadError}</span>
          </div>
          <button
            onClick={clearUploadError}
            className="text-rose-400 hover:text-rose-200 p-1 rounded-md hover:bg-rose-500/20 transition-colors cursor-pointer shrink-0"
            aria-label="Dismiss error"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Composer */}
      <div
        onDragOver={handleDragOver}
        onDragEnter={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          'relative rounded-[22px] bg-moso-900 border text-left transition-colors duration-150',
          'shadow-[0_1px_2px_rgb(0_0_0/0.04),0_8px_28px_rgb(0_0_0/0.07)]',
          isDraggingOver
            ? 'border-accent-500 border-dashed ring-2 ring-accent-500/30'
            : 'border-moso-750 focus-within:border-moso-600'
        )}
      >
        {/* Hidden Native File Input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          onChange={handleFileChange}
          className="hidden"
          disabled={isUploadingDocument}
        />

        {/* Drag Overlay Notice when dragging file */}
        {isDraggingOver && (
          <div className="absolute inset-0 rounded-[22px] bg-moso-900/95 backdrop-blur-sm flex items-center justify-center gap-2 text-accent-400 z-30 pointer-events-none">
            <FileUp className="h-4.5 w-4.5 animate-bounce" />
            <span className="text-xs font-medium">Drop PDF here to attach</span>
          </div>
        )}

        {/* Attached Documents Row */}
        {hasAttachments && (
          <div className="px-3.5 pt-3 pb-1 flex flex-wrap gap-1.5 sm:gap-2 items-center">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="group flex items-center gap-1.5 pl-2 pr-1.5 py-1 rounded-lg bg-moso-800/80 border border-moso-750 text-xs text-moso-200 max-w-full"
              >
                <span className="px-1.5 text-[9px] font-bold tracking-wider rounded bg-rose-500/15 text-rose-400">PDF</span>
                <span className="font-medium truncate max-w-[120px] sm:max-w-[240px]" title={doc.filename}>
                  {doc.filename}
                </span>
                <span className="text-[10px] text-moso-400 shrink-0">
                  ({doc.page_count}p, {formatFileSize(doc.file_size)})
                </span>
                <button
                  type="button"
                  onClick={() => removeDocument(doc.id)}
                  className="p-0.5 rounded text-moso-400 hover:text-white hover:bg-moso-700/60 transition-colors cursor-pointer shrink-0"
                  title="Remove document"
                  aria-label={`Remove ${doc.filename}`}
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}

            {isUploadingDocument && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-moso-850 border border-accent-500/40 text-xs text-accent-400 animate-pulse">
                <Loader2 className="h-3 w-3 animate-spin shrink-0" />
                <span className="text-[11px] font-medium">Reading PDF</span>
              </div>
            )}
          </div>
        )}

        {/* Text */}
        <textarea
          ref={textareaRef}
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            documents.length > 0
              ? 'Ask about the attached PDF'
              : webSearchEnabled
              ? 'Ask or search the web'
              : 'Ask Moso AI anything'
          }
          className="block w-full bg-transparent text-moso-100 text-[16px] placeholder:text-moso-500 resize-none focus:outline-none min-h-[28px] max-h-48 leading-relaxed px-4 pt-3.5 pb-1 scrollbar-none"
        />

        {/* Actions */}
        <div className="flex items-center justify-between gap-2 px-2.5 pb-2.5 pt-1">
          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled={isUploadingDocument}
              onClick={() => fileInputRef.current?.click()}
              className={cn(
                'h-9 w-9 rounded-full border flex items-center justify-center transition-colors cursor-pointer shrink-0',
                isUploadingDocument
                  ? 'border-moso-750 text-moso-500 cursor-not-allowed'
                  : documents.length > 0
                  ? 'border-accent-500/40 text-accent-400 bg-accent-500/10 hover:bg-accent-500/20'
                  : 'border-moso-750 text-moso-400 hover:text-white hover:bg-moso-800/70'
              )}
              title="Attach PDF document (max 20 MB)"
              aria-label="Attach PDF document"
            >
              {isUploadingDocument ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : documents.length > 0 ? (
                <Paperclip className="h-4 w-4" />
              ) : (
                <Plus className="h-[18px] w-[18px]" />
              )}
            </button>

            <button
              type="button"
              onClick={() => setWebSearchEnabled(!webSearchEnabled)}
              className={cn(
                'h-9 rounded-full border flex items-center justify-center gap-1.5 transition-colors cursor-pointer shrink-0',
                webSearchEnabled
                  ? 'px-3 border-accent-500/40 bg-accent-500/10 text-accent-400 hover:bg-accent-500/20'
                  : 'w-9 border-transparent text-moso-400 hover:text-white hover:bg-moso-800/70'
              )}
              title={webSearchEnabled ? 'Web search is on (click to turn off)' : 'Web search is off (click to turn on)'}
              aria-label="Toggle web search"
              aria-pressed={webSearchEnabled}
            >
              <Globe className="h-4 w-4" />
              {webSearchEnabled && <span className="text-[13px] font-medium">Web</span>}
            </button>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <button
              type="button"
              onClick={openSettings}
              title={`Active model: ${currentModel?.name || selectedModel} (click to change)`}
              className="hidden sm:flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[13px] text-moso-400 hover:text-white hover:bg-moso-800/70 transition-colors cursor-pointer"
            >
              <span className="max-w-[120px] truncate">{currentModel?.name || selectedModel}</span>
              <ChevronDown className="h-3 w-3" />
            </button>

            {isGenerating ? (
              <button
                type="button"
                onClick={onStopGeneration}
                className="h-9 w-9 rounded-full flex items-center justify-center bg-rose-500/15 text-rose-400 hover:bg-rose-500/25 transition-colors cursor-pointer"
                title="Stop generation"
                aria-label="Stop generation"
              >
                <Square className="h-3.5 w-3.5 fill-current" />
              </button>
            ) : (
              <button
                type="button"
                disabled={!input.trim()}
                onClick={handleSend}
                className={cn(
                  'h-9 w-9 rounded-full flex items-center justify-center transition-colors duration-150',
                  input.trim()
                    ? 'bg-moso-accent text-moso-950 hover:bg-moso-accent-hover cursor-pointer'
                    : 'bg-moso-800 text-moso-500 cursor-not-allowed'
                )}
                aria-label="Send message"
                title="Send message"
              >
                <ArrowUp className="h-4 w-4 stroke-[2.5]" />
              </button>
            )}
          </div>
        </div>
      </div>

      {variant === 'dock' && (
        <p className="text-center pt-2 text-[12px] text-moso-500">
          Moso AI can make mistakes.{' '}
          <button
            type="button"
            onClick={openSettings}
            className="underline underline-offset-2 hover:text-moso-300 transition-colors cursor-pointer"
          >
            Check important info.
          </button>
        </p>
      )}
    </div>
  );
};
