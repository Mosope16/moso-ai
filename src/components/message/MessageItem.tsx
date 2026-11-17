import React, { useState } from 'react';
import { Copy, Check, RotateCcw, AlertTriangle, User } from 'lucide-react';
import { Message } from '../../types';
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

  return (
    <div
      className={cn(
        'group flex gap-3.5 py-4 px-3 sm:px-4 rounded-xl transition-colors duration-150',
        isUser ? 'bg-moso-900/40 justify-end' : 'bg-transparent justify-start'
      )}
    >
      {/* Assistant Avatar (Left) */}
      {!isUser && (
        <div className="shrink-0 pt-0.5 select-none">
          <div className="h-7 w-7 rounded-lg bg-moso-850 border border-moso-700/80 flex items-center justify-center p-1 shadow-xs">
            <img src="/logo.svg" alt="Moso AI" className="h-5 w-5" />
          </div>
        </div>
      )}

      {/* Message Content Container */}
      <div className={cn('flex flex-col min-w-0 max-w-full', isUser ? 'items-end' : 'items-start flex-1')}>
        {/* Author & Timestamp */}
        <div className="flex items-center gap-2 mb-1.5 text-[11px] text-moso-400 select-none">
          <span className="font-semibold text-moso-200">
            {isUser ? 'You' : 'Moso AI'}
          </span>
          {message.model && !isUser && (
            <span className="text-[10px] text-moso-500 font-mono">
              ({message.model})
            </span>
          )}
          {showTimestamp && formattedTime && (
            <span className="text-moso-500 text-[10px]">{formattedTime}</span>
          )}
        </div>

        {/* Message Body */}
        {isUser ? (
          <div className="bg-moso-800 text-moso-100 rounded-2xl rounded-tr-xs px-4 py-2.5 text-sm leading-relaxed max-w-2xl border border-moso-700/60 shadow-xs selection:bg-moso-accent/25">
            <div className="whitespace-pre-wrap break-words">
              <InlineText text={message.content} />
            </div>
          </div>
        ) : (
          <div className="w-full text-moso-100 text-sm leading-relaxed max-w-3xl">
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

        {/* Assistant Actions Toolbar (Copy & Regenerate) */}
        {!isUser && !message.is_streaming && message.content && (
          <div className="flex items-center gap-1 mt-2.5 opacity-0 group-hover:opacity-100 transition-opacity select-none">
            <button
              type="button"
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-2 py-1 rounded text-[11px] text-moso-400 hover:text-white hover:bg-moso-800 transition-colors cursor-pointer"
              title="Copy message text"
            >
              {copied ? (
                <>
                  <Check className="h-3 w-3 text-emerald-400" />
                  <span className="text-emerald-400 font-medium">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3" />
                  <span>Copy</span>
                </>
              )}
            </button>

            {isLatest && onRegenerate && (
              <button
                type="button"
                onClick={onRegenerate}
                className="flex items-center gap-1.5 px-2 py-1 rounded text-[11px] text-moso-400 hover:text-white hover:bg-moso-800 transition-colors cursor-pointer"
                title="Regenerate this response"
              >
                <RotateCcw className="h-3 w-3" />
                <span>Regenerate</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* User Avatar (Right) */}
      {isUser && (
        <div className="shrink-0 pt-0.5 select-none">
          <div className="h-7 w-7 rounded-lg bg-moso-750 border border-moso-650 flex items-center justify-center text-moso-300 shadow-xs">
            <User className="h-4 w-4" />
          </div>
        </div>
      )}
    </div>
  );
};
