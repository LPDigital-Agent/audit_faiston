// =============================================================================
// Coach NEXO Card - Faiston Academy Dashboard
// =============================================================================
// AI coach recommendation card showing personalized learning suggestions.
// NEXO provides XP potential and actionable recommendations.
// =============================================================================

'use client';

import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';

interface CoachNexoCardProps {
  message: string;
  xpPotential: number;
  onViewRecommendations: () => void;
}

export function CoachNexoCard({ message, xpPotential, onViewRecommendations }: CoachNexoCardProps) {
  const [imageError, setImageError] = useState(false);

  return (
    <div className="bg-white/5 border border-white/10 rounded-2xl p-4 h-full flex flex-col">
      {/* Header with Avatar inline */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-shrink-0">
          <div className="w-12 h-12 rounded-xl overflow-hidden">
            {imageError ? (
              <div className="w-full h-full bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)] flex items-center justify-center">
                <span className="text-xl font-bold text-white">N</span>
              </div>
            ) : (
              <img
                src="/images/nexo-avatar.jpg"
                alt="Coach NEXO"
                className="w-full h-full object-cover"
                onError={() => setImageError(true)}
              />
            )}
          </div>
          {/* Online indicator */}
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: 'spring', stiffness: 500 }}
            className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-green-500 rounded-full border-2 border-[#151720]"
          />
        </div>
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)] flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <h3 className="text-base font-semibold text-white">Coach NEXO</h3>
        </div>
      </div>

      {/* Message Bubble */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-white/5 border border-white/10 rounded-xl p-3 mb-3 flex-1"
      >
        <p className="text-xs text-white/80 leading-relaxed">{message}</p>
      </motion.div>

      {/* XP Text */}
      <p className="text-center text-xs font-medium text-[var(--faiston-magenta-mid,#C31B8C)] mb-3">
        +{xpPotential} XP potencial
      </p>

      {/* CTA Button */}
      <Button
        onClick={onViewRecommendations}
        className="w-full bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)] hover:opacity-90 text-white text-sm py-2 border-0"
      >
        Ver recomendacoes
      </Button>
    </div>
  );
}
