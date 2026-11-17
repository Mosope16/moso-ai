import React, { useState, useRef, useEffect } from 'react';
import {
  ArrowUp,
  Square,
  Paperclip,
  Cpu,
  X,
  AlertCircle,
  Loader2,
  FileUp,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { Button } from '../ui/Button';
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
    isMockMode,
    documents,
    isUploadingDocument,
    uploadError,
    uploadDocument,
    removeDocument,
    clearUploadError,
  } = useApp();

  const [input, setInput] = useState('');
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const currentModel = availableModels.find((m) => m.id === selectedModel);

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollHeight = textareaRef.current.scrollHeight;
      // Cap at 200px max height
      textareaRef.current.style.height = `${Math.min(scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
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
    // Reset file input so identical file can be re-selected if deleted
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

  return (
    <div className="w-full max-w-[880px] lg:max-w-[920px] mx-auto px-4 pb-4 pt-1 select-none">
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

      {/* Main Input Container with Drag and Drop Support */}
      <div
        onDragOver={handleDragOver}
        onDragEnter={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          'relative rounded-2xl bg-moso-900 border shadow-xl transition-all duration-150',
          isDraggingOver
            ? 'border-moso-accent border-dashed ring-2 ring-moso-accent/40 bg-moso-900/90'
            : 'border-moso-700/80 focus-within:border-moso-accent/50 focus-within:ring-1 focus-within:ring-moso-accent/30'
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
          <div className="absolute inset-0 bg-moso-900/95 backdrop-blur-sm rounded-2xl flex items-center justify-center gap-2 text-moso-accent z-30 pointer-events-none">
            <FileUp className="h-5 w-5 animate-bounce" />
            <span className="text-xs font-medium">Drop PDF here to attach to conversation</span>
          </div>
        )}

        {/* Top bar inside input: Active Model Pill */}
        <div className="flex items-center justify-between px-4 pt-2.5 pb-1 text-xs">
          <div className="flex items-center gap-1.5 text-moso-400">
            <Cpu className="h-3.5 w-3.5 text-moso-accent" />
            <span className="font-medium text-moso-300">
              {currentModel?.name || selectedModel}
            </span>
            <span className="text-[11px] text-moso-500 font-mono">
              ({currentModel?.size || 'Local'})
            </span>
          </div>

          <div className="text-[11px] text-moso-500 hidden sm:flex items-center gap-1">
            <span>Shift + Enter for new line</span>
          </div>
        </div>

        {/* Attached Documents and Upload Progress List */}
        {(documents.length > 0 || isUploadingDocument) && (
          <div className="px-4 pt-1.5 pb-1 flex flex-wrap gap-2 items-center">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="group flex items-center gap-2 pl-2.5 pr-2 py-1 rounded-lg bg-moso-800/90 border border-moso-700/80 text-xs text-moso-200 hover:border-moso-600 transition-colors max-w-full"
              >
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="px-1.5 py-0.2 text-[9px] font-bold tracking-wider rounded bg-rose-500/20 text-rose-400 border border-rose-500/30">
                    PDF
                  </span>
                  <span
                    className="font-medium text-moso-200 truncate max-w-[160px] sm:max-w-[260px]"
                    title={doc.filename}
                  >
                    {doc.filename}
                  </span>
                  <span className="text-[11px] text-moso-400 shrink-0">
                    ({doc.page_count} {doc.page_count === 1 ? 'page' : 'pages'} • {formatFileSize(doc.file_size)})
                  </span>
                </div>
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
              <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-moso-850 border border-moso-accent/40 text-xs text-moso-accent animate-pulse">
                <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />
                <span className="text-[11px] font-medium">Extracting & indexing PDF text...</span>
              </div>
            )}
          </div>
        )}

        {/* Text Area */}
        <div className="px-4 py-1.5">
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              documents.length > 0
                ? "Ask a question about the attached PDF document(s)..."
                : "Ask Moso AI anything..."
            }
            className="w-full bg-transparent text-white text-[15px] placeholder:text-moso-500 resize-none focus:outline-none min-h-[52px] max-h-48 leading-relaxed font-normal"
          />
        </div>

        {/* Bottom Actions Bar */}
        <div className="flex items-center justify-between px-3.5 pb-2.5 pt-1">
          {/* Left Actions: Attachment Button */}
          <div className="relative flex items-center gap-1">
            <button
              type="button"
              disabled={isUploadingDocument}
              onClick={() => fileInputRef.current?.click()}
              className={cn(
                'p-2 rounded-lg transition-colors cursor-pointer flex items-center gap-2 text-xs',
                isUploadingDocument
                  ? 'text-moso-500 cursor-not-allowed'
                  : documents.length > 0
                  ? 'text-moso-accent hover:text-white hover:bg-moso-800'
                  : 'text-moso-400 hover:text-white hover:bg-moso-800'
              )}
              title="Attach PDF document (max 20 MB)"
              aria-label="Attach PDF document"
            >
              {isUploadingDocument ? (
                <Loader2 className="h-4 w-4 animate-spin text-moso-accent" />
              ) : (
                <Paperclip className="h-4 w-4" />
              )}
              <span className="hidden sm:inline text-[12px] text-moso-400">
                {documents.length > 0 ? `${documents.length} PDF attached` : 'Attach PDF'}
              </span>
            </button>
          </div>

          {/* Right Action: Send or Stop Button */}
          <div className="flex items-center gap-2">
            {isGenerating ? (
              <Button
                variant="danger"
                size="sm"
                onClick={onStopGeneration}
                className="rounded-xl gap-1.5 px-3.5 py-2 font-medium"
              >
                <Square className="h-3 w-3 fill-current" />
                <span>Stop</span>
              </Button>
            ) : (
              <button
                type="button"
                disabled={!input.trim()}
                onClick={handleSend}
                className={cn(
                  'h-8.5 w-8.5 rounded-xl flex items-center justify-center transition-all duration-150',
                  input.trim()
                    ? 'bg-moso-accent text-moso-950 hover:bg-moso-accent-hover shadow-sm cursor-pointer'
                    : 'bg-moso-800 text-moso-500 cursor-not-allowed'
                )}
                aria-label="Send message"
              >
                <ArrowUp className="h-4.5 w-4.5 stroke-[2.5]" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Zero Telemetry Subline */}
      <div className="mt-2.5 text-center text-[11px] text-moso-500 flex items-center justify-center gap-1.5 select-none">
        <span
          className={cn(
            'h-1.5 w-1.5 rounded-full',
            isMockMode ? 'bg-cyan-400' : 'bg-emerald-500/80'
          )}
        />
        <span>
          {isMockMode
            ? 'Dev simulation • Zero telemetry • Local browser storage'
            : documents.length > 0
            ? 'Local PDF context active • Local inference • Zero telemetry'
            : 'Local inference • Zero telemetry • Stored in local SQLite'}
        </span>
      </div>
    </div>
  );
};
