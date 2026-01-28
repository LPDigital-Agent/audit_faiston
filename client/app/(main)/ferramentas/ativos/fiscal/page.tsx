"use client";

// =============================================================================
// Fiscal Page - Tax Documents and Accounting
// =============================================================================
// Displays NF documents, tax obligations, and fiscal calendar.
// NOW SHOWS REAL DATA OR EMPTY STATE - No more mock data!
// =============================================================================

import { useState } from "react";
import { GlassCard, GlassCardHeader, GlassCardTitle } from "@/components/shared/glass-card";
import { AssetManagementHeader } from "@/components/ferramentas/ativos/asset-management-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import {
  FileText,
  Search,
  Filter,
  Download,
  Calendar,
  DollarSign,
  CheckCircle,
  AlertTriangle,
  Clock,
  ExternalLink,
  Upload,
  ChevronRight,
  InboxIcon,
} from "lucide-react";
import { formatCurrency } from "@/lib/ativos/constants";
import { motion } from "framer-motion";

/**
 * Fiscal Page - Tax Documents and Accounting
 *
 * Displays NF documents, tax obligations, and fiscal calendar.
 * NOW USES REAL DATA - Empty state when no documents exist.
 */

const statusConfig: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  autorizado: { label: "Autorizado", color: "bg-green-500/20 text-green-400", icon: CheckCircle },
  pendente: { label: "Pendente", color: "bg-yellow-500/20 text-yellow-400", icon: Clock },
  cancelado: { label: "Cancelado", color: "bg-red-500/20 text-red-400", icon: AlertTriangle },
  denegado: { label: "Denegado", color: "bg-red-500/20 text-red-400", icon: AlertTriangle },
};

const tipoLabels: Record<string, string> = {
  nfe: "NF",
  nfse: "NFS-e",
  cte: "CT-e",
};

// Real fiscal documents - empty array until backend integration
// TODO: Replace with useFiscalDocuments() hook when backend is ready
type FiscalDocument = {
  id: string;
  numero: string;
  tipo: string;
  status: string;
  valor: number;
  dataEmissao: string;
  cliente?: string;
};

type FiscalObligation = {
  id: string;
  titulo: string;
  dataVencimento: string;
  status: string;
  tipo: string;
};

export default function FiscalPage() {
  // Real data - empty until backend integration
  const fiscalDocuments: FiscalDocument[] = [];
  const fiscalObligations: FiscalObligation[] = [];

  // Stable timestamp for calculating days until due (React 19 purity requirement)
  // Using useState initializer so Date.now() is only called once during mount
  const [now] = useState(() => Date.now());

  const totalValue = fiscalDocuments.reduce((sum, doc) => sum + doc.valor, 0);
  const emittedCount = fiscalDocuments.filter(d => d.status === "autorizado").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <AssetManagementHeader
        title="Fiscal e Contábil"
        subtitle="Documentos fiscais e obrigações acessórias"
        primaryAction={{
          label: "Novo Documento",
          onClick: () => console.log("Novo documento"),
          icon: <Upload className="w-4 h-4" />,
        }}
        secondaryActions={[
          {
            label: "Exportar",
            onClick: () => console.log("Exportar"),
            icon: <Download className="w-4 h-4" />,
          },
        ]}
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0 }}
        >
          <GlassCard className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-blue-mid/20 flex items-center justify-center">
                <FileText className="w-5 h-5 text-blue-light" />
              </div>
              <div>
                <p className="text-2xl font-bold text-text-primary">
                  {fiscalDocuments.length}
                </p>
                <p className="text-sm text-text-muted">Total Documentos</p>
              </div>
            </div>
          </GlassCard>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <GlassCard className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
                <CheckCircle className="w-5 h-5 text-green-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-text-primary">{emittedCount}</p>
                <p className="text-sm text-text-muted">Emitidas</p>
              </div>
            </div>
          </GlassCard>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <GlassCard className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-yellow-500/20 flex items-center justify-center">
                <Clock className="w-5 h-5 text-yellow-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-text-primary">
                  {fiscalDocuments.filter(d => d.status === "pendente").length}
                </p>
                <p className="text-sm text-text-muted">Pendentes</p>
              </div>
            </div>
          </GlassCard>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <GlassCard className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-magenta-mid/20 flex items-center justify-center">
                <DollarSign className="w-5 h-5 text-magenta-light" />
              </div>
              <div>
                <p className="text-2xl font-bold text-text-primary">
                  {formatCurrency(totalValue)}
                </p>
                <p className="text-sm text-text-muted">Valor Total</p>
              </div>
            </div>
          </GlassCard>
        </motion.div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Documents Table */}
        <div className="lg:col-span-2">
          <GlassCard>
            <GlassCardHeader>
              <div className="flex items-center justify-between w-full gap-4">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-blue-light" />
                  <GlassCardTitle>Documentos Fiscais</GlassCardTitle>
                </div>
                <div className="flex gap-2">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                    <Input
                      placeholder="Buscar..."
                      className="pl-10 bg-white/5 border-border h-9 w-48"
                    />
                  </div>
                  <Button variant="outline" size="sm" className="border-border">
                    <Filter className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </GlassCardHeader>

            {/* Table Header */}
            <div className="hidden md:grid grid-cols-12 gap-4 px-4 py-3 border-b border-border text-xs font-medium text-text-muted uppercase tracking-wider">
              <div className="col-span-3">Documento</div>
              <div className="col-span-2">Tipo</div>
              <div className="col-span-2">Status</div>
              <div className="col-span-2">Valor</div>
              <div className="col-span-2">Data</div>
              <div className="col-span-1"></div>
            </div>

            <ScrollArea className="max-h-[400px]">
              <div className="divide-y divide-border">
                {fiscalDocuments.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <InboxIcon className="w-12 h-12 text-text-muted mb-3" />
                    <p className="text-sm font-medium text-text-primary mb-1">
                      Nenhum documento fiscal
                    </p>
                    <p className="text-xs text-text-muted">
                      Os documentos fiscais aparecerão aqui após a integração
                    </p>
                  </div>
                ) : (
                  fiscalDocuments.map((doc, index) => {
                    const status = statusConfig[doc.status];
                    const StatusIcon = status.icon;

                    return (
                      <motion.div
                        key={doc.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.03 }}
                        className="grid grid-cols-1 md:grid-cols-12 gap-4 px-4 py-4 hover:bg-white/5 transition-colors cursor-pointer items-center"
                      >
                        {/* Document Info */}
                        <div className="col-span-3">
                          <p className="text-sm font-medium text-text-primary">
                            {doc.numero}
                          </p>
                          <p className="text-xs text-text-muted truncate">
                            {doc.cliente || "Cliente não informado"}
                          </p>
                        </div>

                        {/* Type */}
                        <div className="col-span-2">
                          <Badge variant="outline" className="text-xs">
                            {tipoLabels[doc.tipo]}
                          </Badge>
                        </div>

                        {/* Status */}
                        <div className="col-span-2">
                          <Badge className={status.color}>
                            <StatusIcon className="w-3 h-3 mr-1" />
                            {status.label}
                          </Badge>
                        </div>

                        {/* Value */}
                        <div className="col-span-2">
                          <p className="text-sm text-text-primary">
                            {formatCurrency(doc.valor)}
                          </p>
                        </div>

                        {/* Date */}
                        <div className="col-span-2">
                          <p className="text-sm text-text-muted">
                            {new Date(doc.dataEmissao).toLocaleDateString("pt-BR")}
                          </p>
                        </div>

                        {/* Actions */}
                        <div className="col-span-1 flex justify-end">
                          <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                            <ExternalLink className="w-4 h-4" />
                          </Button>
                        </div>
                      </motion.div>
                    );
                  })
                )}
              </div>
            </ScrollArea>
          </GlassCard>
        </div>

        {/* Fiscal Calendar / Obligations */}
        <div className="lg:col-span-1">
          <GlassCard className="h-full">
            <GlassCardHeader>
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-magenta-light" />
                <GlassCardTitle>Obrigações</GlassCardTitle>
              </div>
            </GlassCardHeader>

            <ScrollArea className="h-[400px]">
              <div className="space-y-3 p-4">
                {fiscalObligations.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <Calendar className="w-10 h-10 text-text-muted mb-3" />
                    <p className="text-sm font-medium text-text-primary mb-1">
                      Nenhuma obrigação pendente
                    </p>
                    <p className="text-xs text-text-muted">
                      As obrigações fiscais aparecerão aqui
                    </p>
                  </div>
                ) : (
                  fiscalObligations.map((obligation, index) => {
                    const daysUntil = Math.ceil(
                      (new Date(obligation.dataVencimento).getTime() - now) /
                        (1000 * 60 * 60 * 24)
                    );
                    const isUrgent = daysUntil <= 7;

                    return (
                      <motion.div
                        key={obligation.id}
                        initial={{ opacity: 0, x: 10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.1 }}
                        className={`p-4 rounded-lg border ${
                          isUrgent
                            ? "border-yellow-500/30 bg-yellow-500/5"
                            : "border-border bg-white/5"
                        }`}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <p className="text-sm font-medium text-text-primary">
                            {obligation.titulo}
                          </p>
                          {isUrgent && (
                            <AlertTriangle className="w-4 h-4 text-yellow-400 shrink-0" />
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-text-muted">
                          <Calendar className="w-3 h-3" />
                          <span>
                            {new Date(obligation.dataVencimento).toLocaleDateString("pt-BR")}
                          </span>
                          <span className={isUrgent ? "text-yellow-400" : ""}>
                            ({daysUntil} dias)
                          </span>
                        </div>
                        <Badge variant="outline" className="mt-2 text-xs">
                          {obligation.tipo.charAt(0).toUpperCase() + obligation.tipo.slice(1)}
                        </Badge>
                      </motion.div>
                    );
                  })
                )}
              </div>
            </ScrollArea>

            <div className="p-4 border-t border-border">
              <Button variant="ghost" size="sm" className="w-full text-text-muted hover:text-text-primary">
                Ver calendário completo
                <ChevronRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
