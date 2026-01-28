// =============================================================================
// useProjects Hook - SGA Inventory Module
// =============================================================================
// Project/client management with CRUD operations.
// =============================================================================


import { useMemo, useCallback, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useAssetManagement } from '@/contexts/ativos';
import { createProject } from '@/services/sgaAgentcore';
import type { SGAProject } from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface UseProjectsReturn {
  // Data
  projects: SGAProject[];
  isLoading: boolean;
  error: string | null;

  // Search/filter
  searchTerm: string;
  setSearchTerm: (term: string) => void;
  filteredProjects: SGAProject[];

  // Filtered projects
  activeProjects: SGAProject[];

  // Lookup
  getProjectById: (id: string) => SGAProject | undefined;
  getProjectByCode: (code: string) => SGAProject | undefined;

  // Mutations
  createNewProject: {
    mutate: (params: Omit<SGAProject, 'id' | 'created_at' | 'updated_at'>) => void;
    mutateAsync: (params: Omit<SGAProject, 'id' | 'created_at' | 'updated_at'>) => Promise<SGAProject>;
    isPending: boolean;
    isError: boolean;
    error: Error | null;
  };

  // Actions
  refresh: () => Promise<void>;
}

// =============================================================================
// Hook
// =============================================================================

export function useProjects(): UseProjectsReturn {
  const {
    projects,
    masterDataLoading,
    masterDataError,
    refreshMasterData,
    getProjectById,
  } = useAssetManagement();

  // Local search state
  const [searchTerm, setSearchTerm] = useState('');

  // Filtered by search
  const filteredProjects = useMemo(() => {
    if (!searchTerm) return projects;
    const term = searchTerm.toLowerCase();
    return projects.filter(
      proj =>
        proj.code.toLowerCase().includes(term) ||
        proj.name.toLowerCase().includes(term) ||
        proj.client_name.toLowerCase().includes(term)
    );
  }, [projects, searchTerm]);

  // Filtered lists
  const activeProjects = useMemo(
    () => projects.filter(proj => proj.is_active),
    [projects]
  );

  // Lookup by code
  const getProjectByCode = useCallback(
    (code: string) => projects.find(proj => proj.code === code),
    [projects]
  );

  // Create project mutation
  const createProjectMutation = useMutation({
    mutationFn: async (params: Omit<SGAProject, 'id' | 'created_at' | 'updated_at'>) => {
      const result = await createProject(params);
      return result.data.project;
    },
    onSuccess: () => {
      refreshMasterData();
    },
  });

  return {
    projects,
    isLoading: masterDataLoading,
    error: masterDataError,
    searchTerm,
    setSearchTerm,
    filteredProjects,
    activeProjects,
    getProjectById,
    getProjectByCode,
    createNewProject: {
      mutate: createProjectMutation.mutate,
      mutateAsync: createProjectMutation.mutateAsync,
      isPending: createProjectMutation.isPending,
      isError: createProjectMutation.isError,
      error: createProjectMutation.error,
    },
    refresh: refreshMasterData,
  };
}

// Re-export types
export type { SGAProject };
