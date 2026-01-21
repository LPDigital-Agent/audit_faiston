"use client";

import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { NexoStoryPanel } from "@/components/nexo/nexo-story-panel";
import { NexoVideoPanel } from "@/components/nexo/nexo-video-panel";

/**
 * Conheça o Nexo Page
 *
 * Landing page introducing the NEXO AI assistant to Faiston employees.
 * Features a two-column layout with:
 * - Left: Story panel with NEXO's history and capabilities
 * - Right: Video panel with Avatar presentation
 *
 * Responsive: Stacks vertically on mobile, side-by-side on desktop.
 */

export default function ConhecaNexoPage() {
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
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-text-primary">
            Conheça o <span className="gradient-text-nexo">Nexo</span>
          </h1>
        </div>
        <p className="text-text-secondary">
          Seu assistente de IA pessoal na Faiston
        </p>
      </motion.div>

      {/* Two Column Layout - Asymmetric for portrait video */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-6 items-stretch">
        {/* Left Panel - Story (flexible width) */}
        <NexoStoryPanel />

        {/* Right Panel - Video (fixed width for portrait) */}
        <NexoVideoPanel />
      </div>
    </div>
  );
}
