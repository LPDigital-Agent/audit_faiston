"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import { cn } from "@/lib/utils";
import { GlassCard } from "@/components/shared/glass-card";
import { GradientText } from "@/components/shared/gradient-text";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Calendar, MessageSquare, Newspaper, ArrowRight, RefreshCw } from "lucide-react";
import { getGreeting } from "@/lib/utils";
import { nexoConversation } from "@/mocks/mock-data";
import { useAuth } from "@/contexts/AuthContext";
import { motion } from "framer-motion";
import {
  getDailySummary,
  type DailySummaryResponse,
  type NewsSectionData,
  type TipsSectionData,
} from "@/services/portalAgentcore";

// MANDATORY: All NEXO images must use the official avatar
const NEXO_AVATAR_PATH = "/Avatars/nexo-avatar.png";

// Feature flag to use real AgentCore (set to true after deployment)
const USE_AGENTCORE = process.env.NEXT_PUBLIC_USE_PORTAL_AGENTCORE === "true";

/**
 * NEXOHero - Main AI assistant widget for the dashboard
 *
 * Displays:
 * - Personalized greeting
 * - Daily summary (from AgentCore or mock)
 * - Quick suggestion chips
 *
 * Data source:
 * - Primary: Portal AgentCore (get_daily_summary action)
 * - Fallback: Mock data (when AgentCore unavailable)
 */

interface SummaryData {
  meetings: { count: number; highlight: string };
  messages: { count: number; highlight: string };
  news: { count: number; highlight: string };
}

const DEFAULT_SUMMARY: SummaryData = {
  meetings: { count: 3, highlight: "proxima: Daily em 15min" },
  messages: { count: 5, highlight: "no Teams" },
  news: { count: 2, highlight: "sobre AWS e Google AI" },
};

export function NEXOHero() {
  const { user } = useAuth();
  const greeting = getGreeting();
  const firstName = user?.name ? user.name.split(" ")[0] : "Usuario";

  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [summary, setSummary] = useState<SummaryData>(DEFAULT_SUMMARY);
  const [suggestions, setSuggestions] = useState<string[]>(nexoConversation.suggestions);
  const [dailyTip, setDailyTip] = useState<string | null>(null);

  const fetchDailySummary = async (showRefreshing = false) => {
    if (showRefreshing) setIsRefreshing(true);

    try {
      if (USE_AGENTCORE) {
        const response = await getDailySummary(true);

        if (response.data.success) {
          const { summary: summaryData } = response.data;

          // Extract news count from news section if available
          const newsSection = summaryData.sections.find((s) => s.type === "news");
          const newsData = newsSection?.data as NewsSectionData | undefined;
          const newsCount = newsData?.total_articles || 2;

          // Extract tip if available
          const tipsSection = summaryData.sections.find((s) => s.type === "tips");
          const tipsData = tipsSection?.data as TipsSectionData | undefined;
          if (tipsData?.tip) {
            setDailyTip(tipsData.tip);
          }

          // Update summary with real data
          // Note: Calendar/Teams still mock since MS Graph is deferred
          setSummary({
            meetings: { count: 3, highlight: "proxima: Daily em 15min" },
            messages: { count: 5, highlight: "no Teams" },
            news: { count: newsCount, highlight: "noticias de tecnologia" },
          });

          // Keep default suggestions for now
          setSuggestions(nexoConversation.suggestions);
        }
      } else {
        // Use mock data
        await new Promise((resolve) => setTimeout(resolve, 300));
        setSummary(DEFAULT_SUMMARY);
        setSuggestions(nexoConversation.suggestions);
      }
    } catch (err) {
      console.error("[NEXOHero] Error fetching daily summary:", err);
      // Keep default values on error
      setSummary(DEFAULT_SUMMARY);
      setSuggestions(nexoConversation.suggestions);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDailySummary();

    // Refresh every 30 minutes if AgentCore is enabled
    if (USE_AGENTCORE) {
      const interval = setInterval(() => fetchDailySummary(), 30 * 60 * 1000);
      return () => clearInterval(interval);
    }
  }, []);

  const handleRefresh = () => {
    fetchDailySummary(true);
  };

  return (
    <GlassCard className="h-full p-6 flex flex-col" hoverGlow={false}>
      {/* Header with NEXO Avatar - MANDATORY: Use official avatar */}
      <div className="flex items-center gap-3 mb-4">
        <motion.div
          className="w-14 h-14 rounded-full overflow-hidden border-2 border-cyan-400/50"
          animate={{
            boxShadow: [
              "0 0 15px rgba(0, 250, 251, 0.3)",
              "0 0 25px rgba(0, 250, 251, 0.5)",
              "0 0 15px rgba(0, 250, 251, 0.3)",
            ],
          }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        >
          <Image
            src={NEXO_AVATAR_PATH}
            alt="NEXO Avatar"
            width={56}
            height={56}
            className="w-full h-full object-cover"
            priority
          />
        </motion.div>
        <div className="flex-1">
          <GradientText variant="nexo" size="lg" bold>
            NEXO
          </GradientText>
          <p className="text-xs text-text-muted">Seu assistente de IA</p>
        </div>
        {USE_AGENTCORE && (
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={handleRefresh}
            disabled={isRefreshing}
            aria-label="Atualizar resumo"
          >
            <RefreshCw
              className={cn(
                "w-4 h-4 text-text-muted",
                isRefreshing && "animate-spin"
              )}
            />
          </Button>
        )}
      </div>

      {/* Greeting */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="mb-4"
      >
        <h2 className="text-h1 text-text-primary">
          {greeting}, <span className="gradient-text-action">{firstName}</span>!
        </h2>
      </motion.div>

      {/* Daily Summary */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="flex-1 mb-4"
      >
        <p className="text-sm text-text-secondary mb-3">
          Aqui esta seu resumo do dia:
        </p>

        {isLoading ? (
          <div className="space-y-3">
            <SummaryItemSkeleton />
            <SummaryItemSkeleton />
            <SummaryItemSkeleton />
          </div>
        ) : (
          <ul className="space-y-2">
            <SummaryItem
              icon={Calendar}
              text={`${summary.meetings.count} reunioes agendadas`}
              highlight={summary.meetings.highlight}
              color="blue"
            />
            <SummaryItem
              icon={MessageSquare}
              text={`${summary.messages.count} mensagens nao lidas`}
              highlight={summary.messages.highlight}
              color="magenta"
            />
            <SummaryItem
              icon={Newspaper}
              text={`${summary.news.count} noticias importantes`}
              highlight={summary.news.highlight}
              color="blue"
            />
          </ul>
        )}

        {/* Daily Tip (if available from AgentCore) */}
        {dailyTip && (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="mt-4 p-3 rounded-lg bg-blue-mid/10 border border-blue-mid/20"
          >
            <p className="text-xs text-text-secondary">
              <span className="text-blue-light font-medium">Dica:</span> {dailyTip}
            </p>
          </motion.div>
        )}
      </motion.div>

      {/* Quick Suggestions */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="flex flex-wrap gap-2"
      >
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-24 rounded-md" />
          ))
        ) : (
          suggestions.map((suggestion, index) => (
            <Button
              key={index}
              variant="outline"
              size="sm"
              className={cn(
                "bg-white/5 border-border hover:bg-white/10",
                "text-text-secondary hover:text-text-primary",
                "transition-all duration-150"
              )}
            >
              {suggestion}
              <ArrowRight className="w-3 h-3 ml-1" />
            </Button>
          ))
        )}
      </motion.div>
    </GlassCard>
  );
}

interface SummaryItemProps {
  icon: React.ElementType;
  text: string;
  highlight: string;
  color: "blue" | "magenta";
}

function SummaryItem({ icon: Icon, text, highlight, color }: SummaryItemProps) {
  return (
    <li className="flex items-center gap-3 text-sm">
      <div
        className={cn(
          "w-8 h-8 rounded-lg flex items-center justify-center",
          color === "blue" ? "bg-blue-mid/20" : "bg-magenta-mid/20"
        )}
      >
        <Icon
          className={cn(
            "w-4 h-4",
            color === "blue" ? "text-blue-light" : "text-magenta-light"
          )}
        />
      </div>
      <span className="text-text-primary">
        {text}{" "}
        <span className="text-text-muted">({highlight})</span>
      </span>
    </li>
  );
}

function SummaryItemSkeleton() {
  return (
    <div className="flex items-center gap-3">
      <Skeleton className="w-8 h-8 rounded-lg" />
      <div className="flex-1">
        <Skeleton className="w-40 h-4" />
      </div>
    </div>
  );
}

export default NEXOHero;
