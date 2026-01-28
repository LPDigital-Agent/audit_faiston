// =============================================================================
// Learning Map Section - Faiston Academy Dashboard
// =============================================================================
// Displays the student's learning journey with progress, level, and metrics.
// Shows overall progress, current level badge, and key statistics.
// =============================================================================

'use client';

import { Rocket, Zap, Clock, Flame } from 'lucide-react';
import { motion } from 'framer-motion';
import { MetricCard } from './MetricCard';

interface LearningMapSectionProps {
  progress: number;
  levelName: string;
  skillsMastered: number;
  totalSkills: number;
  timeInvested: string;
  streak: number;
}

export function LearningMapSection({
  progress,
  levelName,
  skillsMastered,
  totalSkills,
  timeInvested,
  streak,
}: LearningMapSectionProps) {
  return (
    <div className="bg-white/5 border border-white/10 rounded-2xl p-4">
      {/* Header */}
      <div className="mb-4">
        <h2 className="text-lg font-bold text-white mb-1">Mapa de Aprendizado</h2>
        <p className="text-xs text-white/50">Sua Jornada de Aprendizado</p>
      </div>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs text-white/70">Progresso Geral</span>
          <span className="text-xs font-semibold text-white">{progress}%</span>
        </div>
        <div className="h-2 bg-white/10 rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 1, ease: 'easeOut' }}
            className="h-full rounded-full"
            style={{
              background:
                'linear-gradient(90deg, var(--faiston-magenta-mid, #C31B8C) 0%, var(--faiston-blue-mid, #2226C0) 100%)',
            }}
          />
        </div>
      </div>

      {/* Level Badge */}
      <div className="flex items-center gap-2.5 mb-4 p-3 bg-white/5 border border-white/10 rounded-xl">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 flex items-center justify-center flex-shrink-0">
          <Rocket className="w-4 h-4 text-[var(--faiston-magenta-mid,#C31B8C)]" />
        </div>
        <div className="min-w-0">
          <p className="text-[10px] text-white/50 uppercase tracking-wider">Nivel Atual</p>
          <p className="text-base font-bold text-[var(--faiston-magenta-mid,#C31B8C)] truncate">
            {levelName}
          </p>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-3 gap-2">
        <MetricCard icon={Zap} label="Habilidades" value={`${skillsMastered}/${totalSkills}`} trend="up" />
        <MetricCard icon={Clock} label="Tempo" value={timeInvested} />
        <MetricCard icon={Flame} label="Sequencia" value={`${streak}d`} trend="up" />
      </div>
    </div>
  );
}
