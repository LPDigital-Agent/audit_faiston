"use client";

import { motion } from "framer-motion";
import { Radio, Construction } from "lucide-react";

/**
 * Dispatch Center Dashboard - Coming Soon
 *
 * Placeholder page for the Dispatch Center module.
 * This will be the central hub for dispatch operations,
 * real-time tracking, and communication management.
 */
export default function DispatchCenterDashboardPage() {
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
            <Radio className="w-12 h-12 text-white" />
          </div>
          <div className="absolute -bottom-2 -right-2 w-10 h-10 rounded-full bg-yellow-500/20 flex items-center justify-center">
            <Construction className="w-5 h-5 text-yellow-400" />
          </div>
        </div>

        {/* Title */}
        <h1 className="text-2xl font-bold text-text-primary mb-3">
          Dispatch Center
        </h1>

        {/* Description */}
        <p className="text-text-secondary mb-6">
          Central de despacho e comunicação em tempo real.
          Gerencie operações, rastreie entregas e coordene equipes
          de forma eficiente.
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
            <p className="text-sm font-medium text-text-primary">Rastreamento</p>
            <p className="text-xs text-text-muted">GPS em tempo real</p>
          </div>
          <div className="p-3 rounded-lg bg-white/5 border border-border">
            <p className="text-sm font-medium text-text-primary">Comunicação</p>
            <p className="text-xs text-text-muted">Chat integrado</p>
          </div>
          <div className="p-3 rounded-lg bg-white/5 border border-border">
            <p className="text-sm font-medium text-text-primary">Roteirização</p>
            <p className="text-xs text-text-muted">Otimização de rotas</p>
          </div>
          <div className="p-3 rounded-lg bg-white/5 border border-border">
            <p className="text-sm font-medium text-text-primary">Alertas</p>
            <p className="text-xs text-text-muted">Notificações push</p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
