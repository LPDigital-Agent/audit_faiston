"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Clock, ArrowRight, Star } from "lucide-react";
import { cn } from "@/lib/utils";
import { BlogPost, formatBlogDate } from "@/lib/blog/types";
import { BlogCategoryBadge } from "./blog-category-badge";

/**
 * BlogHero - Featured article hero section
 *
 * Displays the featured/highlighted article in a larger format
 * with gradient background and prominent styling.
 */

interface BlogHeroProps {
  /** Featured blog post */
  post: BlogPost;
  /** Custom class names */
  className?: string;
}

export function BlogHero({ post, className }: BlogHeroProps) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className={cn("group", className)}
    >
      <Link href={`/blog/${post.slug}`}>
        <div
          className={cn(
            "relative overflow-hidden rounded-2xl",
            "bg-gradient-to-br from-white/10 to-white/5",
            "backdrop-blur-sm",
            "border border-border",
            "transition-all duration-300",
            "hover:border-magenta-mid/40",
            "hover:shadow-[0_0_30px_rgba(253,86,101,0.15)]"
          )}
        >
          {/* Gradient overlay */}
          <div className="absolute inset-0 bg-gradient-to-br from-magenta-dark/10 via-transparent to-blue-dark/10 opacity-50" />

          <div className="relative p-6 md:p-8">
            {/* Featured Badge & Category */}
            <div className="flex flex-wrap items-center gap-3 mb-4">
              <span
                className={cn(
                  "inline-flex items-center gap-1.5",
                  "px-3 py-1 rounded-full",
                  "bg-magenta-mid/20 border border-magenta-mid/30",
                  "text-sm font-medium text-magenta-light"
                )}
              >
                <Star className="w-3.5 h-3.5 fill-current" />
                Destaque
              </span>
              <BlogCategoryBadge category={post.category} size="md" />
            </div>

            {/* Title */}
            <h2
              className={cn(
                "text-2xl md:text-3xl font-bold text-text-primary mb-4",
                "group-hover:text-magenta-light transition-colors"
              )}
            >
              {post.title}
            </h2>

            {/* Excerpt */}
            <p className="text-base text-text-secondary mb-6 max-w-2xl">
              {post.excerpt}
            </p>

            {/* Meta & CTA */}
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-4 text-text-muted">
                <span className="text-sm">
                  {formatBlogDate(post.publishedAt)}
                </span>
                <span className="w-1 h-1 rounded-full bg-text-muted" />
                <div className="flex items-center gap-1.5">
                  <Clock className="w-4 h-4" />
                  <span className="text-sm">{post.readTime} min de leitura</span>
                </div>
              </div>

              <span
                className={cn(
                  "inline-flex items-center gap-2",
                  "px-4 py-2 rounded-lg",
                  "bg-white/5 border border-border",
                  "text-sm font-medium text-text-primary",
                  "group-hover:bg-magenta-mid/20 group-hover:border-magenta-mid/40",
                  "group-hover:text-magenta-light",
                  "transition-all duration-300"
                )}
              >
                Ler artigo completo
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
              </span>
            </div>
          </div>
        </div>
      </Link>
    </motion.article>
  );
}

export default BlogHero;
