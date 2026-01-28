// =============================================================================
// Academy AgentCore Service - Faiston Academy
// =============================================================================
// Purpose: Invoke AWS Bedrock AgentCore Runtime directly from the React SPA
// using JWT Bearer Token authentication.
//
// This service handles all AI features for Faiston Academy:
// - NEXO AI Chat (renamed from Sasha)
// - Flashcards generation
// - MindMap generation
// - Audio Class generation (ElevenLabs TTS)
// - Video Class generation
// - Slide Deck generation
// - Extra Class generation (HeyGen)
// - Reflection analysis
// - YouTube search
//
// Configuration: See @/lib/config/agentcore.ts for ARN configuration
// =============================================================================

import { ACADEMY_AGENTCORE_ARN } from '@/lib/config/agentcore';
import { ACADEMY_STORAGE_KEYS } from '@/lib/academy/constants';
import {
  createAgentCoreService,
  type AgentCoreRequest,
  type AgentCoreResponse,
  type InvokeOptions,
} from './agentcoreBase';
import type {
  FlashcardsRequest,
  FlashcardsResponse,
  MindMapRequest,
  MindMapResponse,
  NexoChatRequest,
  NexoChatResponse,
  ReflectionRequest,
  ReflectionResponse,
  AudioClassRequest,
  AudioClassResponse,
  YouTubeSearchRequest,
  YouTubeSearchResponse,
  VideoClassRequest,
  VideoClassResponse,
  SlideDeckRequest,
  SlideDeckResponse,
  SlideDeckPlanRequest,
  SlideDeckPlanResponse,
  SlideBatchRequest,
  SlideBatchResponse,
  ValidateDoubtRequest,
  ValidateDoubtResponse,
  GenerateExtraClassRequest,
  GenerateExtraClassResponse,
  CheckExtraClassStatusRequest,
  CheckExtraClassStatusResponse,
} from '@/lib/academy/types';

// =============================================================================
// Service Instance
// =============================================================================

const academyService = createAgentCoreService({
  arn: ACADEMY_AGENTCORE_ARN,
  sessionStorageKey: ACADEMY_STORAGE_KEYS.AGENTCORE_SESSION,
  logPrefix: '[Academy AgentCore]',
  sessionPrefix: 'session',
});

// =============================================================================
// Re-export Types
// =============================================================================

export type { AgentCoreRequest, AgentCoreResponse, InvokeOptions };

// =============================================================================
// Core Functions (delegated to base service)
// =============================================================================

export const invokeAgentCore = academyService.invoke;
export const getSessionId = academyService.getSessionId;
export const clearSession = academyService.clearSession;
export const getAgentCoreConfig = academyService.getConfig;

// =============================================================================
// NEXO AI Chat (renamed from Sasha)
// =============================================================================

export async function nexoChat(
  params: NexoChatRequest
): Promise<AgentCoreResponse<NexoChatResponse>> {
  return invokeAgentCore<NexoChatResponse>({
    action: 'nexo_chat',
    question: params.question,
    transcription: params.transcription,
    episode_title: params.episode_title || '',
    conversation_history: params.conversation_history || [],
  });
}

// =============================================================================
// Flashcards
// =============================================================================

export async function generateFlashcards(
  params: FlashcardsRequest
): Promise<AgentCoreResponse<FlashcardsResponse>> {
  return invokeAgentCore<FlashcardsResponse>({
    action: 'generate_flashcards',
    transcription: params.transcription,
    difficulty: params.difficulty || 'medium',
    num_cards: params.count || 10,
    custom_prompt: params.custom_prompt || '',
  });
}

// =============================================================================
// MindMap
// =============================================================================

export async function generateMindMap(
  params: MindMapRequest
): Promise<AgentCoreResponse<MindMapResponse>> {
  return invokeAgentCore<MindMapResponse>({
    action: 'generate_mindmap',
    transcription: params.transcription,
    episode_title: params.episode_title || 'Aula',
  });
}

// =============================================================================
// Reflection
// =============================================================================

export async function analyzeReflection(
  params: ReflectionRequest
): Promise<AgentCoreResponse<ReflectionResponse>> {
  return invokeAgentCore<ReflectionResponse>({
    action: 'analyze_reflection',
    student_explanation: params.reflection,
    transcription: params.transcription,
    episode_title: '',
  });
}

// =============================================================================
// Audio Class
// =============================================================================

export async function generateAudioClass(
  params: AudioClassRequest,
  signal?: AbortSignal
): Promise<AgentCoreResponse<AudioClassResponse>> {
  return invokeAgentCore<AudioClassResponse>(
    {
      action: 'generate_audio_class',
      transcription: params.transcription,
      mode: params.mode || 'deep_explanation',
      student_name: params.student_name || 'Estudante',
      custom_prompt: params.custom_prompt || undefined,
      male_voice_id: params.male_voice_id,
      female_voice_id: params.female_voice_id,
      male_voice_name: params.male_voice_name,
      female_voice_name: params.female_voice_name,
    },
    { signal }
  );
}

// =============================================================================
// YouTube Search
// =============================================================================

export async function searchYouTube(
  params: YouTubeSearchRequest
): Promise<AgentCoreResponse<YouTubeSearchResponse>> {
  return invokeAgentCore<YouTubeSearchResponse>({
    action: 'search_youtube',
    transcription: params.transcription,
    episode_title: params.episode_title || 'Aula',
    category: params.category || 'Educacao',
  });
}

// =============================================================================
// Video Class
// =============================================================================

export async function generateVideoClass(
  params: VideoClassRequest,
  signal?: AbortSignal
): Promise<AgentCoreResponse<VideoClassResponse>> {
  return invokeAgentCore<VideoClassResponse>(
    {
      action: 'generate_video_class',
      transcription: params.transcription,
      format: params.format,
      visual_theme: params.visual_theme,
      custom_prompt: params.custom_prompt || '',
      episode_id: params.episode_id,
    },
    { signal }
  );
}

// =============================================================================
// Slide Deck
// =============================================================================

export async function generateSlideDeck(
  params: SlideDeckRequest
): Promise<AgentCoreResponse<SlideDeckResponse>> {
  return invokeAgentCore<SlideDeckResponse>({
    action: 'generate_slidedeck',
    transcription: params.transcription,
    episode_title: params.episode_title || 'Aula',
    episode_id: params.episode_id || 'unknown',
  });
}

export async function planSlideDeck(
  params: SlideDeckPlanRequest
): Promise<AgentCoreResponse<SlideDeckPlanResponse>> {
  return invokeAgentCore<SlideDeckPlanResponse>({
    action: 'slidedeck_plan',
    transcription: params.transcription,
    episode_title: params.episode_title || 'Aula',
    archetype: params.archetype || 'deep_dive',
  });
}

export async function generateSlideBatch(
  params: SlideBatchRequest,
  signal?: AbortSignal
): Promise<AgentCoreResponse<SlideBatchResponse>> {
  return invokeAgentCore<SlideBatchResponse>(
    {
      action: 'slidedeck_batch',
      batch_type: params.batch_type,
      episode_title: params.episode_title,
      episode_id: params.episode_id,
      concepts: params.concepts || [],
      concept_indices: params.concept_indices || [],
      slide_indices: params.slide_indices,
      style: params.style || 'corporate',
      generation_id: params.generation_id,
    },
    { signal }
  );
}

export interface GenerationProgress {
  phase: 'planning' | 'generating' | 'complete';
  current: number;
  total: number;
  message: string;
}

export async function generateSlideDeckV4(
  params: SlideDeckRequest,
  onProgress?: (progress: GenerationProgress) => void
): Promise<SlideDeckResponse> {
  const episodeId = params.episode_id || 'unknown';
  const episodeTitle = params.episode_title || 'Aula';

  // PHASE 1: Create plan
  onProgress?.({
    phase: 'planning',
    current: 0,
    total: 1,
    message: 'Analisando conteudo...',
  });

  const { data: plan } = await planSlideDeck({
    transcription: params.transcription,
    episode_title: episodeTitle,
    archetype: params.archetype,
  });

  if (!plan || !plan.batches || !Array.isArray(plan.batches)) {
    throw new Error(
      (plan as { error?: string })?.error ||
        'Falha ao criar plano de slides. Por favor, tente novamente.'
    );
  }

  const totalBatches = plan.batches.length;
  onProgress?.({
    phase: 'generating',
    current: 0,
    total: totalBatches,
    message: `Gerando ${plan.total_slides} slides em ${totalBatches} lotes...`,
  });

  // PHASE 2: Generate batches in parallel
  const generationId = plan.generation_id;
  let completedBatches = 0;

  const batchPromises = plan.batches.map(async (batch) => {
    const result = await generateSlideBatch({
      batch_type: batch.slide_type,
      episode_title: episodeTitle,
      episode_id: episodeId,
      concepts: plan.concepts,
      concept_indices: batch.concept_indices,
      slide_indices: batch.slide_indices,
      style: 'corporate',
      generation_id: generationId,
    });

    completedBatches++;
    onProgress?.({
      phase: 'generating',
      current: completedBatches,
      total: totalBatches,
      message: `Lote ${completedBatches}/${totalBatches} concluido`,
    });

    return result;
  });

  const batchResults = await Promise.all(batchPromises);

  // PHASE 3: Aggregate results
  const allSlides = batchResults
    .flatMap(r => r.data.slides)
    .sort((a, b) => a.index - b.index)
    .map(slide => ({
      id: slide.id,
      title: slide.title,
      image_url: slide.image_url,
      speaker_notes: slide.speaker_notes,
    }));

  onProgress?.({
    phase: 'complete',
    current: totalBatches,
    total: totalBatches,
    message: 'Slide deck concluido!',
  });

  return {
    deck_title: plan.deck_title,
    slides: allSlides,
    generatedAt: new Date().toISOString(),
    model: 'gemini-3-pro + imagen-3',
  };
}

// =============================================================================
// Extra Class (HeyGen)
// =============================================================================

/**
 * Validate if a student's doubt relates to the transcription content.
 */
export async function validateDoubt(
  params: ValidateDoubtRequest
): Promise<AgentCoreResponse<ValidateDoubtResponse>> {
  return invokeAgentCore<ValidateDoubtResponse>({
    action: 'validate_doubt',
    transcription: params.transcription,
    doubt: params.doubt,
  });
}

/**
 * Generate personalized extra class video with HeyGen.
 */
export async function generateExtraClass(
  params: GenerateExtraClassRequest,
  signal?: AbortSignal
): Promise<AgentCoreResponse<GenerateExtraClassResponse>> {
  return invokeAgentCore<GenerateExtraClassResponse>(
    {
      action: 'generate_extra_class',
      transcription: params.transcription,
      doubt: params.doubt,
      episode_id: params.episode_id,
      student_name: params.student_name,
    },
    { signal }
  );
}

/**
 * Check the status of a HeyGen video generation.
 */
export async function checkExtraClassStatus(
  params: CheckExtraClassStatusRequest
): Promise<AgentCoreResponse<CheckExtraClassStatusResponse>> {
  return invokeAgentCore<CheckExtraClassStatusResponse>({
    action: 'check_extra_class_status',
    video_id: params.video_id,
  });
}
