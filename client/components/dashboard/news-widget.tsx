"use client";

import { useState, useEffect } from "react";
import { GlassCard, GlassCardHeader, GlassCardTitle } from "@/components/shared/glass-card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Newspaper, Clock, ExternalLink, RefreshCw, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { newsArticles as mockNewsArticles } from "@/mocks/mock-data";
import { formatRelativeTime, cn } from "@/lib/utils";
import { getTechNews, type NewsArticle } from "@/services/portalAgentcore";

/**
 * NewsWidget - Tech news feed widget
 *
 * Displays aggregated tech news from multiple sources.
 * Categories: AWS, Azure, GCP, AI/ML
 *
 * Data source:
 * - Primary: Portal AgentCore (real RSS feeds)
 * - Fallback: Mock data (when AgentCore unavailable)
 */

const categoryColors: Record<string, string> = {
  "cloud-aws": "bg-orange-500/20 text-orange-400",
  "cloud-azure": "bg-blue-500/20 text-blue-400",
  "cloud-gcp": "bg-red-500/20 text-red-400",
  ai: "bg-purple-500/20 text-purple-400",
  brazil: "bg-green-500/20 text-green-400",
};

const sourceIcons: Record<string, string> = {
  aws: "🟠",
  google: "🔵",
  azure: "🔷",
  techcrunch: "🟢",
  hackernews: "🟧",
  techtudo: "🇧🇷",
  canaltech: "🇧🇷",
};

// Feature flag to use real AgentCore (set to true after deployment)
const USE_AGENTCORE = process.env.NEXT_PUBLIC_USE_PORTAL_AGENTCORE === "true";

export function NewsWidget() {
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchNews = async (showRefreshing = false) => {
    if (showRefreshing) setIsRefreshing(true);
    setError(null);

    try {
      if (USE_AGENTCORE) {
        // Fetch from Portal AgentCore
        const response = await getTechNews({
          categories: ["cloud-aws", "cloud-gcp", "cloud-azure", "ai"],
          max_articles: 10,
        });

        if (response.data.success && response.data.articles.length > 0) {
          setArticles(response.data.articles);
        } else {
          // Fallback to mock if no articles
          setArticles(mockNewsArticles as unknown as NewsArticle[]);
        }
      } else {
        // Use mock data when AgentCore is not enabled
        // Simulate network delay for realistic UX
        await new Promise((resolve) => setTimeout(resolve, 500));
        setArticles(mockNewsArticles as unknown as NewsArticle[]);
      }
    } catch (err) {
      console.error("[NewsWidget] Error fetching news:", err);
      setError("Erro ao carregar notícias");
      // Fallback to mock data on error
      setArticles(mockNewsArticles as unknown as NewsArticle[]);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchNews();

    // Auto-refresh every 15 minutes if AgentCore is enabled
    if (USE_AGENTCORE) {
      const interval = setInterval(() => fetchNews(), 15 * 60 * 1000);
      return () => clearInterval(interval);
    }
  }, []);

  const handleRefresh = () => {
    fetchNews(true);
  };

  return (
    <GlassCard className="h-full flex flex-col">
      <GlassCardHeader>
        <div className="flex items-center gap-2">
          <Newspaper className="w-4 h-4 text-magenta-light" />
          <GlassCardTitle>Notícias Tech</GlassCardTitle>
        </div>
        <div className="flex items-center gap-2">
          {USE_AGENTCORE && (
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={handleRefresh}
              disabled={isRefreshing}
              aria-label="Atualizar notícias"
            >
              <RefreshCw
                className={cn(
                  "w-3 h-3",
                  isRefreshing && "animate-spin"
                )}
              />
            </Button>
          )}
          <Badge variant="outline" className="text-xs">
            {isLoading ? "..." : `${articles.length} novidades`}
          </Badge>
        </div>
      </GlassCardHeader>

      {error && (
        <div className="px-4 py-2 flex items-center gap-2 text-xs text-amber-400 bg-amber-500/10 border-b border-amber-500/20">
          <AlertCircle className="w-3 h-3" />
          <span>{error} - usando dados de exemplo</span>
        </div>
      )}

      <ScrollArea className="flex-1 -mx-4 px-4">
        <div className="space-y-3">
          {isLoading ? (
            // Loading skeletons
            Array.from({ length: 4 }).map((_, i) => (
              <NewsCardSkeleton key={i} />
            ))
          ) : (
            articles.map((article) => (
              <NewsCard key={article.id} article={article} />
            ))
          )}
        </div>
      </ScrollArea>
    </GlassCard>
  );
}

interface NewsCardProps {
  article: NewsArticle;
}

function NewsCard({ article }: NewsCardProps) {
  const timeAgo = formatRelativeTime(article.publishedAt);
  const categoryColor =
    categoryColors[article.category] || "bg-gray-500/20 text-gray-400";
  const sourceIcon = sourceIcons[article.sourceIcon] || "📰";

  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        "block p-3 rounded-lg",
        "border border-border",
        "transition-all duration-150",
        "hover:bg-white/5 hover:border-magenta-mid/30",
        "group"
      )}
    >
      {/* Source & Category */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-sm">{sourceIcon}</span>
        <span className="text-xs text-text-muted">{article.source}</span>
        <Badge className={cn("ml-auto text-[10px]", categoryColor)}>
          {article.category === "ai"
            ? "AI"
            : article.category === "brazil"
            ? "BR"
            : article.category.split("-")[1]?.toUpperCase()}
        </Badge>
      </div>

      {/* Title */}
      <h4 className="text-sm font-medium text-text-primary mb-2 line-clamp-2 group-hover:text-blue-light transition-colors">
        {article.title}
      </h4>

      {/* Summary */}
      <p className="text-xs text-text-muted line-clamp-2 mb-2">
        {article.summary}
      </p>

      {/* Footer */}
      <div className="flex items-center gap-4 text-xs text-text-muted">
        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          <span>{timeAgo}</span>
        </div>
        <div className="flex items-center gap-1">
          <span>{article.readTime} min de leitura</span>
        </div>
        <ExternalLink className="w-3 h-3 ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
    </a>
  );
}

function NewsCardSkeleton() {
  return (
    <div className="p-3 rounded-lg border border-border">
      <div className="flex items-center gap-2 mb-2">
        <Skeleton className="w-5 h-5 rounded" />
        <Skeleton className="w-20 h-3" />
        <Skeleton className="ml-auto w-10 h-4 rounded" />
      </div>
      <Skeleton className="w-full h-4 mb-2" />
      <Skeleton className="w-3/4 h-4 mb-2" />
      <Skeleton className="w-full h-3 mb-2" />
      <Skeleton className="w-2/3 h-3 mb-2" />
      <div className="flex items-center gap-4">
        <Skeleton className="w-16 h-3" />
        <Skeleton className="w-20 h-3" />
      </div>
    </div>
  );
}

export default NewsWidget;
