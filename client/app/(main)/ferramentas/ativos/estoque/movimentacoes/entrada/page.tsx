'use client';

// =============================================================================
// Entrada de Materiais Page - SGA Inventory Module
// =============================================================================
// REDESIGNED: Smart Universal File Importer with 2 tabs:
// - Upload Inteligente: Auto-detects and processes ALL file types
//   (XML, PDF, CSV, XLSX, JPG, PNG, TXT) via AI agents
// - Manual: Direct entry without source file
//
// Architecture: SmartUploadZone → useSmartImporter → Backend Agent Routing
// - XML/PDF/Image → IntakeAgent (NF extraction)
// - CSV/XLSX → ImportAgent (spreadsheet mapping)
// - TXT → ImportAgent + Gemini AI (intelligent text extraction)
// =============================================================================

import { useState } from 'react';
import Link from 'next/link';
import { AnimatePresence, motion } from 'framer-motion';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  ArrowLeft,
  Upload,
  PenLine,
  X,
  FolderPlus,
  CheckCircle2,
  RefreshCw,
  Briefcase,
  Brain,
} from 'lucide-react';
import {
  useAssetManagement,
  useManualEntry,
  useSmartImporter,
  type ManualEntryRequest,
} from '@/hooks/ativos';

// BUG-027: Debug Analytics via AgentCore
import { recordDebugAction, type DebugAction } from '@/services/sgaAgentcore';

// Smart Import Components (NEW)
import {
  SmartUploadZone,
  SmartPreview,
  EntradaManualTab,
  PendingEntriesList,
} from './components';

// NEXO Intelligent Import Components
import { SmartImportNexoPanel } from '@/components/ferramentas/ativos/estoque/nexo';

// =============================================================================
// Tab Types
// =============================================================================

type EntradaTab = 'smart' | 'manual';

// =============================================================================
// Page Component
// =============================================================================

export default function EntradaPage() {
  const [activeTab, setActiveTab] = useState<EntradaTab>('smart');
  // File stored for NEXO intelligent analysis flow
  const [nexoFile, setNexoFile] = useState<File | null>(null);

  // Smart Importer Hook (NEW - unified for all file types)
  // Includes NEXO Intelligent Import toggle for agentic AI-first flow
  const {
    detectedType,
    isProcessing: smartProcessing,
    progress: smartProgress,
    error: smartError,
    preview: smartPreview,
    uploadAndProcess,
    clearPreview: clearSmartPreview,
    confirmEntry: confirmSmartEntry,
    pendingEntries,
    pendingEntriesLoading,
    assignProject,
    // NEXO toggle - SmartImportNexoPanel manages its own state via useSmartImportNexo
    useNexoFlow,
    setUseNexoFlow,
  } = useSmartImporter();

  // Asset Management Hook for master data
  const { projects, locations, partNumbers } = useAssetManagement();

  // Manual Entry Hook (real implementation)
  const {
    isProcessing: manualProcessing,
    error: manualError,
    submitEntry,
  } = useManualEntry();

  // Project Assignment Modal state
  const [projectModalOpen, setProjectModalOpen] = useState(false);
  const [projectModalEntryId, setProjectModalEntryId] = useState<string | null>(null);
  const [projectModalProject, setProjectModalProject] = useState('');
  const [isAssigningProject, setIsAssigningProject] = useState(false);

  // Handle opening project assignment modal
  const openProjectModal = (entryId: string) => {
    setProjectModalEntryId(entryId);
    setProjectModalProject('');
    setProjectModalOpen(true);
  };

  // Handle project assignment
  const handleAssignProject = async () => {
    if (!projectModalEntryId || !projectModalProject) return;

    setIsAssigningProject(true);
    try {
      await assignProject(projectModalEntryId, projectModalProject);
      setProjectModalOpen(false);
      setProjectModalEntryId(null);
      setProjectModalProject('');
    } catch {
      // Error handling
    } finally {
      setIsAssigningProject(false);
    }
  };

  // Handle Smart Upload (unified for ALL file types)
  // Project and Location are optional - can be set in preview after analysis
  // When NEXO flow is enabled for spreadsheets, uses intelligent analysis with questions
  const handleSmartUpload = async (file: File, projectId: string | null, locationId: string | null) => {
    const isSpreadsheet = file.name.endsWith('.xlsx') || file.name.endsWith('.csv');

    // AI-First: NEXO ALWAYS analyzes spreadsheets autonomously (no toggle needed)
    if (isSpreadsheet) {
      console.log('[EntradaPage] AI-First: NEXO autonomous analysis for:', file.name);
      // Store file - SmartImportNexoPanel will handle analysis internally
      setNexoFile(file);
    } else {
      // NF processing (XML/PDF/Image) continues to use standard flow
      await uploadAndProcess(file, projectId, locationId);
    }
  };

  // Handle NEXO analysis complete
  // NOTE: Do NOT clear nexoFile here - let SmartImportNexoPanel show success screen
  // The panel will call onCancel when user clicks "Nova Importação"
  const handleNexoComplete = (sessionId: string) => {
    console.log('[EntradaPage] NEXO import complete, session:', sessionId);
    // Keep nexoFile set so SmartImportNexoPanel shows success state
    // The panel's "Nova Importação" button calls onCancel which will clear it
  };

  // Handle NEXO cancel
  const handleNexoCancel = () => {
    console.log('[EntradaPage] NEXO analysis cancelled');
    setNexoFile(null);
  };

  // BUG-027 FIX: Handle debug analysis panel actions with analytics
  const handleDebugAction = async (action: DebugAction) => {
    console.log('[EntradaPage] Debug action:', action);

    // Track action via AgentCore (async, non-blocking)
    if (smartError?.debug_analysis) {
      recordDebugAction({
        action,
        error_signature: smartError.debug_analysis.error_signature || 'unknown',
        error_type: smartError.debug_analysis.error_type || 'unknown',
        suggested_action: (smartError.debug_analysis.suggested_action as DebugAction) || 'retry',
        ...(action === 'escalate' && { debug_analysis: smartError.debug_analysis }),
      }).catch((err) => {
        // Non-blocking: log failure but don't interrupt user flow
        console.warn('[EntradaPage] Failed to record debug action:', err);
      });
    }

    // Execute action
    switch (action) {
      case 'retry':
        // Clear error and allow user to retry upload
        // Note: useSmartImporter already handles reset on new upload
        break;
      case 'escalate':
        // Logged for batch review via AgentCore (per interview decision)
        console.log('[EntradaPage] Escalation logged for batch review');
        break;
      case 'fallback':
        // Switch to manual entry tab
        setActiveTab('manual');
        break;
      case 'abort':
        // Clear state and reset
        clearSmartPreview();
        break;
    }
  };

  // Handle Smart Confirm
  const handleSmartConfirm = async () => {
    await confirmSmartEntry();
  };

  // Handle Manual submit (real implementation using useManualEntry hook)
  const handleManualSubmit = async (params: Omit<ManualEntryRequest, 'items'>) => {
    await submitEntry(params);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/ferramentas/ativos/estoque/movimentacoes">
                <ArrowLeft className="w-4 h-4 mr-1" />
                Movimentacoes
              </Link>
            </Button>
          </div>
          <h1 className="text-xl font-semibold text-text-primary">
            Entrada de Materiais
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Upload inteligente ou entrada manual
          </p>
        </div>
      </div>

      {/* NEW: 2 Tabs Only (Smart Upload + Manual) */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as EntradaTab)}>
        <TabsList className="w-full grid grid-cols-2 bg-white/5 p-1 rounded-lg">
          <TabsTrigger
            value="smart"
            className="flex items-center gap-2 data-[state=active]:bg-gradient-to-r data-[state=active]:from-blue-mid/20 data-[state=active]:to-magenta-mid/20 data-[state=active]:text-blue-light"
          >
            <Upload className="w-4 h-4" />
            <span>Upload Inteligente</span>
          </TabsTrigger>
          <TabsTrigger
            value="manual"
            className="flex items-center gap-2 data-[state=active]:bg-purple-500/20 data-[state=active]:text-purple-400"
          >
            <PenLine className="w-4 h-4" />
            <span>Manual</span>
          </TabsTrigger>
        </TabsList>

        {/* Smart Upload Tab Content */}
        <TabsContent value="smart" className="mt-6 space-y-4">
          {/* NEXO Intelligent Import Toggle */}
          <div className="flex items-center justify-between p-3 bg-gradient-to-r from-purple-500/10 to-cyan-500/10 rounded-lg border border-purple-500/20">
            <div className="flex items-center gap-3">
              <Brain className="w-5 h-5 text-purple-400" />
              <div>
                <Label htmlFor="nexo-toggle" className="text-sm font-medium text-text-primary cursor-pointer">
                  Importação Inteligente com NEXO
                </Label>
                <p className="text-xs text-text-muted">
                  NEXO analisa e faz perguntas para mapear colunas automaticamente
                </p>
              </div>
            </div>
            <Switch
              id="nexo-toggle"
              checked={useNexoFlow}
              onCheckedChange={setUseNexoFlow}
            />
          </div>

          {/* NEXO Analysis Panel - shown when NEXO is analyzing a file */}
          {nexoFile ? (
            <SmartImportNexoPanel
              file={nexoFile}
              onComplete={handleNexoComplete}
              onCancel={handleNexoCancel}
            />
          ) : !smartPreview ? (
            <SmartUploadZone
              onFileSelect={handleSmartUpload}
              isProcessing={smartProcessing}
              progress={smartProgress}
              error={smartError}
              detectedType={detectedType}
              onDebugAction={handleDebugAction}
            />
          ) : (
            <SmartPreview
              preview={smartPreview}
              onConfirm={handleSmartConfirm}
              onCancel={clearSmartPreview}
            />
          )}
        </TabsContent>

        {/* Manual Tab Content (existing component) */}
        <TabsContent value="manual" className="mt-6">
          <EntradaManualTab
            isProcessing={manualProcessing}
            error={manualError}
            projects={projects}
            locations={locations}
            partNumbers={partNumbers}
            onSubmit={handleManualSubmit}
            onClear={() => {}}
          />
        </TabsContent>
      </Tabs>

      {/* Pending Entries (shown when no preview in progress) */}
      {!smartPreview && pendingEntries.length > 0 && (
        <PendingEntriesList
          entries={pendingEntries}
          isLoading={pendingEntriesLoading}
          onAssignProject={openProjectModal}
          onReview={(id) => console.log('Review entry:', id)}
        />
      )}

      {/* Project Assignment Modal */}
      <AnimatePresence>
        {projectModalOpen && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => !isAssigningProject && setProjectModalOpen(false)}
          >
            <motion.div
              className="bg-surface-elevated border border-border rounded-xl p-6 w-full max-w-md mx-4 shadow-xl"
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Modal Header */}
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-orange-500/20 flex items-center justify-center">
                    <FolderPlus className="w-5 h-5 text-orange-400" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-text-primary">
                      Atribuir Projeto
                    </h3>
                    <p className="text-xs text-text-muted">
                      Selecione o projeto para esta entrada
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => !isAssigningProject && setProjectModalOpen(false)}
                  className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                  disabled={isAssigningProject}
                >
                  <X className="w-5 h-5 text-text-muted" />
                </button>
              </div>

              {/* Project Selection */}
              <div className="mb-6">
                <label className="text-sm font-medium text-text-primary mb-2 block">
                  <Briefcase className="w-4 h-4 inline mr-2" />
                  Projeto
                </label>
                <select
                  className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                  value={projectModalProject}
                  onChange={(e) => setProjectModalProject(e.target.value)}
                  disabled={isAssigningProject}
                >
                  <option value="">Selecione o projeto...</option>
                  {projects.filter(p => p.is_active).map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.code} - {project.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Actions */}
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => setProjectModalOpen(false)}
                  disabled={isAssigningProject}
                >
                  Cancelar
                </Button>
                <Button
                  className="flex-1 bg-orange-500 hover:bg-orange-600"
                  onClick={handleAssignProject}
                  disabled={!projectModalProject || isAssigningProject}
                >
                  {isAssigningProject ? (
                    <>
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                      Atribuindo...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4 mr-2" />
                      Atribuir Projeto
                    </>
                  )}
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
