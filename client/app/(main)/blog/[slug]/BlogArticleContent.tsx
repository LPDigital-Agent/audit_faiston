"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowLeft, Clock, Calendar, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { BlogPost, formatBlogDate } from "@/lib/blog/types";
import { BlogCategoryBadge } from "@/components/blog/blog-category-badge";

/**
 * BlogArticleContent - Client component for article display
 *
 * Handles:
 * - Framer Motion animations
 * - Markdown content rendering
 * - Interactive elements
 */

interface BlogArticleContentProps {
  post: BlogPost;
}

export function BlogArticleContent({ post }: BlogArticleContentProps) {
  // Convert markdown content to HTML-like rendering
  const renderContent = (content: string) => {
    // Simple markdown-to-JSX conversion for display
    const lines = content.trim().split("\n");
    const elements: React.ReactNode[] = [];
    let currentList: React.ReactNode[] = [];
    let currentTable: string[][] = [];
    let inTable = false;
    let tableHeaders: string[] = [];

    const flushList = () => {
      if (currentList.length > 0) {
        elements.push(
          <ul key={`list-${elements.length}`} className="list-disc list-inside space-y-1 my-4 text-text-secondary">
            {currentList.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        );
        currentList = [];
      }
    };

    const flushTable = () => {
      if (currentTable.length > 0 && tableHeaders.length > 0) {
        elements.push(
          <div key={`table-${elements.length}`} className="overflow-x-auto my-6">
            <table className="min-w-full border border-border rounded-lg overflow-hidden">
              <thead className="bg-white/5">
                <tr>
                  {tableHeaders.map((header, i) => (
                    <th key={i} className="px-4 py-2 text-left text-sm font-medium text-text-primary border-b border-border">
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {currentTable.map((row, rowIndex) => (
                  <tr key={rowIndex} className="border-b border-border/50 last:border-0">
                    {row.map((cell, cellIndex) => (
                      <td key={cellIndex} className="px-4 py-2 text-sm text-text-secondary">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        currentTable = [];
        tableHeaders = [];
        inTable = false;
      }
    };

    lines.forEach((line, index) => {
      const trimmedLine = line.trim();

      // Skip empty lines
      if (!trimmedLine) {
        flushList();
        return;
      }

      // Headers
      if (trimmedLine.startsWith("# ")) {
        flushList();
        flushTable();
        elements.push(
          <h1 key={`h1-${index}`} className="text-2xl font-bold text-text-primary mt-8 mb-4">
            {trimmedLine.slice(2)}
          </h1>
        );
        return;
      }

      if (trimmedLine.startsWith("## ")) {
        flushList();
        flushTable();
        elements.push(
          <h2 key={`h2-${index}`} className="text-xl font-semibold text-text-primary mt-6 mb-3">
            {trimmedLine.slice(3)}
          </h2>
        );
        return;
      }

      if (trimmedLine.startsWith("### ")) {
        flushList();
        flushTable();
        elements.push(
          <h3 key={`h3-${index}`} className="text-lg font-medium text-text-primary mt-4 mb-2">
            {trimmedLine.slice(4)}
          </h3>
        );
        return;
      }

      // Table rows
      if (trimmedLine.startsWith("|") && trimmedLine.endsWith("|")) {
        flushList();
        const cells = trimmedLine
          .slice(1, -1)
          .split("|")
          .map((cell) => cell.trim());

        // Check if it's a separator row (|---|---|)
        if (cells.every((cell) => /^-+$/.test(cell))) {
          inTable = true;
          return;
        }

        if (!inTable) {
          // This is the header row
          tableHeaders = cells;
        } else {
          // This is a data row
          currentTable.push(cells);
        }
        return;
      } else if (inTable) {
        flushTable();
      }

      // List items
      if (trimmedLine.startsWith("- ") || trimmedLine.startsWith("* ")) {
        flushTable();
        currentList.push(formatInlineText(trimmedLine.slice(2)));
        return;
      }

      // Numbered list items
      if (/^\d+\.\s/.test(trimmedLine)) {
        flushTable();
        flushList();
        const match = trimmedLine.match(/^\d+\.\s(.+)$/);
        if (match) {
          elements.push(
            <p key={`numbered-${index}`} className="text-text-secondary my-2 pl-4">
              <span className="font-medium text-text-primary">{trimmedLine.split(".")[0]}.</span> {formatInlineText(match[1])}
            </p>
          );
        }
        return;
      }

      // Regular paragraph
      flushList();
      flushTable();
      elements.push(
        <p key={`p-${index}`} className="text-text-secondary my-4 leading-relaxed">
          {formatInlineText(trimmedLine)}
        </p>
      );
    });

    flushList();
    flushTable();

    return elements;
  };

  // Format inline text (bold, etc.)
  const formatInlineText = (text: string): React.ReactNode => {
    // Handle **bold** text
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return (
          <strong key={i} className="font-semibold text-text-primary">
            {part.slice(2, -2)}
          </strong>
        );
      }
      return part;
    });
  };

  return (
    <div className="min-h-screen">
      {/* Back Navigation */}
      <motion.div
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.3 }}
        className="mb-6"
      >
        <Link
          href="/blog"
          className={cn(
            "inline-flex items-center gap-2",
            "text-sm text-text-muted hover:text-text-primary",
            "transition-colors"
          )}
        >
          <ArrowLeft className="w-4 h-4" />
          Voltar para Blog
        </Link>
      </motion.div>

      {/* Article Container */}
      <motion.article
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="max-w-3xl"
      >
        {/* Meta Header */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <BlogCategoryBadge category={post.category} size="md" />
          <span className="w-1 h-1 rounded-full bg-text-muted" />
          <div className="flex items-center gap-1.5 text-text-muted">
            <Calendar className="w-4 h-4" />
            <span className="text-sm">{formatBlogDate(post.publishedAt)}</span>
          </div>
          <span className="w-1 h-1 rounded-full bg-text-muted" />
          <div className="flex items-center gap-1.5 text-text-muted">
            <Clock className="w-4 h-4" />
            <span className="text-sm">{post.readTime} min de leitura</span>
          </div>
        </div>

        {/* Title */}
        <h1 className="text-3xl md:text-4xl font-bold text-text-primary mb-6">
          {post.title}
        </h1>

        {/* Divider */}
        <div className="h-px bg-gradient-to-r from-border via-magenta-mid/30 to-border mb-8" />

        {/* Article Content */}
        <div className="prose-custom">{renderContent(post.content)}</div>

        {/* Footer Actions */}
        <div className="mt-12 pt-6 border-t border-border">
          <div className="flex flex-wrap items-center justify-between gap-4">
            {/* Tags */}
            {post.tags && post.tags.length > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                {post.tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-2.5 py-1 text-xs rounded-full bg-white/5 border border-border text-text-muted"
                  >
                    #{tag}
                  </span>
                ))}
              </div>
            )}

            {/* External Link */}
            {post.externalUrl && (
              <a
                href={post.externalUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(
                  "inline-flex items-center gap-2",
                  "px-4 py-2 rounded-lg",
                  "bg-white/5 border border-border",
                  "text-sm text-text-secondary hover:text-text-primary",
                  "hover:bg-white/10 hover:border-magenta-mid/30",
                  "transition-all duration-200"
                )}
              >
                <ExternalLink className="w-4 h-4" />
                Ver artigo original
              </a>
            )}
          </div>
        </div>
      </motion.article>
    </div>
  );
}
