// =============================================================================
// Notes Editor Panel - Faiston Academy
// =============================================================================
// Personal notes editor with auto-save functionality.
// Allows students to take notes during video lessons.
// =============================================================================

'use client';

import { useAcademyClassroom } from '@/contexts/AcademyClassroomContext';
import { Check, Loader2, FileText } from 'lucide-react';
import { Textarea } from '@/components/ui/textarea';

export function NotesEditorPanel() {
  const { notes, updateNotes, notesSaving, episodeId } = useAcademyClassroom();

  // Count words and characters
  const wordCount = notes.trim() ? notes.trim().split(/\s+/).length : 0;
  const charCount = notes.length;

  return (
    <div className="h-full flex flex-col bg-black/20">
      {/* Header */}
      <div className="px-6 py-5 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 flex items-center justify-center border border-[var(--faiston-magenta-mid,#C31B8C)]/20">
              <FileText className="w-6 h-6 text-[var(--faiston-magenta-mid,#C31B8C)]" />
            </div>
            <div>
              <h3 className="text-xl font-semibold text-white">Notas</h3>
              <p className="text-sm text-white/40">Anote os pontos importantes da aula</p>
            </div>
          </div>

          {/* Save Status */}
          <div className="flex items-center gap-1.5">
            {notesSaving ? (
              <>
                <Loader2 className="w-4 h-4 text-[var(--faiston-magenta-mid,#C31B8C)] animate-spin" />
                <span className="text-xs text-white/50">Salvando...</span>
              </>
            ) : (
              <>
                <Check className="w-4 h-4 text-[var(--faiston-magenta-mid,#C31B8C)]" />
                <span className="text-xs text-white/50">Salvo</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Textarea */}
      <div className="flex-1 p-6 overflow-hidden">
        <Textarea
          value={notes}
          onChange={(e) => updateNotes(e.target.value)}
          placeholder="Digite suas anotacoes aqui...

Dicas:
• Anote os pontos principais do video
• Escreva perguntas para pesquisar depois
• Registre insights e ideias

Suas anotacoes sao salvas automaticamente."
          className="h-full w-full resize-none bg-white/[0.03] border-white/10 text-white placeholder:text-white/20 rounded-xl focus:border-[var(--faiston-magenta-mid,#C31B8C)]/50 focus:ring-1 focus:ring-[var(--faiston-magenta-mid,#C31B8C)]/20"
        />
      </div>

      {/* Footer with stats */}
      <div className="px-6 py-3 border-t border-white/5 flex items-center justify-between text-xs text-white/40">
        <span>Episodio {episodeId}</span>
        <span>
          {wordCount} {wordCount === 1 ? 'palavra' : 'palavras'} · {charCount} caracteres
        </span>
      </div>
    </div>
  );
}
