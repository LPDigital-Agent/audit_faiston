// =============================================================================
// useMindMap Hook - Faiston Academy
// =============================================================================
// Hook for mind map generation and visualization.
// Supports hierarchical node expansion/collapse.
// =============================================================================


import { useState, useEffect, useCallback, startTransition } from 'react';
import { useMutation } from '@tanstack/react-query';
import { generateMindMap } from '@/services/academyAgentcore';
import type { MindMapNode } from '@/lib/academy/types';
import { ACADEMY_STORAGE_KEYS } from '@/lib/academy/constants';

interface UseMindMapOptions {
  courseId: string;
  episodeId: string;
  episodeTitle?: string;
  onSeek?: (time: number) => void;
}

interface MindMapData {
  title: string;
  nodes: MindMapNode[];
  generatedAt: string;
  model?: string;
}

const getStorageKey = (courseId: string, episodeId: string) =>
  `${ACADEMY_STORAGE_KEYS.MINDMAP_PREFIX}${courseId}_${episodeId}`;

function collectAllNodeIds(nodes: MindMapNode[]): string[] {
  const ids: string[] = [];

  function traverse(node: MindMapNode) {
    ids.push(node.id);
    if (node.children) {
      node.children.forEach(traverse);
    }
  }

  nodes.forEach(traverse);
  return ids;
}

export function useMindMap({
  courseId,
  episodeId,
  episodeTitle = 'Aula',
  onSeek,
}: UseMindMapOptions) {
  const [mindMapData, setMindMapData] = useState<MindMapData | null>(null);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  // Load from localStorage on mount
  useEffect(() => {
    const storageKey = getStorageKey(courseId, episodeId);
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const parsed = JSON.parse(stored);
        startTransition(() => {
          if (parsed.data) {
            setMindMapData(parsed.data);
          }
          if (parsed.expanded && Array.isArray(parsed.expanded)) {
            setExpandedNodes(new Set(parsed.expanded));
          }
        });
      }
    } catch (e) {
      console.error('Failed to load mindmap:', e);
    }
  }, [courseId, episodeId]);

  // Save to localStorage when data changes
  useEffect(() => {
    if (mindMapData) {
      const storageKey = getStorageKey(courseId, episodeId);
      const data = {
        data: mindMapData,
        expanded: Array.from(expandedNodes),
      };
      try {
        localStorage.setItem(storageKey, JSON.stringify(data));
      } catch (e) {
        console.error('Failed to save mindmap:', e);
      }
    }
  }, [mindMapData, expandedNodes, courseId, episodeId]);

  // Toggle node expansion
  const toggleNode = useCallback((nodeId: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);

  // Generate mutation
  const generateMutation = useMutation({
    mutationFn: async (transcription: string): Promise<MindMapData> => {
      const { data } = await generateMindMap({
        transcription,
        episode_title: episodeTitle,
      });
      return data;
    },
    onSuccess: (data) => {
      setMindMapData(data);
      // Start with only root expanded
      setExpandedNodes(new Set(['root']));
    },
  });

  // Expand all nodes
  const expandAll = useCallback(() => {
    if (!mindMapData) return;
    const allIds = collectAllNodeIds(mindMapData.nodes);
    setExpandedNodes(new Set(['root', ...allIds]));
  }, [mindMapData]);

  // Collapse all nodes (only root visible)
  const collapseAll = useCallback(() => {
    setExpandedNodes(new Set(['root']));
  }, []);

  // Navigate to timestamp
  const navigateToTimestamp = useCallback(
    (timestamp: number) => {
      if (onSeek) {
        onSeek(timestamp);
      }
    },
    [onSeek]
  );

  // Reset mind map
  const resetMindMap = useCallback(() => {
    setMindMapData(null);
    setExpandedNodes(new Set());
    const storageKey = getStorageKey(courseId, episodeId);
    try {
      localStorage.removeItem(storageKey);
    } catch (e) {
      console.error('Failed to reset mindmap:', e);
    }
  }, [courseId, episodeId]);

  return {
    // Data
    mindMapData,
    expandedNodes,

    // Actions
    generate: generateMutation.mutate,
    toggleNode,
    expandAll,
    collapseAll,
    navigateToTimestamp,
    resetMindMap,

    // Mutation state
    isGenerating: generateMutation.isPending,
    generateError: generateMutation.error,

    // Helpers
    hasMindMap: mindMapData !== null,
  };
}

// Re-export types for convenience
export type { MindMapNode } from '@/lib/academy/types';
