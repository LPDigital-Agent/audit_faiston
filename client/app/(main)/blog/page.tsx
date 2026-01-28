"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { PenSquare, Filter } from "lucide-react";
import { cn } from "@/lib/utils";
import { BlogCategory } from "@/lib/blog/types";
import {
  BLOG_POSTS,
  getFeaturedPost,
  getNonFeaturedPosts,
} from "@/mocks/blog-mock-data";
import { BlogHero } from "@/components/blog/blog-hero";
import { BlogCard } from "@/components/blog/blog-card";

/**
 * Blog Page - Internal Company Blog
 *
 * Displays articles from faiston.com/blogs/ reformatted
 * for the Faiston One design system with glassmorphism,
 * bento grid layout, and category filtering.
 */

type FilterCategory = "all" | BlogCategory;

const FILTER_OPTIONS: { value: FilterCategory; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "seguranca", label: "Seguranca" },
  { value: "infraestrutura", label: "Infraestrutura" },
  { value: "cloud", label: "Cloud" },
  { value: "inovacao", label: "Inovacao" },
  { value: "blog-news", label: "Blog & News" },
];

export default function BlogPage() {
  const [activeFilter, setActiveFilter] = useState<FilterCategory>("all");

  const featuredPost = getFeaturedPost();
  const nonFeaturedPosts = getNonFeaturedPosts();

  // Filter posts based on selected category
  const filteredPosts =
    activeFilter === "all"
      ? nonFeaturedPosts
      : nonFeaturedPosts.filter((post) => post.category === activeFilter);

  // Show featured in filtered results if matches filter
  const showFeatured =
    activeFilter === "all" ||
    (featuredPost && featuredPost.category === activeFilter);

  return (
    <div className="min-h-screen">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="mb-8"
      >
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl gradient-nexo flex items-center justify-center">
            <PenSquare className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-text-primary">Blog Faiston</h1>
        </div>
        <p className="text-text-secondary">
          Novidades, tecnologia e insights para sua empresa
        </p>
      </motion.div>

      {/* Featured Article */}
      {showFeatured && featuredPost && (
        <div className="mb-8">
          <BlogHero post={featuredPost} />
        </div>
      )}

      {/* Filter Bar */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.2 }}
        className="mb-6"
      >
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 text-text-muted mr-2">
            <Filter className="w-4 h-4" />
            <span className="text-sm">Filtrar:</span>
          </div>
          {FILTER_OPTIONS.map((option) => (
            <button
              key={option.value}
              onClick={() => setActiveFilter(option.value)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-sm font-medium",
                "transition-all duration-200",
                "border",
                activeFilter === option.value
                  ? "bg-magenta-mid/20 border-magenta-mid/40 text-magenta-light"
                  : "bg-white/5 border-border text-text-muted hover:text-text-primary hover:bg-white/10"
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Articles Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {filteredPosts.map((post, index) => (
          <BlogCard key={post.id} post={post} index={index} />
        ))}
      </div>

      {/* Empty State */}
      {filteredPosts.length === 0 && !showFeatured && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-16"
        >
          <p className="text-text-muted">
            Nenhum artigo encontrado nesta categoria.
          </p>
        </motion.div>
      )}

      {/* Article Count */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="mt-8 text-center"
      >
        <p className="text-sm text-text-muted">
          Exibindo {filteredPosts.length + (showFeatured && featuredPost ? 1 : 0)}{" "}
          de {BLOG_POSTS.length} artigos
        </p>
      </motion.div>
    </div>
  );
}
