import React, { useState, useMemo } from 'react';
import { Copy, Check } from 'lucide-react';
import katex from 'katex';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { cn } from '../../utils/cn';

// Unified remark/rehype math plugin configuration
export const mathPlugins = {
  remark: [remarkMath],
  rehype: [[rehypeKatex, { throwOnError: false, errorColor: '#f87171' }]],
};

interface MarkdownRendererProps {
  content: string;
  isStreaming?: boolean;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, isStreaming }) => {
  // Parse markdown into structured segments: code blocks, block math, tables, prose
  const segments = useMemo(() => parseMarkdownSegments(content), [content]);

  return (
    <div className={cn('prose-moso leading-relaxed space-y-3', isStreaming && 'typing-cursor')}>
      {segments.map((seg, idx) => {
        if (seg.type === 'code') {
          return (
            <CodeBlock
              key={idx}
              language={seg.language || 'text'}
              code={seg.code}
            />
          );
        }

        if (seg.type === 'math-block') {
          return (
            <MathView
              key={idx}
              math={seg.math}
              displayMode={true}
              rawText={seg.rawText}
            />
          );
        }

        if (seg.type === 'table') {
          return <MarkdownTable key={idx} headers={seg.headers} rows={seg.rows} />;
        }

        return <ProseSegment key={idx} text={seg.text} />;
      })}
    </div>
  );
};

// ---------------------------------------------------------
// Segment Models & Parser
// ---------------------------------------------------------

interface CodeSegment {
  type: 'code';
  language: string;
  code: string;
}

interface MathBlockSegment {
  type: 'math-block';
  math: string;
  rawText?: string;
}

interface TableSegment {
  type: 'table';
  headers: string[];
  rows: string[][];
}

interface TextSegment {
  type: 'text';
  text: string;
}

type Segment = CodeSegment | MathBlockSegment | TableSegment | TextSegment;

function parseMarkdownSegments(markdown: string): Segment[] {
  const segments: Segment[] = [];
  const lines = markdown.split('\n');

  let currentCodeLines: string[] = [];
  let currentTextLines: string[] = [];
  let currentLang = '';
  let inCodeBlock = false;

  const flushText = () => {
    if (currentTextLines.length > 0) {
      // Process text lines to detect multi-line block math and tables
      const subSegments = extractBlockMathAndTables(currentTextLines);
      segments.push(...subSegments);
      currentTextLines = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.trim().startsWith('```')) {
      if (!inCodeBlock) {
        // Starting a code block
        flushText();
        inCodeBlock = true;
        currentLang = line.trim().slice(3).trim();
        currentCodeLines = [];
      } else {
        // Ending a code block
        inCodeBlock = false;
        // If the code block is marked ```math, render it as a block math equation!
        if (currentLang.toLowerCase() === 'math' || currentLang.toLowerCase() === 'latex-math') {
          segments.push({
            type: 'math-block',
            math: currentCodeLines.join('\n').trim(),
          });
        } else {
          segments.push({
            type: 'code',
            language: currentLang,
            code: currentCodeLines.join('\n'),
          });
        }
        currentCodeLines = [];
        currentLang = '';
      }
    } else if (inCodeBlock) {
      currentCodeLines.push(line);
    } else {
      currentTextLines.push(line);
    }
  }

  // Handle unclosed code blocks during streaming
  if (inCodeBlock && currentCodeLines.length > 0) {
    if (currentLang.toLowerCase() === 'math') {
      segments.push({
        type: 'math-block',
        math: currentCodeLines.join('\n').trim(),
      });
    } else {
      segments.push({
        type: 'code',
        language: currentLang,
        code: currentCodeLines.join('\n'),
      });
    }
  } else {
    flushText();
  }

  return segments;
}

// Extract multi-line block equations (\[ ... \] and $$ ... $$) and markdown tables
function extractBlockMathAndTables(lines: string[]): Segment[] {
  const segments: Segment[] = [];
  let buffer: string[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // 1. Check for starting multi-line block math \[
    if (trimmed === '\\[' || (trimmed.startsWith('\\[') && !trimmed.endsWith('\\]'))) {
      if (buffer.length > 0) {
        segments.push({ type: 'text', text: buffer.join('\n') });
        buffer = [];
      }

      const mathLines: string[] = [line.replace(/^\s*\\\[/, '')];
      i++;
      let closed = false;

      while (i < lines.length) {
        const nextLine = lines[i];
        if (nextLine.trim().endsWith('\\]')) {
          mathLines.push(nextLine.replace(/\\\]\s*$/, ''));
          closed = true;
          i++;
          break;
        }
        mathLines.push(nextLine);
        i++;
      }

      const rawFormula = mathLines.join('\n').trim();
      if (closed || rawFormula.length > 0) {
        segments.push({
          type: 'math-block',
          math: rawFormula,
          rawText: `\\[\n${rawFormula}\n\\]`,
        });
      }
      continue;
    }

    // 2. Check for starting multi-line block math $$
    if (trimmed === '$$' || (trimmed.startsWith('$$') && trimmed.length > 2 && !trimmed.slice(2).includes('$$'))) {
      if (buffer.length > 0) {
        segments.push({ type: 'text', text: buffer.join('\n') });
        buffer = [];
      }

      const mathLines: string[] = [line.replace(/^\s*\$\$/, '')];
      i++;
      let closed = false;

      while (i < lines.length) {
        const nextLine = lines[i];
        if (nextLine.trim().endsWith('$$') || nextLine.trim() === '$$') {
          mathLines.push(nextLine.replace(/\$\$\s*$/, ''));
          closed = true;
          i++;
          break;
        }
        mathLines.push(nextLine);
        i++;
      }

      const rawFormula = mathLines.join('\n').trim();
      if (closed || rawFormula.length > 0) {
        segments.push({
          type: 'math-block',
          math: rawFormula,
          rawText: `$$\n${rawFormula}\n$$`,
        });
      }
      continue;
    }

    // 3. Check for markdown table (header + delimiter row)
    if (
      (trimmed.startsWith('|') || trimmed.includes('|')) &&
      i + 1 < lines.length &&
      /^\|?(\s*:?-+:?\s*\|?)+$/.test(lines[i + 1].trim())
    ) {
      if (buffer.length > 0) {
        segments.push({ type: 'text', text: buffer.join('\n') });
        buffer = [];
      }

      const splitRow = (row: string) => {
        let clean = row.trim();
        if (clean.startsWith('|')) clean = clean.slice(1);
        if (clean.endsWith('|')) clean = clean.slice(0, -1);
        return clean.split('|').map((c) => c.trim());
      };

      const headers = splitRow(lines[i]);
      i += 2; // skip header and delimiter

      const rows: string[][] = [];
      while (i < lines.length) {
        const rowLine = lines[i].trim();
        if (!rowLine.includes('|') || rowLine.length === 0) {
          break;
        }
        rows.push(splitRow(rowLine));
        i++;
      }

      segments.push({ type: 'table', headers, rows });
      continue;
    }

    buffer.push(line);
    i++;
  }

  if (buffer.length > 0) {
    segments.push({ type: 'text', text: buffer.join('\n') });
  }

  return segments;
}

// ---------------------------------------------------------
// KaTeX Math View Component
// ---------------------------------------------------------

export const MathView: React.FC<{
  math: string;
  displayMode: boolean;
  rawText?: string;
}> = ({ math, displayMode, rawText }) => {
  const renderedHtml = useMemo(() => {
    try {
      return katex.renderToString(math, {
        displayMode,
        throwOnError: false,
        errorColor: '#f87171',
        strict: false,
        trust: false,
      });
    } catch (err) {
      console.warn('KaTeX render error:', err);
      return null;
    }
  }, [math, displayMode]);

  if (!renderedHtml) {
    // Fallback on unexpected failure
    return (
      <span
        className="text-rose-400 font-mono text-xs bg-rose-500/10 border border-rose-500/20 px-1.5 py-0.5 rounded inline-block"
        title="KaTeX parsing error"
      >
        {rawText || (displayMode ? `\\[${math}\\]` : `\\(${math}\\)`)}
      </span>
    );
  }

  if (displayMode) {
    return (
      <div
        className="my-3 overflow-x-auto overflow-y-hidden py-2 px-1 text-center max-w-full scrollbar-thin text-moso-100 font-normal"
        dangerouslySetInnerHTML={{ __html: renderedHtml }}
      />
    );
  }

  return (
    <span
      className="inline-block max-w-full overflow-x-auto align-middle px-0.5 mx-0.5"
      dangerouslySetInnerHTML={{ __html: renderedHtml }}
    />
  );
};

// ---------------------------------------------------------
// Code Block Component with Copy Button
// ---------------------------------------------------------

const CodeBlock: React.FC<{ language: string; code: string }> = ({ language, code }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.warn('Failed to copy code to clipboard', e);
    }
  };

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-moso-700/80 bg-moso-950 font-mono text-xs shadow-md">
      {/* Code Header Bar */}
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-moso-900 border-b border-moso-800 text-moso-400 select-none">
        <span className="font-semibold text-[11px] text-moso-300 uppercase tracking-wider">
          {language || 'code'}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] hover:text-white hover:bg-moso-800 transition-colors cursor-pointer"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-emerald-400" />
              <span className="text-emerald-400 font-medium">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              <span>Copy code</span>
            </>
          )}
        </button>
      </div>

      {/* Code Content (Strictly preserves raw text including any LaTeX) */}
      <div className="p-3.5 overflow-x-auto text-moso-100 leading-relaxed font-normal selection:bg-moso-accent/25">
        <pre className="m-0 p-0 whitespace-pre">
          <code>{code}</code>
        </pre>
      </div>
    </div>
  );
};

// ---------------------------------------------------------
// Prose Segment Formatter (Headings, Lists, Paragraphs)
// ---------------------------------------------------------

const ProseSegment: React.FC<{ text: string }> = ({ text }) => {
  const paragraphs = text.split('\n\n').filter((p) => p.trim().length > 0);

  return (
    <>
      {paragraphs.map((p, idx) => {
        const trimmed = p.trim();

        // Heading 1 (#)
        if (trimmed.startsWith('# ')) {
          return (
            <h1 key={idx} className="text-xl font-bold text-white tracking-tight mt-4 mb-2">
              <InlineText text={trimmed.slice(2)} />
            </h1>
          );
        }

        // Heading 2 (##)
        if (trimmed.startsWith('## ')) {
          return (
            <h2 key={idx} className="text-lg font-semibold text-white tracking-tight mt-3 mb-1.5">
              <InlineText text={trimmed.slice(3)} />
            </h2>
          );
        }

        // Heading 3 (###)
        if (trimmed.startsWith('### ')) {
          return (
            <h3 key={idx} className="text-sm font-semibold text-moso-100 tracking-tight mt-2.5 mb-1">
              <InlineText text={trimmed.slice(4)} />
            </h3>
          );
        }

        // Blockquote (>)
        if (trimmed.startsWith('>')) {
          const quoteLines = trimmed
            .split('\n')
            .map((l) => l.replace(/^>\s?/, ''))
            .join(' ');
          return (
            <blockquote
              key={idx}
              className="border-l-2 border-moso-accent pl-3 py-1 my-2 text-moso-300 italic bg-moso-850/40 rounded-r-lg"
            >
              <InlineText text={quoteLines} />
            </blockquote>
          );
        }

        // Lists (- or * or 1.)
        const lines = trimmed.split('\n');
        const isUnorderedList = lines.every((l) => l.trim().startsWith('- ') || l.trim().startsWith('* '));
        const isOrderedList = lines.every((l) => /^\d+\.\s/.test(l.trim()));

        if (isUnorderedList) {
          return (
            <ul key={idx} className="list-disc pl-5 space-y-1 my-2 text-moso-200">
              {lines.map((l, lIdx) => (
                <li key={lIdx}>
                  <InlineText text={l.trim().replace(/^[-*]\s+/, '')} />
                </li>
              ))}
            </ul>
          );
        }

        if (isOrderedList) {
          return (
            <ol key={idx} className="list-decimal pl-5 space-y-1 my-2 text-moso-200">
              {lines.map((l, lIdx) => (
                <li key={lIdx}>
                  <InlineText text={l.trim().replace(/^\d+\.\s+/, '')} />
                </li>
              ))}
            </ol>
          );
        }

        // Normal paragraph with line-breaks
        return (
          <p key={idx} className="my-1.5 text-moso-200 leading-relaxed">
            {lines.map((line, lIdx) => (
              <React.Fragment key={lIdx}>
                <InlineText text={line} />
                {lIdx < lines.length - 1 && <br />}
              </React.Fragment>
            ))}
          </p>
        );
      })}
    </>
  );
};

// ---------------------------------------------------------
// Table Component
// ---------------------------------------------------------

const MarkdownTable: React.FC<{ headers: string[]; rows: string[][] }> = ({ headers, rows }) => {
  return (
    <div className="my-3 overflow-x-auto max-w-full rounded-xl border border-moso-750 bg-moso-900/50 shadow-sm scrollbar-thin">
      <table className="w-full text-left border-collapse text-xs">
        <thead>
          <tr className="border-b border-moso-750 bg-moso-850/80 text-moso-200 font-semibold">
            {headers.map((h, hIdx) => (
              <th key={hIdx} className="px-3.5 py-2">
                <InlineText text={h} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-moso-800 text-moso-300">
          {rows.map((row, rIdx) => (
            <tr key={rIdx} className="hover:bg-moso-800/30 transition-colors">
              {row.map((cell, cIdx) => (
                <td key={cIdx} className="px-3.5 py-2">
                  <InlineText text={cell} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// ---------------------------------------------------------
// Inline Text & Math Tokenizer
// ---------------------------------------------------------

export const InlineText: React.FC<{ text: string }> = ({ text }) => {
  // Tokenizer regex matching in priority order:
  // 1. Inline code: `...` (must not evaluate math)
  // 2. Block math: \[ ... \] or $$ ... $$
  // 3. Inline math: \( ... \) or $ ... $ (excluding prices)
  // 4. Bold: **...**
  // 5. Links: [text](url)
  const masterRegex = /(`[^`]+`)|(\\\[[\s\S]*?\\\])|(\$\$[\s\S]*?\$\$)|(\\\([\s\S]*?\\\))|(\$(?!\s)[^$\n]+(?<!\s)\$)|(\*\*[^*]+\*\*)|(\[[^\]]+\]\([^)]+\))/g;

  const elements: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = masterRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      elements.push(text.substring(lastIndex, match.index));
    }

    const token = match[0];

    // 1. Inline Code
    if (token.startsWith('`') && token.endsWith('`')) {
      elements.push(
        <code
          key={key++}
          className="font-mono text-[12px] bg-moso-800 text-moso-accent px-1.5 py-0.5 rounded border border-moso-700/60"
        >
          {token.slice(1, -1)}
        </code>
      );
    }
    // 2. Block Math \[ ... \]
    else if (token.startsWith('\\[') && token.endsWith('\\]')) {
      const math = token.slice(2, -2).trim();
      elements.push(
        <MathView key={key++} math={math} displayMode={true} rawText={token} />
      );
    }
    // 3. Block Math $$ ... $$
    else if (token.startsWith('$$') && token.endsWith('$$')) {
      const math = token.slice(2, -2).trim();
      elements.push(
        <MathView key={key++} math={math} displayMode={true} rawText={token} />
      );
    }
    // 4. Inline Math \( ... \)
    else if (token.startsWith('\\(') && token.endsWith('\\)')) {
      const math = token.slice(2, -2).trim();
      elements.push(
        <MathView key={key++} math={math} displayMode={false} rawText={token} />
      );
    }
    // 5. Inline Math $ ... $
    else if (token.startsWith('$') && token.endsWith('$')) {
      const math = token.slice(1, -1).trim();
      elements.push(
        <MathView key={key++} math={math} displayMode={false} rawText={token} />
      );
    }
    // 6. Bold Text
    else if (token.startsWith('**') && token.endsWith('**')) {
      elements.push(
        <strong key={key++} className="font-semibold text-white">
          {token.slice(2, -2)}
        </strong>
      );
    }
    // 7. Markdown Link
    else if (token.startsWith('[') && token.includes('](')) {
      const linkMatch = token.match(/\[(.*?)\]\((.*?)\)/);
      if (linkMatch) {
        elements.push(
          <a
            key={key++}
            href={linkMatch[2]}
            target="_blank"
            rel="noopener noreferrer"
            className="text-moso-accent underline underline-offset-2 hover:text-emerald-300"
          >
            {linkMatch[1]}
          </a>
        );
      } else {
        elements.push(token);
      }
    } else {
      elements.push(token);
    }

    lastIndex = masterRegex.lastIndex;
  }

  if (lastIndex < text.length) {
    elements.push(text.substring(lastIndex));
  }

  return <>{elements.length > 0 ? elements : text}</>;
};
