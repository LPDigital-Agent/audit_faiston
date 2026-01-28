"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Clock, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { BlogPost, formatBlogDate } from "@/lib/blog/types";
import { BlogCategoryBadge } from "./blog-category-badge";

/**
 * BlogCard - Article card for blog listing
 *
 * Features:
 * - Glassmorphism background
 * - Ghost border with magenta glow on hover
 * - Category badge with semantic colors
 * - Staggered animation for grid display
 */

interface BlogCardProps {
  /** Blog post data */
  post: BlogPost;
  /** Animation index for staggered entrance */
  index?: number;
  /** Custom class names */
  className?: string;
}

export function BlogCard({ post, index = 0, className }: BlogCardProps) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.1 }}
      className={cn("group", className)}
    >
      <Link href={`/blog/${post.slug}`}>
        <div
          className={cn(
            "h-full p-5 rounded-xl",
            "bg-white/5 backdrop-blur-sm",
            "border border-border",
            "transition-all duration-300",
            "hover:bg-white/10",
            "hover:border-magenta-mid/40",
            "hover:shadow-[0_0_20px_rgba(253,86,101,0.1)]"
          )}
        >
          {/* Category & Date */}
          <div className="flex items-center justify-between mb-3">
            <BlogCategoryBadge category={post.category} />
            <span className="text-xs text-text-muted">
              {formatBlogDate(post.publishedAt)}
            </span>
          </div>

          {/* Title */}
          <h3
            className={cn(
              "text-lg font-semibold text-text-primary mb-2",
              "line-clamp-2",
              "group-hover:text-magenta-light transition-colors"
            )}
          >
            {post.title}
          </h3>

          {/* Excerpt */}
          <p className="text-sm text-text-secondary line-clamp-3 mb-4">
            {post.excerpt}
          </p>

          {/* Footer */}
          <div className="flex items-center justify-between pt-3 border-t border-border/50">
            <div className="flex items-center gap-1.5 text-text-muted">
              <Clock className="w-3.5 h-3.5" />
              <span className="text-xs">{post.readTime} min</span>
            </div>
            <span
              className={cn(
                "flex items-center gap-1 text-xs font-medium",
                "text-text-muted group-hover:text-magenta-light",
                "transition-colors"
              )}
            >
              Ler mais
              <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1" />
            </span>
          </div>
        </div>
      </Link>
    </motion.article>
  );
}

export default BlogCard;
