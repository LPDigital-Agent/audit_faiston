"use client";

import { useEffect, useCallback } from "react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import {
  LayoutDashboard,
  Newspaper,
  Calendar,
  MessageSquare,
  Settings,
  HelpCircle,
  Search,
  User,
  FileText,
  Plus,
  Send,
  Sparkles,
} from "lucide-react";
import { useRouter } from "next/navigation";

/**
 * CommandPalette - Universal search and action palette
 *
 * Triggered by Cmd+K / Ctrl+K
 * Features:
 * - Fuzzy search
 * - Navigation shortcuts
 * - Quick actions
 * - NEXO AI integration (future)
 */

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Navigation items
const navigationItems = [
  { label: "Dashboard", icon: LayoutDashboard, href: "/" },
  { label: "Notícias", icon: Newspaper, href: "/noticias" },
  { label: "Calendário", icon: Calendar, href: "/calendario" },
  { label: "Teams", icon: MessageSquare, href: "/teams" },
  { label: "Configurações", icon: Settings, href: "/configuracoes" },
  { label: "Ajuda", icon: HelpCircle, href: "/ajuda" },
];

// Quick actions
const quickActions = [
  { label: "Agendar reunião", icon: Plus, action: "schedule-meeting" },
  { label: "Enviar mensagem", icon: Send, action: "send-message" },
  { label: "Buscar documento", icon: FileText, action: "search-document" },
  { label: "Perguntar ao NEXO", icon: Sparkles, action: "ask-nexo" },
];

// Mock people for search
const people = [
  { name: "Maria Silva", email: "maria@faiston.com", role: "Product Manager" },
  { name: "João Costa", email: "joao@faiston.com", role: "Developer" },
  { name: "Ana Oliveira", email: "ana@faiston.com", role: "Designer" },
  { name: "Carlos Mendes", email: "carlos@faiston.com", role: "Tech Lead" },
];

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const router = useRouter();

  // Global keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        onOpenChange(!open);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onOpenChange]);

  const handleSelect = useCallback(
    (value: string) => {
      onOpenChange(false);

      // Handle navigation
      const navItem = navigationItems.find((item) => item.href === value);
      if (navItem) {
        router.push(navItem.href);
        return;
      }

      // Handle actions (future implementation)
      const action = quickActions.find((item) => item.action === value);
      if (action) {
        console.log("Action triggered:", action.action);
        // TODO: Implement action handlers
        return;
      }

      // Handle people (future implementation)
      const person = people.find((p) => p.email === value);
      if (person) {
        console.log("Selected person:", person.name);
        // TODO: Open chat or profile
      }
    },
    [router, onOpenChange]
  );

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput
        placeholder="Buscar ou perguntar ao NEXO..."
        className="border-none focus:ring-0"
      />
      <CommandList>
        <CommandEmpty>
          <div className="flex flex-col items-center gap-2 py-6">
            <Search className="w-10 h-10 text-text-muted" />
            <p className="text-sm text-text-muted">Nenhum resultado encontrado</p>
            <p className="text-xs text-text-muted">
              Tente buscar por páginas, ações ou pessoas
            </p>
          </div>
        </CommandEmpty>

        {/* NEXO AI */}
        <CommandGroup heading="NEXO AI">
          <CommandItem
            value="ask-nexo"
            onSelect={handleSelect}
            className="flex items-center gap-3"
          >
            <div className="w-8 h-8 rounded-lg gradient-nexo flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <div>
              <p className="text-sm font-medium">Perguntar ao NEXO</p>
              <p className="text-xs text-text-muted">
                Use IA para encontrar respostas
              </p>
            </div>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {/* Navigation */}
        <CommandGroup heading="Navegação">
          {navigationItems.map((item) => (
            <CommandItem
              key={item.href}
              value={item.href}
              onSelect={handleSelect}
              className="flex items-center gap-3"
            >
              <item.icon className="w-4 h-4 text-text-muted" />
              <span>{item.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        {/* Quick Actions */}
        <CommandGroup heading="Ações Rápidas">
          {quickActions.slice(0, 3).map((action) => (
            <CommandItem
              key={action.action}
              value={action.action}
              onSelect={handleSelect}
              className="flex items-center gap-3"
            >
              <action.icon className="w-4 h-4 text-text-muted" />
              <span>{action.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        {/* People */}
        <CommandGroup heading="Pessoas">
          {people.map((person) => (
            <CommandItem
              key={person.email}
              value={person.email}
              onSelect={handleSelect}
              className="flex items-center gap-3"
            >
              <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
                <User className="w-4 h-4 text-text-muted" />
              </div>
              <div>
                <p className="text-sm font-medium">{person.name}</p>
                <p className="text-xs text-text-muted">{person.role}</p>
              </div>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}

export default CommandPalette;
