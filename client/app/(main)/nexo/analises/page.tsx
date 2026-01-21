"use client";

import { motion } from "framer-motion";
import { Brain, Construction, BarChart3, TrendingUp, FileSearch, Lightbulb } from "lucide-react";

/**
 * NEXO Análises AI - AI-Powered Analytics
 *
 * Placeholder page for AI-powered analytics and insights.
 * This will provide intelligent data analysis, predictions,
 * and actionable recommendations.
 */
export default function NexoAnalisesPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        className="max-w-md"
      >
        {/* Icon */}
        <div className="relative mx-auto mb-6">
          <div className="w-24 h-24 rounded-2xl gradient-action flex items-center justify-center">
            <Brain className="w-12 h-12 text-white" />
          </div>
          <div className="absolute -bottom-2 -right-2 w-10 h-10 rounded-full bg-yellow-500/20 flex items-center justify-center">
            <Construction className="w-5 h-5 text-yellow-400" />
          </div>
        </div>

        {/* Title */}
        <h1 className="text-2xl font-bold text-text-primary mb-3">
          Análises <span className="gradient-text-action">AI</span>
        </h1>

        {/* Description */}
        <p className="text-text-secondary mb-6">
          Análises inteligentes e insights gerados por IA.
          Descubra padrões, previsões e recomendações
          baseadas nos dados da sua empresa.
        </p>

        {/* Coming Soon Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-yellow-500/10 border border-yellow-500/30">
          <Construction className="w-4 h-4 text-yellow-400" />
          <span className="text-sm font-medium text-yellow-400">
            Em Desenvolvimento
          </span>
        </div>

        {/* Feature Preview */}
        <div className="mt-8 grid grid-cols-2 gap-3 text-left">
          <div className="p-3 rounded-lg bg-white/5 border border-border">
            <div className="flex items-center gap-2 mb-1">
              <BarChart3 className="w-4 h-4 text-blue-light" />
              <p className="text-sm font-medium text-text-primary">Dashboards</p>
            </div>
            <p className="text-xs text-text-muted">Visualizações inteligentes</p>
          </div>
          <div className="p-3 rounded-lg bg-white/5 border border-border">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp className="w-4 h-4 text-magenta-light" />
              <p className="text-sm font-medium text-text-primary">Previsões</p>
            </div>
            <p className="text-xs text-text-muted">Tendências futuras</p>
          </div>
          <div className="p-3 rounded-lg bg-white/5 border border-border">
            <div className="flex items-center gap-2 mb-1">
              <FileSearch className="w-4 h-4 text-green-400" />
              <p className="text-sm font-medium text-text-primary">Anomalias</p>
            </div>
            <p className="text-xs text-text-muted">Detecção automática</p>
          </div>
          <div className="p-3 rounded-lg bg-white/5 border border-border">
            <div className="flex items-center gap-2 mb-1">
              <Lightbulb className="w-4 h-4 text-yellow-400" />
              <p className="text-sm font-medium text-text-primary">Insights</p>
            </div>
            <p className="text-xs text-text-muted">Recomendações AI</p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
