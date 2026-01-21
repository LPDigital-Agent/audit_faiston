"use client";

import { motion } from "framer-motion";
import { GraduationCap, Construction, BookOpen, Award, Users, PlayCircle } from "lucide-react";

/**
 * Faiston Academy Dashboard - Coming Soon
 *
 * Placeholder page for the Faiston Academy module.
 * This will be the corporate learning platform with
 * courses, certifications, and training programs.
 */
export default function FaistonAcademyDashboardPage() {
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
          <div className="w-24 h-24 rounded-2xl gradient-nexo flex items-center justify-center">
            <GraduationCap className="w-12 h-12 text-white" />
          </div>
          <div className="absolute -bottom-2 -right-2 w-10 h-10 rounded-full bg-yellow-500/20 flex items-center justify-center">
            <Construction className="w-5 h-5 text-yellow-400" />
          </div>
        </div>

        {/* Title */}
        <h1 className="text-2xl font-bold text-text-primary mb-3">
          Faiston Academy
        </h1>

        {/* Description */}
        <p className="text-text-secondary mb-6">
          Plataforma de aprendizado corporativo.
          Desenvolva habilidades, obtenha certificações
          e acompanhe seu progresso profissional.
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
              <PlayCircle className="w-4 h-4 text-blue-light" />
              <p className="text-sm font-medium text-text-primary">Cursos</p>
            </div>
            <p className="text-xs text-text-muted">Vídeos e trilhas</p>
          </div>
          <div className="p-3 rounded-lg bg-white/5 border border-border">
            <div className="flex items-center gap-2 mb-1">
              <Award className="w-4 h-4 text-magenta-light" />
              <p className="text-sm font-medium text-text-primary">Certificados</p>
            </div>
            <p className="text-xs text-text-muted">Reconhecimento</p>
          </div>
          <div className="p-3 rounded-lg bg-white/5 border border-border">
            <div className="flex items-center gap-2 mb-1">
              <BookOpen className="w-4 h-4 text-green-400" />
              <p className="text-sm font-medium text-text-primary">Materiais</p>
            </div>
            <p className="text-xs text-text-muted">PDFs e docs</p>
          </div>
          <div className="p-3 rounded-lg bg-white/5 border border-border">
            <div className="flex items-center gap-2 mb-1">
              <Users className="w-4 h-4 text-yellow-400" />
              <p className="text-sm font-medium text-text-primary">Turmas</p>
            </div>
            <p className="text-xs text-text-muted">Aprendizado em grupo</p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
