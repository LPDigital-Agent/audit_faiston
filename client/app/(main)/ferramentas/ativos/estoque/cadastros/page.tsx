'use client';

// =============================================================================
// Cadastros Page - SGA Inventory Module
// =============================================================================
// Master data management: Part Numbers, Locations, Projects.
// =============================================================================

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
import {
  Package,
  MapPin,
  Briefcase,
  Plus,
  ChevronRight,
  Settings,
} from 'lucide-react';
import { useAssetManagement } from '@/hooks/ativos';

// =============================================================================
// Page Component
// =============================================================================

export default function CadastrosPage() {
  const { partNumbers, locations, projects, masterDataLoading } = useAssetManagement();

  const sections = [
    {
      title: 'Part Numbers',
      description: 'Catálogo de produtos e componentes',
      icon: Package,
      color: 'text-blue-light',
      bgColor: 'bg-blue-mid/20',
      href: '/ferramentas/ativos/estoque/cadastros/part-numbers',
      count: partNumbers.length,
      stats: [
        { label: 'Ativos', value: partNumbers.filter(p => p.is_active).length },
        { label: 'Serializados', value: partNumbers.filter(p => p.is_serialized).length },
      ],
    },
    {
      title: 'Locais',
      description: 'Almoxarifados, clientes e pontos de entrega',
      icon: MapPin,
      color: 'text-green-400',
      bgColor: 'bg-green-500/20',
      href: '/ferramentas/ativos/estoque/cadastros/locais',
      count: locations.length,
      stats: [
        { label: 'Armazéns', value: locations.filter(l => l.type === 'WAREHOUSE').length },
        { label: 'Clientes', value: locations.filter(l => l.type === 'CUSTOMER').length },
      ],
    },
    {
      title: 'Projetos',
      description: 'Clientes e contratos ativos',
      icon: Briefcase,
      color: 'text-magenta-mid',
      bgColor: 'bg-magenta-dark/20',
      href: '/ferramentas/ativos/estoque/cadastros/projetos',
      count: projects.length,
      stats: [
        { label: 'Ativos', value: projects.filter(p => p.is_active).length },
      ],
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">
            Cadastros
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Gerenciamento de dados mestres do estoque
          </p>
        </div>
        <Button variant="outline">
          <Settings className="w-4 h-4 mr-2" />
          Configurações
        </Button>
      </div>

      {/* Sections Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {sections.map((section, index) => (
          <motion.div
            key={section.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
          >
            <Link href={section.href}>
              <GlassCard className="h-full hover:border-blue-mid/50 transition-colors cursor-pointer">
                <GlassCardHeader>
                  <div className="flex items-center justify-between w-full">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-lg ${section.bgColor}`}>
                        <section.icon className={`w-5 h-5 ${section.color}`} />
                      </div>
                      <div>
                        <GlassCardTitle>{section.title}</GlassCardTitle>
                        <p className="text-xs text-text-muted mt-0.5">
                          {section.description}
                        </p>
                      </div>
                    </div>
                    <ChevronRight className="w-5 h-5 text-text-muted" />
                  </div>
                </GlassCardHeader>

                <GlassCardContent>
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-3xl font-bold text-text-primary">
                      {masterDataLoading ? '...' : section.count}
                    </span>
                    <Badge variant="outline">Total</Badge>
                  </div>

                  <div className="flex gap-4">
                    {section.stats.map((stat) => (
                      <div key={stat.label} className="flex-1">
                        <p className="text-lg font-semibold text-text-primary">
                          {masterDataLoading ? '...' : stat.value}
                        </p>
                        <p className="text-xs text-text-muted">{stat.label}</p>
                      </div>
                    ))}
                  </div>
                </GlassCardContent>
              </GlassCard>
            </Link>
          </motion.div>
        ))}
      </div>

      {/* Quick Add Section */}
      <GlassCard>
        <GlassCardHeader>
          <div className="flex items-center gap-2">
            <Plus className="w-4 h-4 text-blue-light" />
            <GlassCardTitle>Cadastro Rápido</GlassCardTitle>
          </div>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="flex flex-wrap gap-3">
            <Button asChild>
              <Link href="/ferramentas/ativos/estoque/cadastros/part-numbers?new=true">
                <Package className="w-4 h-4 mr-2" />
                Novo Part Number
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/ferramentas/ativos/estoque/cadastros/locais?new=true">
                <MapPin className="w-4 h-4 mr-2" />
                Novo Local
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/ferramentas/ativos/estoque/cadastros/projetos?new=true">
                <Briefcase className="w-4 h-4 mr-2" />
                Novo Projeto
              </Link>
            </Button>
          </div>
        </GlassCardContent>
      </GlassCard>
    </div>
  );
}
