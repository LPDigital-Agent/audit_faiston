'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

interface MarkdownContentProps {
  content: string;
  className?: string;
}

/**
 * MarkdownContent - Simple markdown renderer for AI responses
 *
 * Renders basic markdown formatting:
 * - **bold** text
 * - *italic* text
 * - `inline code`
 * - ```code blocks```
 * - - bullet lists
 * - 1. numbered lists
 * - [links](url)
 * - # headings
 */
function MarkdownContent({ content, className }: MarkdownContentProps) {
  const renderMarkdown = React.useMemo(() => {
    if (!content) return null;

    // Split into blocks (code blocks vs regular text)
    const blocks = content.split(/(```[\s\S]*?```)/g);

    return blocks.map((block, blockIndex) => {
      // Handle code blocks
      if (block.startsWith('```')) {
        const lines = block.slice(3, -3).split('\n');
        const language = lines[0]?.trim() || '';
        const code = language ? lines.slice(1).join('\n') : lines.join('\n');

        return (
          <pre
            key={blockIndex}
            className="my-2 overflow-x-auto rounded-md bg-zinc-900 p-3 text-sm"
          >
            <code className="text-zinc-100">{code}</code>
          </pre>
        );
      }

      // Handle regular text with inline formatting
      const lines = block.split('\n');

      return (
        <div key={blockIndex}>
          {lines.map((line, lineIndex) => {
            // Empty line = paragraph break
            if (!line.trim()) {
              return <div key={lineIndex} className="h-2" />;
            }

            // Headings
            if (line.startsWith('### ')) {
              return (
                <h4 key={lineIndex} className="mb-1 mt-3 text-sm font-semibold">
                  {formatInline(line.slice(4))}
                </h4>
              );
            }
            if (line.startsWith('## ')) {
              return (
                <h3 key={lineIndex} className="mb-1 mt-3 text-base font-semibold">
                  {formatInline(line.slice(3))}
                </h3>
              );
            }
            if (line.startsWith('# ')) {
              return (
                <h2 key={lineIndex} className="mb-2 mt-4 text-lg font-bold">
                  {formatInline(line.slice(2))}
                </h2>
              );
            }

            // Bullet lists
            if (line.match(/^[\s]*[-*]\s/)) {
              const indent = line.match(/^[\s]*/)?.[0].length || 0;
              const text = line.replace(/^[\s]*[-*]\s/, '');
              return (
                <div
                  key={lineIndex}
                  className="flex items-start gap-2"
                  style={{ paddingLeft: `${indent * 0.5}rem` }}
                >
                  <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-current opacity-60" />
                  <span>{formatInline(text)}</span>
                </div>
              );
            }

            // Numbered lists
            if (line.match(/^[\s]*\d+\.\s/)) {
              const match = line.match(/^[\s]*(\d+)\.\s(.*)$/);
              if (match) {
                return (
                  <div key={lineIndex} className="flex items-start gap-2">
                    <span className="min-w-[1.5rem] text-right opacity-60">
                      {match[1]}.
                    </span>
                    <span>{formatInline(match[2])}</span>
                  </div>
                );
              }
            }

            // Regular paragraph
            return (
              <p key={lineIndex} className="leading-relaxed">
                {formatInline(line)}
              </p>
            );
          })}
        </div>
      );
    });
  }, [content]);

  return (
    <div className={cn('prose prose-sm prose-invert max-w-none', className)}>
      {renderMarkdown}
    </div>
  );
}

/**
 * Format inline markdown elements: bold, italic, code, links
 */
function formatInline(text: string): React.ReactNode {
  if (!text) return null;

  // Split by inline code, bold, italic, and links
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    // Inline code: `code`
    const codeMatch = remaining.match(/^(.*?)`([^`]+)`/);
    if (codeMatch) {
      if (codeMatch[1]) {
        parts.push(...formatBoldItalic(codeMatch[1], key++));
      }
      parts.push(
        <code
          key={key++}
          className="rounded bg-zinc-800 px-1 py-0.5 text-xs text-zinc-200"
        >
          {codeMatch[2]}
        </code>
      );
      remaining = remaining.slice(codeMatch[0].length);
      continue;
    }

    // Link: [text](url)
    const linkMatch = remaining.match(/^(.*?)\[([^\]]+)\]\(([^)]+)\)/);
    if (linkMatch) {
      if (linkMatch[1]) {
        parts.push(...formatBoldItalic(linkMatch[1], key++));
      }
      parts.push(
        <a
          key={key++}
          href={linkMatch[3]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-400 underline hover:text-blue-300"
        >
          {linkMatch[2]}
        </a>
      );
      remaining = remaining.slice(linkMatch[0].length);
      continue;
    }

    // No more special formatting, process rest with bold/italic
    parts.push(...formatBoldItalic(remaining, key++));
    break;
  }

  return parts.length === 1 ? parts[0] : <>{parts}</>;
}

/**
 * Handle bold and italic formatting
 */
function formatBoldItalic(text: string, baseKey: number): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let key = baseKey;

  while (remaining.length > 0) {
    // Bold: **text**
    const boldMatch = remaining.match(/^(.*?)\*\*([^*]+)\*\*/);
    if (boldMatch) {
      if (boldMatch[1]) parts.push(boldMatch[1]);
      parts.push(
        <strong key={key++} className="font-semibold">
          {boldMatch[2]}
        </strong>
      );
      remaining = remaining.slice(boldMatch[0].length);
      continue;
    }

    // Italic: *text*
    const italicMatch = remaining.match(/^(.*?)\*([^*]+)\*/);
    if (italicMatch) {
      if (italicMatch[1]) parts.push(italicMatch[1]);
      parts.push(
        <em key={key++} className="italic">
          {italicMatch[2]}
        </em>
      );
      remaining = remaining.slice(italicMatch[0].length);
      continue;
    }

    // No more formatting
    parts.push(remaining);
    break;
  }

  return parts;
}

export { MarkdownContent };
