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
    <div className={cn('prose-moso text-moso-100 space-y-3.5', isStreaming && 'typing-cursor')}>
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
        className="text-rose-400 font-mono text-xs bg-rose-500/10 border border-rose-500/20 px-2 py-0.5 rounded inline-block"
        title="KaTeX parsing error"
      >
        {rawText || (displayMode ? `\\[${math}\\]` : `\\(${math}\\)`)}
      </span>
    );
  }

  if (displayMode) {
    return (
      <div
        className="my-3.5 overflow-x-auto overflow-y-hidden py-2 px-1 text-center max-w-full scrollbar-thin text-moso-100 font-normal"
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
// Code Syntax Highlighter Tokenizer
// ---------------------------------------------------------

interface CodeToken {
  type: 'keyword' | 'string' | 'comment' | 'number' | 'boolean' | 'function' | 'type' | 'plain';
  text: string;
}

function highlightSyntax(code: string, language: string): React.ReactNode {
  const lang = (language || '').toLowerCase().trim();

  // If no language or simple plain text/markdown, return untouched code
  if (!lang || ['text', 'plain', 'markdown', 'md', 'txt'].includes(lang)) {
    return code;
  }

  const lines = code.split('\n');

  return lines.map((line, lineIdx) => {
    const tokens = tokenizeLine(line, lang);

    return (
      <React.Fragment key={lineIdx}>
        {tokens.map((token, tokenIdx) => {
          let className = '';
          switch (token.type) {
            case 'keyword':
              className = 'text-[#b4a7f5] font-semibold';
              break;
            case 'string':
              className = 'text-[#a5cf9b]';
              break;
            case 'comment':
              className = 'text-[#8a8678] italic';
              break;
            case 'number':
              className = 'text-[#e6b56b]';
              break;
            case 'boolean':
              className = 'text-[#f0907f]';
              break;
            case 'function':
              className = 'text-[#7fc4e8]';
              break;
            case 'type':
              className = 'text-[#e8d48a]';
              break;
            default:
              className = 'text-[#e8e4da]';
          }

          return (
            <span key={tokenIdx} className={className}>
              {token.text}
            </span>
          );
        })}
        {lineIdx < lines.length - 1 && '\n'}
      </React.Fragment>
    );
  });
}

function tokenizeLine(line: string, lang: string): CodeToken[] {
  const tokens: CodeToken[] = [];

  // Determine comment prefix
  const isHashComment = ['python', 'py', 'bash', 'sh', 'zsh', 'yaml', 'yml', 'dockerfile'].includes(lang);
  const isDashDashComment = ['sql', 'lua'].includes(lang);

  // Common keyword sets
  const keywords = new Set([
    // Python
    'def', 'class', 'import', 'from', 'as', 'return', 'if', 'elif', 'else', 'while', 'for', 'in',
    'try', 'except', 'finally', 'raise', 'with', 'lambda', 'pass', 'break', 'continue', 'yield',
    'async', 'await', 'assert', 'self', 'cls',
    // JS / TS
    'const', 'let', 'var', 'function', 'switch', 'case', 'default', 'new', 'extends', 'export',
    'throw', 'typeof', 'instanceof', 'void', 'delete', 'interface', 'type', 'enum', 'implements',
    'public', 'private', 'protected', 'readonly', 'static', 'this', 'super',
    // SQL
    'select', 'from', 'where', 'insert', 'into', 'values', 'update', 'set', 'table', 'drop',
    'alter', 'add', 'join', 'left', 'right', 'inner', 'outer', 'on', 'group', 'by', 'order',
    'asc', 'desc', 'limit', 'offset', 'having', 'union', 'and', 'or', 'not', 'primary', 'key',
    // Rust / Go / C / C++
    'fn', 'pub', 'struct', 'impl', 'trait', 'mut', 'match', 'func', 'package', 'range', 'defer',
    'go', 'int', 'float', 'string', 'bool', 'char', 'void',
    // Bash
    'echo', 'then', 'fi', 'do', 'done', 'esac', 'local', 'source', 'exit'
  ]);

  const booleans = new Set(['true', 'false', 'null', 'undefined', 'none', 'nil', 'true', 'false']);

  let i = 0;
  const len = line.length;

  while (i < len) {
    // 1. Comments
    if ((isHashComment && line[i] === '#') || (!isHashComment && !isDashDashComment && line.startsWith('//', i)) || (isDashDashComment && line.startsWith('--', i))) {
      tokens.push({ type: 'comment', text: line.slice(i) });
      break;
    }

    // 2. Strings ("...", '...', `...`)
    if (line[i] === '"' || line[i] === "'" || line[i] === '`') {
      const quote = line[i];
      let j = i + 1;
      while (j < len && line[j] !== quote) {
        if (line[j] === '\\' && j + 1 < len) j++;
        j++;
      }
      if (j < len) j++; // Include closing quote
      tokens.push({ type: 'string', text: line.slice(i, j) });
      i = j;
      continue;
    }

    // 3. Numbers
    if (/\d/.test(line[i]) && (i === 0 || /[^a-zA-Z0-9_$]/.test(line[i - 1]))) {
      let j = i;
      while (j < len && /[0-9.xXabcdefABCDEF]/.test(line[j])) j++;
      tokens.push({ type: 'number', text: line.slice(i, j) });
      i = j;
      continue;
    }

    // 4. Words (identifiers, keywords, booleans, functions)
    if (/[a-zA-Z_$]/.test(line[i])) {
      let j = i;
      while (j < len && /[a-zA-Z0-9_$]/.test(line[j])) j++;
      const word = line.slice(i, j);
      const lower = word.toLowerCase();

      // Check if followed by '(' -> function
      let isFunc = false;
      let k = j;
      while (k < len && /\s/.test(line[k])) k++;
      if (k < len && line[k] === '(') {
        isFunc = true;
      }

      if (booleans.has(lower)) {
        tokens.push({ type: 'boolean', text: word });
      } else if (keywords.has(lower)) {
        tokens.push({ type: 'keyword', text: word });
      } else if (isFunc) {
        tokens.push({ type: 'function', text: word });
      } else if (/^[A-Z][a-zA-Z0-9_]*$/.test(word)) {
        tokens.push({ type: 'type', text: word });
      } else {
        tokens.push({ type: 'plain', text: word });
      }
      i = j;
      continue;
    }

    // 5. Symbols, whitespace, operators
    tokens.push({ type: 'plain', text: line[i] });
    i++;
  }

  return tokens;
}

// ---------------------------------------------------------
// Code Block Component with Copy Button & Syntax Highlighting
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

  const highlighted = useMemo(() => highlightSyntax(code, language), [code, language]);

  return (
    <div className="my-4 rounded-xl overflow-hidden border border-[#3a3833] bg-[#1f1e1b] font-mono text-[13px]">
      {/* Code Header Bar */}
      <div className="flex items-center justify-between pl-4 pr-2 py-1.5 bg-[#2a2926] text-[#a9a597] select-none">
        <span className="font-sans text-[12px] text-[#a9a597]">
          {language || 'code'}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md font-sans text-[12px] hover:text-[#ece9e0] hover:bg-[#3a3833] transition-colors cursor-pointer"
          title="Copy code to clipboard"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-[#98be93]" />
              <span className="text-[#98be93]">Copied</span>
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>

      {/* Code Content (Preserves exact whitespace, tabs, and indentation) */}
      <div className="p-4 overflow-x-auto text-[#e8e4da] leading-relaxed font-normal selection:bg-[#7fa97a]/30">
        <pre className="m-0 p-0 whitespace-pre">
          <code>{highlighted}</code>
        </pre>
      </div>
    </div>
  );
};

// ---------------------------------------------------------
// Hierarchical List Data Structure & Renderer
// ---------------------------------------------------------

interface ListItemNode {
  type: 'unordered' | 'ordered';
  order?: string;
  text: string;
  children: ListItemNode[];
}

function buildListTree(rawItems: { depth: number; type: 'unordered' | 'ordered'; text: string; order?: string }[]): ListItemNode[] {
  const root: ListItemNode[] = [];
  const stack: { node: ListItemNode; depth: number }[] = [];

  for (const item of rawItems) {
    const node: ListItemNode = {
      type: item.type,
      order: item.order,
      text: item.text,
      children: [],
    };

    while (stack.length > 0 && stack[stack.length - 1].depth >= item.depth) {
      stack.pop();
    }

    if (stack.length === 0) {
      root.push(node);
    } else {
      stack[stack.length - 1].node.children.push(node);
    }

    stack.push({ node, depth: item.depth });
  }

  return root;
}

const RenderListTree: React.FC<{ items: ListItemNode[]; depth?: number }> = ({ items, depth = 0 }) => {
  if (items.length === 0) return null;
  const isOrdered = items[0].type === 'ordered';
  const ListTag = isOrdered ? 'ol' : 'ul';

  return (
    <ListTag
      className={cn(
        isOrdered ? 'list-decimal' : depth === 1 ? 'list-circle' : depth >= 2 ? 'list-square' : 'list-disc',
        depth > 0
          ? 'pl-5 my-1.5 space-y-1'
          : 'pl-6 my-3.5 space-y-2 text-moso-150'
      )}
    >
      {items.map((node, i) => (
        <li key={i} className="leading-relaxed">
          <InlineText text={node.text} />
          {node.children.length > 0 && (
            <RenderListTree items={node.children} depth={depth + 1} />
          )}
        </li>
      ))}
    </ListTag>
  );
};

// ---------------------------------------------------------
// Block-Level Prose Parser & Formatter
// ---------------------------------------------------------

type ProseBlock =
  | { type: 'heading'; level: number; text: string }
  | { type: 'blockquote'; lines: string[] }
  | { type: 'hr' }
  | { type: 'list'; items: { depth: number; type: 'unordered' | 'ordered'; text: string; order?: string }[] }
  | { type: 'paragraph'; lines: string[] };

function parseProseBlocks(text: string): ProseBlock[] {
  const blocks: ProseBlock[] = [];
  const rawParagraphs = text.split('\n\n').filter((p) => p.trim().length > 0);

  for (const p of rawParagraphs) {
    const lines = p.split('\n');
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];
      const trimmed = line.trim();

      // 1. Heading
      const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
      if (headingMatch) {
        blocks.push({
          type: 'heading',
          level: headingMatch[1].length,
          text: headingMatch[2],
        });
        i++;
        continue;
      }

      // 2. Horizontal Rule (---, ***, ___)
      if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
        blocks.push({ type: 'hr' });
        i++;
        continue;
      }

      // 3. Blockquote
      if (trimmed.startsWith('>')) {
        const quoteLines: string[] = [];
        while (i < lines.length && lines[i].trim().startsWith('>')) {
          quoteLines.push(lines[i].trim().replace(/^>\s?/, ''));
          i++;
        }
        blocks.push({ type: 'blockquote', lines: quoteLines });
        continue;
      }

      // 4. List items (contiguous sequence of lines matching bullet or numbered list)
      const listMatch = line.match(/^(\s*)([-*+]|\d+\.)\s+(.*)$/);
      if (listMatch) {
        const listItems: { depth: number; type: 'unordered' | 'ordered'; text: string; order?: string }[] = [];

        while (i < lines.length) {
          const currLine = lines[i];
          const currMatch = currLine.match(/^(\s*)([-*+]|\d+\.)\s+(.*)$/);

          if (currMatch) {
            const indentSpaces = currMatch[1].length;
            const bullet = currMatch[2];
            const isOrdered = /^\d+\./.test(bullet);
            const depth = Math.floor(indentSpaces / 2);

            listItems.push({
              depth,
              type: isOrdered ? 'ordered' : 'unordered',
              order: bullet,
              text: currMatch[3],
            });
            i++;
          } else if (listItems.length > 0 && currLine.startsWith('   ')) {
            // Continuation of previous list item
            listItems[listItems.length - 1].text += ' ' + currLine.trim();
            i++;
          } else {
            break;
          }
        }

        blocks.push({ type: 'list', items: listItems });
        continue;
      }

      // 5. Standard paragraph lines
      const paraLines: string[] = [];
      while (
        i < lines.length &&
        !lines[i].trim().match(/^#{1,6}\s+/) &&
        !lines[i].trim().startsWith('>') &&
        !lines[i].match(/^(\s*)([-*+]|\d+\.)\s+/) &&
        !/^(-{3,}|\*{3,}|_{3,})$/.test(lines[i].trim())
      ) {
        paraLines.push(lines[i]);
        i++;
      }

      if (paraLines.length > 0) {
        blocks.push({ type: 'paragraph', lines: paraLines });
      }
    }
  }

  return blocks;
}

const ProseSegment: React.FC<{ text: string }> = ({ text }) => {
  const blocks = useMemo(() => parseProseBlocks(text), [text]);

  return (
    <>
      {blocks.map((block, idx) => {
        if (block.type === 'heading') {
          if (block.level === 1) {
            return (
              <h1 key={idx} className="text-2xl font-semibold text-white mt-7 mb-3">
                <InlineText text={block.text} />
              </h1>
            );
          }
          if (block.level === 2) {
            return (
              <h2 key={idx} className="text-xl font-semibold text-white mt-6 mb-2.5">
                <InlineText text={block.text} />
              </h2>
            );
          }
          if (block.level === 3) {
            return (
              <h3 key={idx} className="text-lg font-semibold text-white mt-5 mb-2">
                <InlineText text={block.text} />
              </h3>
            );
          }
          return (
            <h4 key={idx} className="text-base font-semibold text-moso-100 mt-4 mb-1.5">
              <InlineText text={block.text} />
            </h4>
          );
        }

        if (block.type === 'hr') {
          return <hr key={idx} className="border-t border-moso-750 my-6" />;
        }

        if (block.type === 'blockquote') {
          return (
            <blockquote
              key={idx}
              className="border-l-2 border-moso-600 pl-4 my-3.5 text-moso-300"
            >
              <InlineText text={block.lines.join(' ')} />
            </blockquote>
          );
        }

        if (block.type === 'list') {
          const tree = buildListTree(block.items);
          return <RenderListTree key={idx} items={tree} />;
        }

        // Paragraph
        return (
          <p key={idx} className="my-3">
            {block.lines.map((line, lIdx) => (
              <React.Fragment key={lIdx}>
                <InlineText text={line} />
                {lIdx < block.lines.length - 1 && <br />}
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
    <div className="my-4 overflow-x-auto max-w-full scrollbar-thin">
      <table className="w-full text-left border-collapse font-sans text-[14px]">
        <thead>
          <tr className="border-b border-moso-600 text-white font-semibold">
            {headers.map((h, hIdx) => (
              <th key={hIdx} className="px-3 py-2.5">
                <InlineText text={h} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-moso-750 text-moso-200">
          {rows.map((row, rIdx) => (
            <tr key={rIdx}>
              {row.map((cell, cIdx) => (
                <td key={cIdx} className="px-3 py-2.5">
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
  // 4. Bold + Italic: ***...***
  // 5. Bold: **...** or __...__
  // 6. Italic: *...* or _..._
  // 7. Strikethrough: ~~...~~
  // 8. Links: [text](url)
  const masterRegex = /(`[^`]+`)|(\\\[[\s\S]*?\\\])|(\$\$[\s\S]*?\$\$)|(\\\([\s\S]*?\\\))|(\$(?!\s)[^$\n]+?(?<!\s)\$)|(\*\*\*[^*]+\*\*\*)|(\*\*[^*]+\*\*|__[^_]+__)|(\*[^*]+\*|(?<!\w)_[^_]+_(?!\w))|(~~[^~]+~~)|(\[[^\]]+\]\([^)]+\))/g;

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
          className="font-mono text-[0.85em] bg-moso-800 text-moso-100 px-1.5 py-0.5 rounded-md"
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
    // 6. Bold + Italic ***...***
    else if (token.startsWith('***') && token.endsWith('***')) {
      elements.push(
        <strong key={key++} className="font-semibold text-white italic">
          {token.slice(3, -3)}
        </strong>
      );
    }
    // 7. Bold Text **...** or __...__
    else if ((token.startsWith('**') && token.endsWith('**')) || (token.startsWith('__') && token.endsWith('__'))) {
      elements.push(
        <strong key={key++} className="font-semibold text-white">
          {token.slice(2, -2)}
        </strong>
      );
    }
    // 8. Italic *...* or _..._
    else if ((token.startsWith('*') && token.endsWith('*')) || (token.startsWith('_') && token.endsWith('_'))) {
      elements.push(
        <em key={key++} className="italic text-moso-150">
          {token.slice(1, -1)}
        </em>
      );
    }
    // 9. Strikethrough ~~...~~
    else if (token.startsWith('~~') && token.endsWith('~~')) {
      elements.push(
        <del key={key++} className="line-through text-moso-400">
          {token.slice(2, -2)}
        </del>
      );
    }
    // 10. Markdown Link [text](url)
    else if (token.startsWith('[') && token.includes('](')) {
      const linkMatch = token.match(/\[(.*?)\]\((.*?)\)/);
      if (linkMatch) {
        elements.push(
          <a
            key={key++}
            href={linkMatch[2]}
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent-400 font-medium underline underline-offset-2 hover:text-accent-300 transition-colors"
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
