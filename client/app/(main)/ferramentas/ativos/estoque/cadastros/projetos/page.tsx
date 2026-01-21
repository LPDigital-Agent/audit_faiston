'use client';

// =============================================================================
// Projects Page - SGA Inventory Module
// =============================================================================
// Project/client management.
// =============================================================================

import { useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
} from '@/components/shared/glass-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import {
  Briefcase,
  ArrowLeft,
  Search,
  Plus,
  RefreshCw,
  ChevronRight,
  Building2,
  Check,
  X,
} from 'lucide-react';
import { useProjects } from '@/hooks/ativos';

// =============================================================================
// Page Component
// =============================================================================

export default function ProjectsPage() {
  const {
    filteredProjects,
    searchTerm,
    setSearchTerm,
    isLoading,
    activeProjects,
    refresh,
  } = useProjects();

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/ferramentas/ativos/estoque/cadastros">
                <ArrowLeft className="w-4 h-4 mr-1" />
                Cadastros
              </Link>
            </Button>
          </div>
          <h1 className="text-xl font-semibold text-text-primary">
            Projetos
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Clientes e contratos ativos
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refresh()}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Atualizar
          </Button>
          <Button>
            <Plus className="w-4 h-4 mr-2" />
            Novo Projeto
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <GlassCard className="p-4">
          <p className="text-2xl font-bold text-text-primary">
            {isLoading ? '...' : filteredProjects.length}
          </p>
          <p className="text-xs text-text-muted">Total de Projetos</p>
        </GlassCard>
        <GlassCard className="p-4">
          <div className="flex items-center gap-2">
            <Check className="w-5 h-5 text-green-400" />
            <p className="text-2xl font-bold text-green-400">
              {isLoading ? '...' : activeProjects.length}
            </p>
          </div>
          <p className="text-xs text-text-muted">Ativos</p>
        </GlassCard>
        <GlassCard className="p-4">
          <div className="flex items-center gap-2">
            <X className="w-5 h-5 text-red-400" />
            <p className="text-2xl font-bold text-red-400">
              {isLoading ? '...' : (filteredProjects.length - activeProjects.length)}
            </p>
          </div>
          <p className="text-xs text-text-muted">Inativos</p>
        </GlassCard>
      </div>

      {/* Search */}
      <GlassCard className="p-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <Input
            placeholder="Buscar por código, nome ou cliente..."
            className="pl-10 bg-white/5 border-border"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </GlassCard>

      {/* Projects List */}
      <GlassCard>
        <GlassCardHeader>
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <Briefcase className="w-4 h-4 text-magenta-mid" />
              <GlassCardTitle>Projetos</GlassCardTitle>
            </div>
            <Badge variant="outline">{filteredProjects.length} registros</Badge>
          </div>
        </GlassCardHeader>

        {/* Table Header */}
        <div className="hidden md:grid grid-cols-12 gap-4 px-4 py-3 border-b border-border text-xs font-medium text-text-muted uppercase tracking-wider">
          <div className="col-span-2">Código</div>
          <div className="col-span-4">Nome</div>
          <div className="col-span-3">Cliente</div>
          <div className="col-span-2">Status</div>
          <div className="col-span-1 text-right">Ações</div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-8 h-8 text-text-muted animate-spin" />
          </div>
        ) : filteredProjects.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Briefcase className="w-12 h-12 text-text-muted mb-3" />
            <p className="text-sm text-text-muted">
              {searchTerm
                ? 'Nenhum projeto encontrado'
                : 'Nenhum projeto cadastrado'}
            </p>
          </div>
        ) : (
          <ScrollArea className="max-h-[500px]">
            <div className="divide-y divide-border">
              {filteredProjects.map((project, index) => (
                <motion.div
                  key={project.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.02 }}
                  className="grid grid-cols-1 md:grid-cols-12 gap-4 px-4 py-4 hover:bg-white/5 transition-colors cursor-pointer items-center"
                >
                  <div className="col-span-2 flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-magenta-dark/20 flex items-center justify-center shrink-0">
                      <Briefcase className="w-5 h-5 text-magenta-mid" />
                    </div>
                    <p className="text-sm font-medium text-text-primary font-mono">
                      {project.code}
                    </p>
                  </div>

                  <div className="col-span-4">
                    <p className="text-sm text-text-primary truncate">
                      {project.name}
                    </p>
                  </div>

                  <div className="col-span-3 flex items-center gap-2">
                    <Building2 className="w-4 h-4 text-text-muted" />
                    <p className="text-sm text-text-muted truncate">
                      {project.client_name}
                    </p>
                  </div>

                  <div className="col-span-2">
                    {project.is_active ? (
                      <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                        <Check className="w-3 h-3 mr-1" />
                        Ativo
                      </Badge>
                    ) : (
                      <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
                        <X className="w-3 h-3 mr-1" />
                        Inativo
                      </Badge>
                    )}
                  </div>

                  <div className="col-span-1 flex items-center justify-end">
                    <ChevronRight className="w-4 h-4 text-text-muted" />
                  </div>
                </motion.div>
              ))}
            </div>
          </ScrollArea>
        )}
      </GlassCard>
    </div>
  );
}
