'use client';

// =============================================================================
// Mobile Checklist - SGA Inventory PWA Component
// =============================================================================
// Touch-friendly checklist for picking, counting, and verification tasks.
// Designed for warehouse workers using tablets and phones.
// =============================================================================

import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CheckCircle2,
  Circle,
  MapPin,
  ChevronRight,
  AlertTriangle,
  Camera,
  Check,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';

// =============================================================================
// Types
// =============================================================================

export interface ChecklistItem {
  id: string;
  partNumber: string;
  description: string;
  locationCode: string;
  locationName: string;
  quantity: number;
  quantityChecked?: number;
  status: 'pending' | 'in_progress' | 'completed' | 'issue';
  notes?: string;
  serialNumbers?: string[];
}

interface MobileChecklistProps {
  title: string;
  subtitle?: string;
  items: ChecklistItem[];
  onItemCheck: (itemId: string, checked: number, serials?: string[]) => void;
  onItemIssue?: (itemId: string, issue: string) => void;
  onComplete?: () => void;
  showProgress?: boolean;
  requireSerials?: boolean;
  className?: string;
}

// =============================================================================
// Component
// =============================================================================

export function MobileChecklist({
  title,
  subtitle,
  items,
  onItemCheck,
  onItemIssue,
  onComplete,
  showProgress = true,
  requireSerials = false,
  className = '',
}: MobileChecklistProps) {
  const [expandedItem, setExpandedItem] = useState<string | null>(null);
  const [tempQuantity, setTempQuantity] = useState<Record<string, number>>({});

  // Calculate progress
  const totalItems = items.length;
  const completedItems = items.filter((i) => i.status === 'completed').length;
  const progressPercent = totalItems > 0 ? (completedItems / totalItems) * 100 : 0;

  // Toggle item expansion
  const toggleExpand = useCallback((itemId: string) => {
    setExpandedItem((prev) => (prev === itemId ? null : itemId));
  }, []);

  // Handle quantity change
  const handleQuantityChange = useCallback(
    (itemId: string, delta: number) => {
      const item = items.find((i) => i.id === itemId);
      if (!item) return;

      const current = tempQuantity[itemId] ?? item.quantityChecked ?? 0;
      const newValue = Math.max(0, Math.min(item.quantity, current + delta));
      setTempQuantity((prev) => ({ ...prev, [itemId]: newValue }));
    },
    [items, tempQuantity]
  );

  // Handle item confirmation
  const handleConfirm = useCallback(
    (itemId: string) => {
      const item = items.find((i) => i.id === itemId);
      if (!item) return;

      const quantity = tempQuantity[itemId] ?? item.quantity;
      onItemCheck(itemId, quantity);
      setExpandedItem(null);
      setTempQuantity((prev) => {
        const newState = { ...prev };
        delete newState[itemId];
        return newState;
      });
    },
    [items, tempQuantity, onItemCheck]
  );

  // Handle issue report
  const handleIssue = useCallback(
    (itemId: string) => {
      if (onItemIssue) {
        onItemIssue(itemId, 'Item com problema');
      }
      setExpandedItem(null);
    },
    [onItemIssue]
  );

  // Get status color
  const getStatusColor = (status: ChecklistItem['status']) => {
    switch (status) {
      case 'completed':
        return 'text-green-400';
      case 'in_progress':
        return 'text-blue-400';
      case 'issue':
        return 'text-red-400';
      default:
        return 'text-text-muted';
    }
  };

  // Get status icon
  const getStatusIcon = (status: ChecklistItem['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-6 h-6 text-green-400" />;
      case 'issue':
        return <AlertTriangle className="w-6 h-6 text-red-400" />;
      default:
        return <Circle className="w-6 h-6 text-text-muted" />;
    }
  };

  return (
    <div className={`bg-background rounded-xl border border-border ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-text-primary">{title}</h3>
            {subtitle && (
              <p className="text-xs text-text-muted mt-0.5">{subtitle}</p>
            )}
          </div>
          <Badge variant="outline">
            {completedItems}/{totalItems}
          </Badge>
        </div>

        {/* Progress bar */}
        {showProgress && (
          <div className="mt-3">
            <Progress value={progressPercent} className="h-2" />
            <p className="text-xs text-text-muted mt-1">
              {progressPercent.toFixed(0)}% concluido
            </p>
          </div>
        )}
      </div>

      {/* Items List */}
      <div className="divide-y divide-border">
        {items.map((item) => {
          const isExpanded = expandedItem === item.id;
          const currentQuantity = tempQuantity[item.id] ?? item.quantityChecked ?? 0;

          return (
            <motion.div
              key={item.id}
              layout
              className={`${
                item.status === 'completed' ? 'bg-green-500/5' : ''
              } ${item.status === 'issue' ? 'bg-red-500/5' : ''}`}
            >
              {/* Item Header - Always visible */}
              <button
                className="w-full flex items-center gap-4 p-4 text-left"
                onClick={() => toggleExpand(item.id)}
              >
                {getStatusIcon(item.status)}

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-text-primary truncate">
                      {item.partNumber}
                    </p>
                    <Badge variant="outline" className="text-xs shrink-0">
                      x{item.quantity}
                    </Badge>
                  </div>
                  <p className="text-xs text-text-muted truncate mt-0.5">
                    {item.description}
                  </p>
                  <div className="flex items-center gap-1 mt-1 text-xs text-text-muted">
                    <MapPin className="w-3 h-3" />
                    <span>
                      {item.locationCode} - {item.locationName}
                    </span>
                  </div>
                </div>

                <motion.div
                  animate={{ rotate: isExpanded ? 90 : 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <ChevronRight className={`w-5 h-5 ${getStatusColor(item.status)}`} />
                </motion.div>
              </button>

              {/* Expanded Content */}
              <AnimatePresence>
                {isExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="px-4 pb-4 space-y-4">
                      {/* Quantity Counter */}
                      <div className="flex items-center justify-center gap-4 p-4 bg-white/5 rounded-lg">
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-12 w-12 text-xl"
                          onClick={() => handleQuantityChange(item.id, -1)}
                          disabled={currentQuantity <= 0}
                        >
                          -
                        </Button>
                        <div className="text-center min-w-[80px]">
                          <p className="text-3xl font-bold text-text-primary">
                            {currentQuantity}
                          </p>
                          <p className="text-xs text-text-muted">de {item.quantity}</p>
                        </div>
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-12 w-12 text-xl"
                          onClick={() => handleQuantityChange(item.id, 1)}
                          disabled={currentQuantity >= item.quantity}
                        >
                          +
                        </Button>
                      </div>

                      {/* Quick Actions */}
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="flex-1"
                          onClick={() => setTempQuantity((prev) => ({ ...prev, [item.id]: item.quantity }))}
                        >
                          <Check className="w-4 h-4 mr-1" />
                          Qtd Total
                        </Button>
                        {requireSerials && (
                          <Button variant="outline" size="sm" className="flex-1">
                            <Camera className="w-4 h-4 mr-1" />
                            Escanear
                          </Button>
                        )}
                      </div>

                      {/* Action Buttons */}
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          className="flex-1"
                          onClick={() => handleIssue(item.id)}
                        >
                          <AlertTriangle className="w-4 h-4 mr-2" />
                          Problema
                        </Button>
                        <Button
                          className="flex-1 bg-gradient-to-r from-magenta-mid to-blue-mid"
                          onClick={() => handleConfirm(item.id)}
                          disabled={currentQuantity === 0}
                        >
                          <CheckCircle2 className="w-4 h-4 mr-2" />
                          Confirmar
                        </Button>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          );
        })}
      </div>

      {/* Footer */}
      {completedItems === totalItems && totalItems > 0 && onComplete && (
        <div className="p-4 border-t border-border">
          <Button
            className="w-full bg-green-500 hover:bg-green-600"
            onClick={onComplete}
          >
            <CheckCircle2 className="w-4 h-4 mr-2" />
            Finalizar Checklist
          </Button>
        </div>
      )}
    </div>
  );
}
