import React, { useState, useRef, useEffect } from 'react';
import {
  ArrowUp,
  Square,
  Paperclip,
  Plus,
  Sparkles,
  X,
  AlertCircle,
  Loader2,
  FileUp,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { cn } from '../../utils/cn';

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  isGenerating: boolean;
  onStopGeneration: () => void;
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
  } = useApp();

  const [input, setInput] = useState('');
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [isMultiline, setIsMultiline] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const currentModel = availableModels.find((m) => m.id === selectedModel);

  // Auto-resize textarea height and determine multiline status
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollHeight = textareaRef.current.scrollHeight;
      setIsMultiline(scrollHeight > 34);
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
    setIsMultiline(false);
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
    <div className="w-full max-w-[820px] lg:max-w-[860px] mx-auto px-3 sm:px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-1 select-none">
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

      {/* AI Mistakes Disclaimer: Centered directly above the minimized typing pill bar */}
      <div className="text-center pb-2 select-none">
        <p className="text-[11.5px] sm:text-[12px] text-moso-400/80 font-normal tracking-tight inline-flex items-center justify-center gap-1">
          <span>Moso AI can make mistakes.</span>
          <button
            type="button"
            onClick={openSettings}
            className="underline underline-offset-2 hover:text-moso-200 transition-colors cursor-pointer"
          >
            Check important info.
          </button>
        </p>
      </div>

      {/* Minimized Pill Typing Bar */}
      <div
        onDragOver={handleDragOver}
        onDragEnter={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          'relative bg-moso-900/95 border border-moso-750/80 shadow-xl transition-all duration-200',
          isMultiline || hasAttachments ? 'rounded-2xl sm:rounded-3xl' : 'rounded-full',
          isDraggingOver
            ? 'border-emerald-500 border-dashed ring-2 ring-emerald-500/40 bg-moso-900'
            : 'focus-within:border-emerald-500/50 focus-within:ring-1 focus-within:ring-emerald-500/25'
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
          <div
            className={cn(
              'absolute inset-0 bg-moso-900/95 backdrop-blur-sm flex items-center justify-center gap-2 text-emerald-400 z-30 pointer-events-none',
              isMultiline || hasAttachments ? 'rounded-2xl sm:rounded-3xl' : 'rounded-full'
            )}
          >
            <FileUp className="h-4.5 w-4.5 animate-bounce" />
            <span className="text-xs font-medium">Drop PDF here to attach</span>
          </div>
        )}

        {/* Attached Documents Row (Inside container when documents are present) */}
        {hasAttachments && (
          <div className="px-3.5 pt-2.5 pb-1 flex flex-wrap gap-1.5 sm:gap-2 items-center border-b border-moso-800/60">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="group flex items-center gap-1.5 pl-2 pr-1.5 py-0.5 rounded-lg bg-moso-800/90 border border-moso-700/80 text-xs text-moso-200 hover:border-moso-600 transition-colors max-w-full"
              >
                <span className="px-1.5 py-0.2 text-[9px] font-bold tracking-wider rounded bg-rose-500/20 text-rose-400 border border-rose-500/30">
                  PDF
                </span>
                <span
                  className="font-medium text-moso-200 truncate max-w-[120px] sm:max-w-[240px]"
                  title={doc.filename}
                >
                  {doc.filename}
                </span>
                <span className="text-[10px] text-moso-400 shrink-0">
                  ({doc.page_count}p • {formatFileSize(doc.file_size)})
                </span>
                <button
                  type="button"
                  onClick={() => removeDocument(doc.id)}
                  className="p-0.5 rounded text-moso-400 hover:text-white hover:bg-moso-700 transition-colors cursor-pointer shrink-0"
                  title="Remove document"
                  aria-label={`Remove ${doc.filename}`}
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}

            {isUploadingDocument && (
              <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-lg bg-moso-850 border border-emerald-500/40 text-xs text-emerald-400 animate-pulse">
                <Loader2 className="h-3 w-3 animate-spin shrink-0" />
                <span className="text-[11px] font-medium">Extracting PDF...</span>
              </div>
            )}
          </div>
        )}

        {/* Main Input Row */}
        <div
          className={cn(
            'flex gap-1.5 sm:gap-2 px-2 sm:px-3 py-1.5 sm:py-2',
            isMultiline ? 'items-end' : 'items-center'
          )}
        >
          {/* Left: Plus / Attachment Button */}
          <button
            type="button"
            disabled={isUploadingDocument}
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              'h-8 w-8 sm:h-8.5 sm:w-8.5 rounded-full flex items-center justify-center transition-colors cursor-pointer shrink-0',
              isUploadingDocument
                ? 'text-moso-500 cursor-not-allowed'
                : documents.length > 0
                ? 'text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20'
                : 'text-moso-400 hover:text-white hover:bg-moso-800'
            )}
            title="Attach PDF document (max 20 MB)"
            aria-label="Attach PDF document"
          >
            {isUploadingDocument ? (
              <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />
            ) : documents.length > 0 ? (
              <Paperclip className="h-4 w-4 text-emerald-400" />
            ) : (
              <Plus className="h-4.5 w-4.5" />
            )}
          </button>

          {/* Center: Text Area */}
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              documents.length > 0
                ? 'Ask a question about the attached PDF...'
                : 'Ask Moso AI anything...'
            }
            className="flex-1 bg-transparent text-white text-[15px] sm:text-[15.5px] placeholder:text-zinc-500 resize-none focus:outline-none min-h-[24px] max-h-40 sm:max-h-48 leading-relaxed font-normal py-1 px-1 scrollbar-none"
          />

          {/* Right Actions: Model Pill & Send / Stop Button */}
          <div className="flex items-center gap-1.5 shrink-0">
            {/* Subtle Local Model Badge (matches ChatGPT Think button style) */}
            <button
              type="button"
              onClick={openSettings}
              title={`Active model: ${currentModel?.name || selectedModel} (Click to change)`}
              className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-moso-800/80 hover:bg-moso-750 text-xs text-moso-300 border border-moso-700/60 transition-colors cursor-pointer"
            >
              <Sparkles className="h-3 w-3 text-emerald-400" />
              <span className="text-[11px] font-medium max-w-[80px] truncate">
                {currentModel?.name.replace(/^(Qwen|Ollama)\s*/i, '') || '2B'}
              </span>
            </button>

            {/* Send or Stop Button */}
            {isGenerating ? (
              <button
                type="button"
                onClick={onStopGeneration}
                className="h-8 w-8 sm:h-8.5 sm:w-8.5 rounded-full flex items-center justify-center bg-rose-500/20 text-rose-400 hover:bg-rose-500/30 transition-all cursor-pointer shadow-xs"
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
                  'h-8 w-8 sm:h-8.5 sm:w-8.5 rounded-full flex items-center justify-center transition-all duration-150',
                  input.trim()
                    ? 'bg-emerald-500 text-moso-950 hover:bg-emerald-400 shadow-md cursor-pointer'
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
    </div>
  );
};
