"use client";

import { motion } from "framer-motion";
import { Sparkles, Send, Construction } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * NEXO Chat - AI Assistant Interface
 *
 * Placeholder page for the NEXO AI chat interface.
 * This will be the main conversational AI assistant
 * for Faiston employees.
 */
export default function NexoChatPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        className="max-w-lg w-full"
      >
        {/* Icon */}
        <div className="relative mx-auto mb-6">
          <div className="w-24 h-24 rounded-2xl gradient-nexo flex items-center justify-center">
            <Sparkles className="w-12 h-12 text-white" />
          </div>
          <div className="absolute -bottom-2 -right-2 w-10 h-10 rounded-full bg-yellow-500/20 flex items-center justify-center">
            <Construction className="w-5 h-5 text-yellow-400" />
          </div>
        </div>

        {/* Title */}
        <h1 className="text-2xl font-bold text-text-primary mb-2">
          Chat com <span className="gradient-text-nexo">NEXO</span>
        </h1>

        {/* Subtitle */}
        <p className="text-text-muted text-sm mb-4">
          Seu assistente de IA pessoal
        </p>

        {/* Description */}
        <p className="text-text-secondary mb-6">
          Converse com o NEXO para obter ajuda, tirar dúvidas sobre processos
          internos, agendar reuniões, e muito mais. O NEXO está integrado
          a todos os sistemas da Faiston.
        </p>

        {/* Coming Soon Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-yellow-500/10 border border-yellow-500/30 mb-8">
          <Construction className="w-4 h-4 text-yellow-400" />
          <span className="text-sm font-medium text-yellow-400">
            Em Desenvolvimento
          </span>
        </div>

        {/* Mock Chat Input */}
        <div className="w-full p-4 rounded-2xl bg-white/5 border border-border">
          <div className="flex items-center gap-3">
            <div className="flex-1 px-4 py-3 rounded-xl bg-white/5 text-left">
              <span className="text-text-muted text-sm">
                Pergunte algo ao NEXO...
              </span>
            </div>
            <Button
              size="icon"
              className="w-11 h-11 rounded-xl gradient-nexo"
              disabled
            >
              <Send className="w-5 h-5 text-white" />
            </Button>
          </div>
        </div>

        {/* Capabilities Preview */}
        <div className="mt-8 grid grid-cols-2 gap-3 text-left">
          <div className="p-3 rounded-lg bg-white/5 border border-border">
            <p className="text-sm font-medium text-text-primary">Calendário</p>
            <p className="text-xs text-text-muted">Agende reuniões</p>
          </div>
          <div className="p-3 rounded-lg bg-white/5 border border-border">
            <p className="text-sm font-medium text-text-primary">Processos</p>
            <p className="text-xs text-text-muted">Tire dúvidas</p>
          </div>
          <div className="p-3 rounded-lg bg-white/5 border border-border">
            <p className="text-sm font-medium text-text-primary">Documentos</p>
            <p className="text-xs text-text-muted">Busque informações</p>
          </div>
          <div className="p-3 rounded-lg bg-white/5 border border-border">
            <p className="text-sm font-medium text-text-primary">Relatórios</p>
            <p className="text-xs text-text-muted">Gere insights</p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
