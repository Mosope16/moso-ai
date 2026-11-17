import React, { useState } from 'react';
import { Copy, Check, RotateCcw, AlertTriangle, User, BookOpen, ChevronDown, ChevronUp, FileText, Quote, X } from 'lucide-react';
import { Message, Citation } from '../../types';
import { formatMessageTime } from '../../utils/date';
import { MarkdownRenderer, InlineText } from './MarkdownRenderer';
import { cn } from '../../utils/cn';

interface MessageItemProps {
  message: Message;
  isLatest: boolean;
  onRegenerate?: () => void;
  showTimestamp?: boolean;
}

export const MessageItem: React.FC<MessageItemProps> = ({
  message,
  isLatest,
  onRegenerate,
  showTimestamp = true,
}) => {
  const [copied, setCopied] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [inspectingCitation, setInspectingCitation] = useState<Citation | null>(null);
  const isUser = message.role === 'user';

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.warn('Failed to copy response', e);
    }
  };

  const formattedTime = formatMessageTime(message.created_at);
  const hasCitations = !isUser && message.citations && message.citations.length > 0;

  return (
    <div
      className={cn(
        'group flex gap-4 py-4 px-3 sm:px-4 rounded-xl transition-colors duration-150',
        isUser ? 'bg-moso-900/40 justify-end' : 'bg-transparent justify-start'
      )}
    >
      {/* Assistant Avatar (Left) */}
      {!isUser && (
        <div className="shrink-0 pt-0.5 select-none">
          <div className="h-8 w-8 rounded-lg bg-moso-850 border border-moso-700/80 flex items-center justify-center p-1.5 shadow-xs">
            <img src="/logo.svg" alt="Moso AI" className="h-5 w-5" />
          </div>
        </div>
      )}

      {/* Message Content Container */}
      <div className={cn('flex flex-col min-w-0 max-w-full', isUser ? 'items-end' : 'items-start flex-1')}>
        {/* Author & Timestamp */}
        <div className="flex items-center gap-2 mb-2 text-[12px] text-moso-400 select-none">
          <span className="font-semibold text-moso-200">
            {isUser ? 'You' : 'Moso AI'}
          </span>
          {message.model && !isUser && (
            <span className="text-[11px] text-moso-500 font-mono">
              ({message.model})
            </span>
          )}
          {showTimestamp && formattedTime && (
            <span className="text-moso-500 text-[11px]">{formattedTime}</span>
          )}
        </div>

        {/* Message Body */}
        {isUser ? (
          <div className="bg-moso-800/90 text-moso-100 rounded-2xl rounded-tr-xs px-5 py-3.5 text-[15px] leading-relaxed max-w-2xl border border-moso-700/60 shadow-xs selection:bg-moso-accent/25">
            <div className="whitespace-pre-wrap break-words">
              <InlineText text={message.content} />
            </div>
          </div>
        ) : (
          <div className="w-full text-moso-100 text-[15px] sm:text-[16px] leading-[1.75] max-w-full">
            {message.error ? (
              <div className="flex items-start gap-2.5 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-rose-400" />
                <div>
                  <p className="font-semibold">Inference Error</p>
                  <p className="mt-0.5">{message.error}</p>
                </div>
              </div>
            ) : (
              <MarkdownRenderer
                content={message.content}
                isStreaming={message.is_streaming}
              />
            )}
          </div>
        )}

        {/* Source Citations Section */}
        {hasCitations && (
          <div className="w-full max-w-full mt-3.5 pt-3 border-t border-moso-800/80">
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={() => setSourcesOpen(!sourcesOpen)}
                className="flex items-center gap-1.5 text-xs font-medium text-emerald-400/90 hover:text-emerald-300 transition-colors py-1 cursor-pointer"
              >
                <BookOpen className="h-3.5 w-3.5 text-emerald-400" />
                <span>
                  Sources & Citations ({message.citations!.length})
                </span>
                {sourcesOpen ? (
                  <ChevronUp className="h-3.5 w-3.5 ml-0.5 text-moso-400" />
                ) : (
                  <ChevronDown className="h-3.5 w-3.5 ml-0.5 text-moso-400" />
                )}
              </button>
              <span className="text-[10px] text-moso-500 font-mono">Grounding Verified</span>
            </div>

            {/* Quick chips when collapsed or always visible summary */}
            <div className="flex flex-wrap gap-1.5 mt-2">
              {message.citations!.map((cit, idx) => (
                <button
                  key={`${cit.document_id}-${cit.page_number || idx}-${idx}`}
                  type="button"
                  onClick={() => setInspectingCitation(cit)}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-moso-850 hover:bg-moso-800 border border-moso-750/70 text-xs text-moso-300 hover:text-emerald-300 transition-colors cursor-pointer group/chip"
                  title="Click to inspect source passage"
                >
                  <span className="text-[11px] font-mono text-emerald-400/90 group-hover/chip:text-emerald-300">
                    [{idx + 1}]
                  </span>
                  <FileText className="h-3 w-3 text-moso-400 group-hover/chip:text-emerald-400" />
                  <span className="truncate max-w-[180px]">{cit.filename || cit.document_name || 'Document'}</span>
                  {cit.page_number && (
                    <span className="text-[11px] text-moso-500 font-mono">
                      p. {cit.page_number}
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* Expanded Source Details */}
            {sourcesOpen && (
              <div className="mt-3 space-y-2.5">
                {message.citations!.map((cit, idx) => (
                  <div
                    key={`exp-${cit.document_id}-${cit.page_number || idx}-${idx}`}
                    className="p-3 rounded-lg bg-moso-850/70 border border-moso-800 hover:border-moso-700 transition-colors text-xs"
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="inline-flex items-center justify-center h-4.5 w-4.5 rounded bg-emerald-500/15 text-emerald-400 font-mono text-[11px] font-bold">
                          {idx + 1}
                        </span>
                        <span className="font-medium text-moso-200">{cit.filename || cit.document_name || 'Document'}</span>
                        {cit.page_number && (
                          <span className="text-[11px] px-1.5 py-0.2 rounded bg-moso-800 text-moso-400 font-mono">
                            Page {cit.page_number}
                          </span>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => setInspectingCitation(cit)}
                        className="text-[11px] text-emerald-400 hover:text-emerald-300 transition-colors cursor-pointer"
                      >
                        Inspect Passage
                      </button>
                    </div>
                    <div className="text-moso-350 text-[12px] line-clamp-2 italic border-l-2 border-emerald-500/40 pl-2.5 mt-1.5">
                      "{cit.excerpt}"
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Assistant Actions Toolbar (Copy & Regenerate) */}
        {!isUser && !message.is_streaming && message.content && (
          <div className="flex items-center gap-1.5 mt-3 opacity-90 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity select-none">
            <button
              type="button"
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] text-moso-400 hover:text-white hover:bg-moso-800/80 transition-colors cursor-pointer border border-transparent hover:border-moso-700/60"
              title="Copy message text"
            >
              {copied ? (
                <>
                  <Check className="h-3.5 w-3.5 text-emerald-400" />
                  <span className="text-emerald-400 font-medium">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  <span>Copy</span>
                </>
              )}
            </button>

            {isLatest && onRegenerate && (
              <button
                type="button"
                onClick={onRegenerate}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] text-moso-400 hover:text-white hover:bg-moso-800/80 transition-colors cursor-pointer border border-transparent hover:border-moso-700/60"
                title="Regenerate this response"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                <span>Regenerate</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* User Avatar (Right) */}
      {isUser && (
        <div className="shrink-0 pt-0.5 select-none">
          <div className="h-8 w-8 rounded-lg bg-moso-750 border border-moso-650 flex items-center justify-center text-moso-300 shadow-xs">
            <User className="h-4.5 w-4.5" />
          </div>
        </div>
      )}

      {/* Inspect Passage Modal */}
      {inspectingCitation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="relative w-full max-w-lg bg-moso-900 border border-moso-750 rounded-xl shadow-2xl p-5 flex flex-col max-h-[80vh]">
            <div className="flex items-center justify-between pb-3 border-b border-moso-800">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
                  <Quote className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-moso-100 flex items-center gap-2">
                    <span>{inspectingCitation.filename || inspectingCitation.document_name || 'Document'}</span>
                    {inspectingCitation.page_number && (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-moso-800 text-emerald-400 border border-emerald-500/20">
                        Page {inspectingCitation.page_number}
                      </span>
                    )}
                  </h3>
                  <p className="text-[11px] text-moso-400">Grounded Evidence Excerpt</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setInspectingCitation(null)}
                className="text-moso-400 hover:text-moso-200 p-1 rounded-md hover:bg-moso-800 transition-colors cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 overflow-y-auto pr-1 flex-1">
              <div className="bg-moso-850/80 rounded-lg p-4 border-l-3 border-emerald-500 text-[13px] text-moso-150 leading-relaxed font-sans whitespace-pre-wrap">
                {inspectingCitation.excerpt}
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-moso-800 flex items-center justify-between text-xs text-moso-400">
              <span className="text-[11px]">Source document indexed via local SQLite FTS5</span>
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(inspectingCitation.excerpt);
                }}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-moso-800 hover:bg-moso-750 text-moso-200 text-[11px] font-medium transition-colors cursor-pointer"
              >
                <Copy className="h-3 w-3" />
                <span>Copy Passage</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
