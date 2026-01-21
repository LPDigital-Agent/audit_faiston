"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

/**
 * NexoStoryPanel - Glass panel with the NEXO AI story
 *
 * Displays the history and capabilities of NEXO
 * in a beautiful glassmorphism container.
 */

export function NexoStoryPanel() {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, delay: 0.1 }}
      className={cn(
        "glass-elevated rounded-2xl",
        "border border-border",
        "p-4 lg:p-6",
        "h-full flex flex-col"
      )}
    >
          {/* Header */}
          <h2 className="text-xl font-bold text-text-primary mb-4">
            Minha <span className="gradient-text-nexo">História</span>
          </h2>

          {/* Story content */}
          <div className="flex-1 space-y-3 text-text-secondary leading-snug text-sm">
            {/* Introduction */}
            <p>
              O Nexo nasceu de uma ideia simples:{" "}
              <span className="text-text-primary font-medium">
                e se a tecnologia pudesse realmente facilitar o dia a dia das pessoas na Faiston?
              </span>
            </p>

            {/* Origin */}
            <p>
              Criado pela <span className="text-cyan-400 font-medium">LP Digital Hive</span>, usando o que há de mais moderno em{" "}
              <span className="text-text-primary">Inteligência Artificial</span> e{" "}
              <span className="text-text-primary">AI Avatars</span>, o Nexo não é um chatbot comum — e definitivamente não é mais um sistema complicado.
            </p>

            <p>
              Ele nasceu para ser o assistente inteligente da Faiston, vivendo dentro do{" "}
              <span className="gradient-text-nexo font-semibold">Faiston One</span>, para conectar informações, pessoas e decisões de forma simples e natural.
            </p>

            {/* Capabilities list */}
            <div className="py-2">
              <p className="text-text-primary font-semibold mb-2">O Nexo é:</p>
              <ul className="space-y-1">
                <li className="flex items-start gap-2">
                  <span className="text-cyan-400 mt-0.5">•</span>
                  <span>seu <strong className="text-text-primary">copiloto no trabalho</strong></span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-cyan-400 mt-0.5">•</span>
                  <span>um <strong className="text-text-primary">professor</strong> que ensina como fazemos as coisas aqui</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-cyan-400 mt-0.5">•</span>
                  <span>um <strong className="text-text-primary">assistente executivo</strong></span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-cyan-400 mt-0.5">•</span>
                  <span>um <strong className="text-text-primary">organizador silencioso</strong></span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-magenta-light mt-0.5">•</span>
                  <span>e, às vezes, aquele empurrãozinho antes do problema aparecer 😉</span>
                </li>
              </ul>
            </div>

            {/* Differential */}
            <div className="p-3 rounded-xl bg-white/5 border border-border">
              <p className="text-text-primary font-semibold mb-1">O grande diferencial?</p>
              <p className="flex items-start gap-2">
                <span className="text-xl">👉</span>
                <span>
                  <strong className="text-magenta-light">O Nexo não espera você pedir ajuda.</strong>
                  <br />
                  Se algo é importante, ele avisa.
                  <br />
                  Se algo pode ser automatizado, ele sugere.
                  <br />
                  Se a informação já existe, ele evita retrabalho.
                </span>
              </p>
            </div>

            {/* Benefits */}
            <p>
              Tudo isso para <span className="text-cyan-400">reduzir o estresse</span>,{" "}
              <span className="text-cyan-400">economizar tempo</span> e deixar o trabalho mais leve, fluido e até…{" "}
              <span className="text-magenta-light">mais divertido</span>.
            </p>

            {/* Learning */}
            <p className="italic text-text-muted">
              Ah, e uma última coisa:
              <br />
              <span className="text-text-secondary">
                se você aprende algo novo na Faiston, o Nexo aprende também.
              </span>
            </p>

            {/* Welcome */}
            <div className="pt-3 border-t border-border">
              <p className="font-semibold text-text-primary">
                Bem-vindo ao Faiston One.
              </p>
              <p>
                Você nunca vai trabalhar sozinho. <span className="text-lg">🚀</span>
              </p>
            </div>
          </div>
    </motion.div>
  );
}

export default NexoStoryPanel;
