import React, { useState } from 'react';
import {
  Copy,
  Check,
  RotateCcw,
  AlertTriangle,
  BookOpen,
  ChevronDown,
  ChevronUp,
  FileText,
  Quote,
  X,
  ShieldCheck,
  ShieldAlert,
  ShieldQuestion,
  CheckCircle2,
  AlertCircle,
  Globe,
  ExternalLink,
  GitBranch,
  Activity,
} from 'lucide-react';
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
  const [verificationOpen, setVerificationOpen] = useState(false);
  const [inspectingCitation, setInspectingCitation] = useState<Citation | null>(null);
  const [showDiagnostics, setShowDiagnostics] = useState(false);
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
      className={cn('group flex py-2.5 sm:py-3.5', isUser ? 'justify-end' : 'justify-start')}
    >
      {/* Message Content Container */}
      <div className={cn('flex flex-col min-w-0 max-w-full', isUser ? 'items-end' : 'items-start flex-1')}>
        {/* Verification badge (only shown for factual answers) */}
        <div className="flex items-center gap-2 mb-2 empty:hidden select-none">
          {/* Subtle Verification Indicator Badge if factual */}
          {!isUser && message.verification && message.verification.is_factual && (
            <button
              type="button"
              onClick={() => setVerificationOpen(!verificationOpen)}
              className={cn(
                'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors cursor-pointer border ml-1',
                message.verification.status === 'verified'
                  ? 'bg-accent-500/10 text-accent-400 border-accent-500/30 hover:bg-accent-500/20'
                  : message.verification.status === 'partially_verified'
                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/30 hover:bg-amber-500/20'
                  : 'bg-zinc-500/10 text-zinc-400 border-zinc-500/30 hover:bg-zinc-500/20'
              )}
              title="Click to view evidence verification audit"
            >
              {message.verification.status === 'verified' ? (
                <ShieldCheck className="h-3 w-3 text-accent-400" />
              ) : message.verification.status === 'partially_verified' ? (
                <ShieldAlert className="h-3 w-3 text-amber-400" />
              ) : (
                <ShieldQuestion className="h-3 w-3 text-zinc-400" />
              )}
              <span>
                {message.verification.status === 'verified'
                  ? 'Verified'
                  : message.verification.status === 'partially_verified'
                  ? 'Partially Verified'
                  : 'Unverified'}
              </span>
              {verificationOpen ? (
                <ChevronUp className="h-2.5 w-2.5 opacity-60" />
              ) : (
                <ChevronDown className="h-2.5 w-2.5 opacity-60" />
              )}
            </button>
          )}
        </div>

        {/* Message Body */}
        {isUser ? (
          <div className="bg-moso-800 text-moso-100 rounded-2xl px-4 py-2.5 sm:px-5 sm:py-3 text-[16px] leading-relaxed max-w-[88%] sm:max-w-[80%] selection:bg-moso-accent/25">
            <div className="whitespace-pre-wrap break-words">
              <InlineText text={message.content} />
            </div>
          </div>
        ) : (
          <div className="w-full text-moso-100 max-w-full min-w-0 break-words">
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

        {isUser && showTimestamp && formattedTime && (
          <span className="mt-1 mr-1 text-[11px] text-moso-500 opacity-0 group-hover:opacity-100 transition-opacity select-none">
            {formattedTime}
          </span>
        )}

        {/* Source Citations Section */}
        {hasCitations && (
          <div className="w-full max-w-full mt-3.5 pt-3 border-t border-moso-800/80">
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={() => setSourcesOpen(!sourcesOpen)}
                className="flex items-center gap-1.5 text-xs font-medium text-accent-400/90 hover:text-accent-300 transition-colors py-1 cursor-pointer"
              >
                <BookOpen className="h-3.5 w-3.5 text-accent-400" />
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
              {message.citations!.map((cit, idx) => {
                const isGit = cit.domain === 'github.com' || cit.document_id === 'github_inspect';
                const isWeb = cit.type === 'web' || !!cit.url;
                return (
                  <button
                    key={`${cit.document_id}-${cit.page_number || idx}-${idx}`}
                    type="button"
                    onClick={() => setInspectingCitation(cit)}
                    className={cn(
                      "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs transition-colors cursor-pointer group/chip",
                      isGit
                        ? "bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 text-purple-300 hover:text-white"
                        : isWeb
                        ? "bg-sky-500/10 hover:bg-sky-500/20 border border-sky-500/30 text-sky-300 hover:text-white"
                        : "bg-moso-850 hover:bg-moso-800 border border-moso-750/70 text-moso-300 hover:text-accent-300"
                    )}
                    title={isGit ? `GitHub Repository: ${cit.url || cit.title}` : isWeb ? `Web source: ${cit.url}` : "Click to inspect source passage"}
                  >
                    <span className={cn("text-[11px] font-mono", isGit ? "text-purple-400" : isWeb ? "text-sky-400" : "text-accent-400/90")}>
                      [{idx + 1}]
                    </span>
                    {isGit ? (
                      <GitBranch className="h-3 w-3 text-purple-400 shrink-0" />
                    ) : isWeb ? (
                      <Globe className="h-3 w-3 text-sky-400 shrink-0" />
                    ) : (
                      <FileText className="h-3 w-3 text-moso-400 group-hover/chip:text-accent-400 shrink-0" />
                    )}
                    <span className="truncate max-w-[180px]">
                      {isGit ? (cit.title?.replace('GitHub: ', '') || 'GitHub Repo') : isWeb ? (cit.domain || cit.title || 'Web Source') : (cit.filename || cit.document_name || 'Document')}
                    </span>
                    {cit.page_number && !isWeb && (
                      <span className="text-[11px] text-moso-500 font-mono">
                        p. {cit.page_number}
                      </span>
                    )}
                    {(isWeb || isGit) && cit.url && (
                      <ExternalLink className={cn("h-2.5 w-2.5 opacity-60 group-hover/chip:opacity-100", isGit ? "text-purple-400/70" : "text-sky-400/70")} />
                    )}
                  </button>
                );
              })}
            </div>

            {/* Expanded Source Details */}
            {sourcesOpen && (
              <div className="mt-3 space-y-2.5">
                {message.citations!.map((cit, idx) => {
                  const isWeb = cit.type === 'web' || !!cit.url;
                  return (
                    <div
                      key={`exp-${cit.document_id}-${cit.page_number || idx}-${idx}`}
                      className="p-3 rounded-lg bg-moso-850/70 border border-moso-800 hover:border-moso-700 transition-colors text-xs"
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2 min-w-0 pr-2">
                          <span className={cn(
                            "inline-flex items-center justify-center h-4.5 w-4.5 rounded font-mono text-[11px] font-bold shrink-0",
                            isWeb ? "bg-sky-500/15 text-sky-400" : "bg-accent-500/15 text-accent-400"
                          )}>
                            {idx + 1}
                          </span>
                          {isWeb && <Globe className="h-3.5 w-3.5 text-sky-400 shrink-0" />}
                          <span className="font-medium text-moso-200 truncate">{cit.filename || cit.title || cit.document_name || 'Source'}</span>
                          {isWeb && cit.domain && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-sky-500/10 border border-sky-500/20 text-sky-400 font-mono shrink-0">
                              {cit.domain}
                            </span>
                          )}
                          {cit.page_number && !isWeb && (
                            <span className="text-[11px] px-1.5 py-0.2 rounded bg-moso-800 text-moso-400 font-mono shrink-0">
                              Page {cit.page_number}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {isWeb && cit.url && (
                            <a
                              href={cit.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-[11px] text-sky-400 hover:text-sky-300 underline underline-offset-2 transition-colors cursor-pointer"
                            >
                              <span>Open</span>
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                          <button
                            type="button"
                            onClick={() => setInspectingCitation(cit)}
                            className="text-[11px] text-accent-400 hover:text-accent-300 transition-colors cursor-pointer"
                          >
                            Inspect Excerpt
                          </button>
                        </div>
                      </div>
                      <div className="text-moso-350 text-[12px] line-clamp-2 italic border-l-2 border-accent-500/40 pl-2.5 mt-1.5">
                        "{cit.excerpt}"
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Expandable Verification Audit Card */}
        {!isUser && verificationOpen && message.verification && message.verification.is_factual && (
          <div className="w-full mt-3 p-3.5 rounded-xl bg-moso-850/80 border border-moso-750/70 text-xs space-y-3 animate-fade-in shadow-xs">
            <div className="flex items-center justify-between pb-2 border-b border-moso-750/50">
              <div className="flex items-center gap-2">
                {message.verification.status === 'verified' ? (
                  <ShieldCheck className="h-4 w-4 text-accent-400" />
                ) : message.verification.status === 'partially_verified' ? (
                  <ShieldAlert className="h-4 w-4 text-amber-400" />
                ) : (
                  <ShieldQuestion className="h-4 w-4 text-zinc-400" />
                )}
                <div>
                  <h4 className="font-semibold text-moso-100 text-[12.5px] capitalize">
                    {message.verification.category} Verification Audit
                  </h4>
                  <p className="text-[10.5px] text-moso-400">
                    Evidence Tier {message.verification.tier || 4}: {message.verification.tier_name?.replace('_', ' ') || 'General Knowledge'}
                  </p>
                </div>
              </div>
              <span
                className={cn(
                  'text-[10px] font-medium px-2 py-0.5 rounded-md border',
                  message.verification.status === 'verified'
                    ? 'bg-accent-500/10 text-accent-400 border-accent-500/30'
                    : message.verification.status === 'partially_verified'
                    ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                    : 'bg-zinc-500/10 text-zinc-400 border-zinc-500/30'
                )}
              >
                {message.verification.status.toUpperCase().replace('_', ' ')}
              </span>
            </div>

            {/* Disclaimer / Uncertainty acknowledgement if present */}
            {message.verification.disclaimer && (
              <div className="flex items-start gap-2 p-2.5 rounded-lg bg-moso-900/80 border border-moso-700/60 text-moso-300 text-[11.5px] leading-relaxed">
                <AlertCircle className="h-3.5 w-3.5 text-amber-400 shrink-0 mt-0.5" />
                <span>{message.verification.disclaimer}</span>
              </div>
            )}

            {/* Verified claims */}
            {message.verification.verified_claims && message.verification.verified_claims.length > 0 && (
              <div className="space-y-1">
                <div className="text-[11px] font-medium text-accent-400 flex items-center gap-1.5">
                  <CheckCircle2 className="h-3 w-3" />
                  <span>Verified Claims & Grounding</span>
                </div>
                <ul className="space-y-1 pl-4 text-[11.5px] text-moso-250 list-disc marker:text-accent-500">
                  {message.verification.verified_claims.map((claim, idx) => (
                    <li key={`vc-${idx}`}>{claim}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Unverified claims */}
            {message.verification.unverified_claims && message.verification.unverified_claims.length > 0 && (
              <div className="space-y-1">
                <div className="text-[11px] font-medium text-amber-400 flex items-center gap-1.5">
                  <AlertCircle className="h-3 w-3" />
                  <span>Unverified Claims / Limitations</span>
                </div>
                <ul className="space-y-1 pl-4 text-[11.5px] text-moso-350 list-disc marker:text-amber-500">
                  {message.verification.unverified_claims.map((claim, idx) => (
                    <li key={`uvc-${idx}`}>{claim}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Quotation Verification */}
            {message.verification.quotation_check?.has_quotes && (
              <div className="pt-2 border-t border-moso-800/80 space-y-1.5">
                <div className="text-[11px] font-medium text-moso-300 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <Quote className="h-3 w-3 text-moso-400" />
                    <span>
                      Quotation Audit ({message.verification.quotation_check.quotes_count || 0} quotes checked)
                    </span>
                  </span>
                  <span
                    className={cn(
                      'text-[10px] font-mono',
                      message.verification.quotation_check.all_quotes_verified
                        ? 'text-accent-400'
                        : 'text-amber-400'
                    )}
                  >
                    {message.verification.quotation_check.all_quotes_verified
                      ? 'All Quotes Aligned'
                      : 'Quotation Discrepancy'}
                  </span>
                </div>
                {message.verification.quotation_check.details?.map((qd, qidx) => (
                  <div
                    key={`qd-${qidx}`}
                    className="p-2 rounded bg-moso-900/60 border border-moso-800 text-[11px] flex items-center justify-between gap-2"
                  >
                    <span className="italic truncate max-w-[280px] text-moso-300">"{qd.quote}"</span>
                    <span
                      className={cn(
                        'font-mono text-[10px] shrink-0',
                        qd.verified ? 'text-accent-400' : 'text-amber-400'
                      )}
                    >
                      {qd.verified
                        ? `✓ Match (${Math.round(qd.overlap_score * 100)}%)`
                        : `⚠ Unaligned (${Math.round(qd.overlap_score * 100)}%)`}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Sources Consulted List */}
            {message.verification.sources_consulted && message.verification.sources_consulted.length > 0 && (
              <div className="pt-2 border-t border-moso-800/80 text-[11px] text-moso-400 flex items-center justify-between">
                <span>Sources Consulted: {message.verification.sources_consulted.length}</span>
                <span className="font-mono text-[10px] text-moso-500">Local Verified Index</span>
              </div>
            )}
          </div>
        )}

        {/* Assistant Actions Toolbar (Copy & Regenerate) */}
        {!isUser && !message.is_streaming && message.content && (
          <div className={cn('flex items-center gap-0.5 mt-2 transition-opacity select-none', isLatest ? 'opacity-100' : 'opacity-100 sm:opacity-0 sm:group-hover:opacity-100')}>
            <button
              type="button"
              onClick={handleCopy}
              className="flex items-center gap-1.5 p-1.5 rounded-lg text-[12.5px] text-moso-500 hover:text-white hover:bg-moso-800/70 transition-colors cursor-pointer"
              title="Copy message text"
            >
              {copied ? (
                <>
                  <Check className="h-3.5 w-3.5 text-accent-400" />
                  <span className="text-accent-400 font-medium">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  <span className="sr-only">Copy</span>
                </>
              )}
            </button>

            {isLatest && onRegenerate && (
              <button
                type="button"
                onClick={onRegenerate}
                className="flex items-center gap-1.5 p-1.5 rounded-lg text-[12.5px] text-moso-500 hover:text-white hover:bg-moso-800/70 transition-colors cursor-pointer"
                title="Regenerate this response"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                <span className="sr-only">Regenerate</span>
              </button>
            )}

            {message.diagnostics && message.diagnostics.length > 0 && (
              <button
                type="button"
                onClick={() => setShowDiagnostics(true)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] text-purple-400 hover:text-purple-300 hover:bg-purple-500/10 transition-colors cursor-pointer border border-purple-500/20"
                title="View Evidence Retrieval Diagnostics & Provenance"
              >
                <Activity className="h-3.5 w-3.5" />
                <span>Diagnostics ({message.diagnostics.length})</span>
              </button>
            )}

            {(message.model || (showTimestamp && formattedTime)) && (
              <span className="ml-2 text-[12px] text-moso-500">
                {[message.model, showTimestamp ? formattedTime : ''].filter(Boolean).join(', ')}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Inspect Passage Modal */}
      {inspectingCitation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="relative w-full max-w-lg bg-moso-900 border border-moso-750 rounded-xl shadow-2xl p-5 flex flex-col max-h-[80vh]">
            <div className="flex items-center justify-between pb-3 border-b border-moso-800">
              <div className="flex items-center gap-2">
                <div className={cn(
                  "p-1.5 rounded-lg",
                  inspectingCitation.url || inspectingCitation.type === 'web'
                    ? "bg-sky-500/10 text-sky-400"
                    : "bg-accent-500/10 text-accent-400"
                )}>
                  {inspectingCitation.url || inspectingCitation.type === 'web' ? (
                    <Globe className="h-4 w-4" />
                  ) : (
                    <Quote className="h-4 w-4" />
                  )}
                </div>
                <div className="min-w-0 pr-2">
                  <h3 className="text-sm font-semibold text-moso-100 flex items-center gap-2 truncate">
                    <span className="truncate">
                      {inspectingCitation.title || inspectingCitation.filename || inspectingCitation.document_name || (inspectingCitation.url ? 'Web Source' : 'Document')}
                    </span>
                    {inspectingCitation.page_number && (
                      <span className="shrink-0 text-[10px] font-mono px-1.5 py-0.5 rounded bg-moso-800 text-accent-400 border border-accent-500/20">
                        Page {inspectingCitation.page_number}
                      </span>
                    )}
                    {inspectingCitation.domain && (
                      <span className="shrink-0 text-[10px] font-mono px-1.5 py-0.5 rounded bg-sky-950/70 text-sky-300 border border-sky-800/40">
                        {inspectingCitation.domain}
                      </span>
                    )}
                  </h3>
                  <p className="text-[11px] text-moso-400">
                    {inspectingCitation.url || inspectingCitation.type === 'web'
                      ? 'Live Web Evidence'
                      : 'Grounded Evidence Excerpt'}
                    {inspectingCitation.published_date && ` • ${inspectingCitation.published_date}`}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setInspectingCitation(null)}
                className="text-moso-400 hover:text-moso-200 p-1 rounded-md hover:bg-moso-800 transition-colors cursor-pointer shrink-0"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 overflow-y-auto pr-1 flex-1">
              <div className={cn(
                "rounded-lg p-4 text-[13px] text-moso-150 leading-relaxed font-sans whitespace-pre-wrap",
                inspectingCitation.url || inspectingCitation.type === 'web'
                  ? "bg-moso-850/80 border-l-3 border-sky-500"
                  : "bg-moso-850/80 border-l-3 border-accent-500"
              )}>
                {inspectingCitation.excerpt}
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-moso-800 flex items-center justify-between text-xs text-moso-400 gap-2">
              <span className="text-[11px] truncate">
                {inspectingCitation.url
                  ? 'Retrieved via secure Web Search / Fetch'
                  : 'Source document indexed via local SQLite FTS5'}
              </span>
              <div className="flex items-center gap-2 shrink-0">
                {inspectingCitation.url && (
                  <a
                    href={inspectingCitation.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-sky-950/80 hover:bg-sky-900 border border-sky-700/50 text-sky-300 text-[11px] font-medium transition-colors"
                  >
                    <ExternalLink className="h-3 w-3" />
                    <span>Open URL</span>
                  </a>
                )}
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
        </div>
      )}
      {/* Developer Retrieval Diagnostics Modal */}
      {showDiagnostics && message.diagnostics && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="relative w-full max-w-2xl bg-moso-900 border border-moso-750 rounded-xl shadow-2xl p-5 flex flex-col max-h-[85vh]">
            <div className="flex items-center justify-between pb-3 border-b border-moso-800">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-400">
                  <Activity className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-moso-100">
                    Retrieval Evidence Diagnostics
                  </h3>
                  <p className="text-[11px] text-moso-400">
                    Evidence contract verification, provenance & source identity audit
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowDiagnostics(false)}
                className="text-moso-400 hover:text-moso-200 p-1 rounded-md hover:bg-moso-800 transition-colors cursor-pointer shrink-0"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 overflow-y-auto pr-1 flex-1 space-y-3">
              {message.diagnostics.map((diag, idx) => (
                <div
                  key={idx}
                  className={cn(
                    "rounded-lg p-3.5 border text-xs font-mono",
                    diag.success
                      ? "bg-moso-850/80 border-accent-500/30"
                      : "bg-moso-850/80 border-rose-500/30"
                  )}
                >
                  <div className="flex items-center justify-between pb-2 border-b border-moso-800/80">
                    <span className="font-semibold text-moso-200 flex items-center gap-1.5">
                      {diag.tool === 'github_inspect' && <GitBranch className="h-3.5 w-3.5 text-purple-400" />}
                      {diag.tool === 'web_search' && <Globe className="h-3.5 w-3.5 text-accent-400" />}
                      {diag.tool === 'web_fetch' && <Globe className="h-3.5 w-3.5 text-sky-400" />}
                      {diag.tool}
                    </span>
                    <span
                      className={cn(
                        "px-2 py-0.5 rounded text-[10px] font-bold uppercase",
                        diag.success
                          ? "bg-accent-500/20 text-accent-400 border border-accent-500/30"
                          : "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                      )}
                    >
                      {diag.success ? "Verified" : (diag.error_type || "Failed")}
                    </span>
                  </div>

                  <div className="mt-2.5 space-y-1 text-moso-300">
                    <div>
                      <span className="text-moso-500">Requested: </span>
                      <span className="text-moso-200 select-all">{diag.requested_url || 'N/A'}</span>
                    </div>
                    {diag.resolved_url && diag.resolved_url !== diag.requested_url && (
                      <div>
                        <span className="text-moso-500">Resolved: </span>
                        <span className="text-moso-200 select-all">{diag.resolved_url}</span>
                      </div>
                    )}
                    <div className="flex flex-wrap gap-x-4 gap-y-1 pt-1 text-[11px]">
                      <span>HTTP Status: <strong className="text-moso-200">{diag.http_status ?? 'N/A'}</strong></span>
                      <span>Content Length: <strong className="text-moso-200">{diag.content_length} chars</strong></span>
                      {diag.identity_verified !== null && diag.identity_verified !== undefined && (
                        <span>
                          Identity Verified: <strong className={diag.identity_verified ? "text-accent-400" : "text-rose-400"}>
                            {diag.identity_verified ? "YES" : "NO"}
                          </strong>
                        </span>
                      )}
                    </div>
                    {diag.files_retrieved && diag.files_retrieved.length > 0 && (
                      <div className="pt-1 text-[11px]">
                        <span className="text-moso-500">Retrieved Files: </span>
                        <span className="text-purple-300">{diag.files_retrieved.join(', ')}</span>
                      </div>
                    )}
                    {diag.error && (
                      <div className="mt-2 p-2 rounded bg-rose-950/40 border border-rose-800/40 text-rose-300 text-[11px]">
                        <span className="font-bold">Error Detail: </span>{diag.error}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-4 pt-3 border-t border-moso-800 flex items-center justify-between text-xs text-moso-400">
              <span className="text-[11px]">Evidence Contract & Grounding Assurance</span>
              <button
                type="button"
                onClick={() => setShowDiagnostics(false)}
                className="px-3 py-1 rounded bg-moso-800 hover:bg-moso-750 text-moso-200 text-[11px] font-medium transition-colors cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
