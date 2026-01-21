"use client";

import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Command,
  Search,
  Bell,
  MessageSquare,
  ChevronDown,
  User,
  Settings,
  LogOut,
  Loader2,
} from "lucide-react";
import { getInitials } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";

/**
 * Header - Top header bar for Faiston One
 *
 * Features:
 * - Search trigger (opens Command Palette)
 * - Notifications
 * - User profile with dropdown menu
 * - Sign out functionality
 */

interface HeaderProps {
  onOpenCommandPalette?: () => void;
}

export function Header({ onOpenCommandPalette }: HeaderProps) {
  const router = useRouter();
  const { user, isLoading, isAuthenticated, signOut } = useAuth();

  const userName = user?.name || user?.email?.split("@")[0] || "Usuário";
  const initials = getInitials(userName);

  // Handler para signout
  const handleSignOut = () => {
    signOut();
    router.push("/login");
  };

  return (
    <header
      className={cn(
        "sticky top-0 z-30",
        "h-16 px-6",
        "flex items-center justify-between gap-4",
        "bg-faiston-bg/80 backdrop-blur-md",
        "border-b border-border"
      )}
    >
      {/* Left section - Search */}
      <div className="flex items-center">
        {/* Search Trigger */}
        <Button
          variant="outline"
          onClick={onOpenCommandPalette}
          className={cn(
            "w-64 justify-start gap-2",
            "bg-white/5 border-border hover:bg-white/10",
            "text-text-muted hover:text-text-secondary",
            "transition-all duration-150"
          )}
        >
          <Search className="w-4 h-4" />
          <span className="flex-1 text-left text-sm">Buscar...</span>
          <kbd className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 text-xs font-mono bg-white/10 rounded">
            <Command className="w-3 h-3" />K
          </kbd>
        </Button>
      </div>

      {/* Right section - Actions & Profile */}
      <div className="flex items-center gap-2">
        {/* Notifications */}
        <Button
          variant="ghost"
          size="icon"
          className="relative text-text-secondary hover:text-text-primary hover:bg-white/5"
        >
          <Bell className="w-5 h-5" />
          <Badge
            className="absolute -top-1 -right-1 h-5 w-5 p-0 flex items-center justify-center bg-accent-warning text-white text-xs"
          >
            3
          </Badge>
        </Button>

        {/* Messages */}
        <Button
          variant="ghost"
          size="icon"
          className="relative text-text-secondary hover:text-text-primary hover:bg-white/5"
        >
          <MessageSquare className="w-5 h-5" />
          <Badge
            className="absolute -top-1 -right-1 h-5 w-5 p-0 flex items-center justify-center bg-accent-primary text-white text-xs"
          >
            5
          </Badge>
        </Button>

        {/* Divider */}
        <div className="w-px h-8 bg-border mx-2" />

        {/* User Profile Dropdown */}
        {isLoading ? (
          <div className="flex items-center gap-2 px-2">
            <Loader2 className="w-5 h-5 animate-spin text-text-muted" />
          </div>
        ) : isAuthenticated ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className="flex items-center gap-3 px-2 hover:bg-white/5"
              >
                <Avatar className="h-8 w-8">
                  <AvatarImage src={undefined} alt={userName} />
                  <AvatarFallback className="bg-gradient-to-br from-blue-mid to-magenta-mid text-white text-sm">
                    {initials}
                  </AvatarFallback>
                </Avatar>
                <div className="hidden lg:block text-left">
                  <p className="text-sm font-medium text-text-primary">{userName}</p>
                  <p className="text-xs text-text-muted">{user?.email}</p>
                </div>
                <ChevronDown className="w-4 h-4 text-text-muted hidden lg:block" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-medium">{userName}</p>
                  <p className="text-xs text-text-muted">{user?.email}</p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => router.push("/perfil")}
                className="cursor-pointer"
              >
                <User className="mr-2 h-4 w-4" />
                <span>Meu Perfil</span>
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => router.push("/configuracoes")}
                className="cursor-pointer"
              >
                <Settings className="mr-2 h-4 w-4" />
                <span>Configurações</span>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={handleSignOut}
                className="cursor-pointer text-accent-warning focus:text-accent-warning"
              >
                <LogOut className="mr-2 h-4 w-4" />
                <span>Sair</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <Button
            variant="ghost"
            onClick={() => router.push("/login")}
            className="text-text-secondary hover:text-text-primary"
          >
            Entrar
          </Button>
        )}
      </div>
    </header>
  );
}

export default Header;
