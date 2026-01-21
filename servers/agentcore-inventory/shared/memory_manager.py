"""
============================================================================
AgentMemoryManager - O "Hipocampo" do Nexo Mind (AWS-Native)
============================================================================
Sistema Nervoso que conecta todos os agentes ao AgentCore Memory.
USA SDK OFICIAL DA AWS - nao reinventa a roda!

LEIS GENETICAS APLICADAS:
- Lei 2 (Veritas): Toda memoria tem origin_type nos metadados
- Lei 4 (Ciclos): AWS EpisodicStrategy gera REFLECTIONS automaticamente!

ARQUITETURA:
- STM (CreateEvent) -> AWS consolida automaticamente -> LTM
- SemanticStrategy extrai FATOS
- EpisodicStrategy gera EPISODES + REFLECTIONS (Sleep Cycle automatico!)

NAMESPACES:
- /facts/{actorId}      - SemanticMemoryStrategy (fatos extraidos)
- /episodes/{actorId}   - EpisodicMemoryStrategy (episodios + reflections)
- /strategy/import/company - Global namespace para padroes de importacao

Usage:
    from shared.memory_manager import AgentMemoryManager, MemoryOriginType

    memory = AgentMemoryManager(agent_id="nexo_import", actor_id=user_id)

    # OBSERVE - Buscar conhecimento previo
    prior = await memory.observe("padroes de mapeamento para SERIAL")

    # LEARN - Gravar novo conhecimento
    await memory.learn_fact("Coluna SERIAL mapeia para serial_number", ...)

Architecture: AWS Bedrock AgentCore Memory + Strands Agents
============================================================================
"""

import os
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from shared.genesis_kernel import (
    MemoryOriginType,
    MemorySourceType,
    NexoMemoryMetadata,
    interpret_hebbian_weight,
)
from shared.xray_tracer import trace_memory_operation

# AUDIT-003: Global error capture for Debug Agent enrichment
from shared.debug_utils import debug_error

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

MEMORY_ID = os.environ.get(
    "AGENTCORE_MEMORY_ID",
    "nexo_sga_learning_memory-u3ypElEdl1"
)
MEMORY_REGION = os.environ.get("AWS_REGION", "us-east-2")

# Namespaces AWS-Native (definidos nas Memory Strategies)
NS_FACTS = "/facts/{actorId}"           # SemanticStrategy
NS_EPISODES = "/episodes/{actorId}"     # EpisodicStrategy
NS_GLOBAL = "/strategy/import/company"  # Global (all agents)


# ============================================================================
# MEMORY CLIENT SINGLETON
# ============================================================================

_memory_client = None


def _get_memory_client():
    """Lazy-load AgentCore Memory client (singleton)."""
    global _memory_client
    if _memory_client is None:
        try:
            from bedrock_agentcore.memory import MemoryClient
            _memory_client = MemoryClient(memory_id=MEMORY_ID)
            logger.info(f"[AgentMemoryManager] Memory client initialized: {MEMORY_ID}")
        except ImportError as e:
            logger.warning(f"[AgentMemoryManager] Memory SDK not available: {e}")
        except Exception as e:
            # AUDIT-003: Use debug_error for enriched error analysis
            debug_error(e, "memory_manager_init", {"memory_id": MEMORY_ID})
    return _memory_client


# ============================================================================
# AGENT MEMORY MANAGER
# ============================================================================

class AgentMemoryManager:
    """
    O "Hipocampo" do Nexo Mind - AWS-Native.

    CADA AGENTE instancia esta classe e:
    - ESCREVE eventos (STM) via create_event()
    - LE memorias (LTM) via retrieve_memory_records()

    AWS CUIDA DA CONSOLIDACAO:
    - SemanticStrategy -> extrai FATOS automaticamente
    - EpisodicStrategy -> gera EPISODES + REFLECTIONS automaticamente

    Example:
        memory = AgentMemoryManager(agent_id="nexo_import", actor_id="user-123")

        # Read prior knowledge
        facts = await memory.observe("column mapping patterns for SERIAL")

        # Write new knowledge (fact confirmed by human)
        await memory.learn_fact(
            fact="Column 'SERIAL' maps to 'serial_number'",
            category="column_mapping",
            session_id=session_id,
        )
    """

    def __init__(
        self,
        agent_id: str,
        actor_id: Optional[str] = None,
        use_global_namespace: bool = True,
    ):
        """
        Initialize AgentMemoryManager.

        Args:
            agent_id: ID do agente (nexo_import, data_import, etc)
            actor_id: ID do usuario/ator (para namespacing)
            use_global_namespace: Se True, usa namespace global para patterns
        """
        self.agent_id = agent_id
        self.actor_id = actor_id or "system"
        self.use_global_namespace = use_global_namespace
        self._client = None
        logger.info(
            f"[AgentMemoryManager] Initialized for agent={agent_id}, actor={actor_id}"
        )

    @property
    def client(self):
        """Get memory client (lazy loaded)."""
        if self._client is None:
            self._client = _get_memory_client()
        return self._client

    def _get_namespace(self, namespace_template: str) -> str:
        """Format namespace with actorId."""
        return namespace_template.format(actorId=self.actor_id)

    # ========================================================================
    # OBSERVE (Read from Memory)
    # ========================================================================

    @trace_memory_operation("observe")
    async def observe(
        self,
        query: str,
        limit: int = 10,
        include_facts: bool = True,
        include_episodes: bool = True,
        include_global: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        OBSERVE: Buscar memorias relevantes no LTM.

        AWS automatically extracts to LTM via Strategies, so we just query!

        Args:
            query: Busca semantica (natural language)
            limit: Maximo de resultados por namespace
            include_facts: Buscar no namespace /facts
            include_episodes: Buscar no namespace /episodes
            include_global: Buscar no namespace global

        Returns:
            Lista de memory records com content e metadata
        """
        if not self.client:
            logger.warning("[observe] Memory client not available")
            return []

        results = []
        namespaces_to_search = []

        if include_facts:
            namespaces_to_search.append(
                ("fact", self._get_namespace(NS_FACTS))
            )
        if include_episodes:
            namespaces_to_search.append(
                ("episode", self._get_namespace(NS_EPISODES))
            )
        if include_global:
            namespaces_to_search.append(
                ("global", NS_GLOBAL)
            )

        for memory_type, namespace in namespaces_to_search:
            try:
                records = await self.client.retrieve_memory_records(
                    query=query,
                    namespace=namespace,
                    top_k=limit,
                )
                for record in records:
                    results.append({
                        "type": memory_type,
                        "namespace": namespace,
                        **record,
                    })
            except Exception as e:
                logger.warning(
                    f"[observe] Error querying namespace {namespace}: {e}"
                )

        logger.info(
            f"[observe] Found {len(results)} memories for query: {query[:50]}..."
        )
        return results

    @trace_memory_operation("observe_facts")
    async def observe_facts(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        OBSERVE: Buscar APENAS fatos confirmados.

        Facts are extracted by SemanticMemoryStrategy from HIL interactions.
        """
        return await self.observe(
            query=query,
            limit=limit,
            include_facts=True,
            include_episodes=False,
            include_global=False,
        )

    @trace_memory_operation("observe_episodes")
    async def observe_episodes(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        OBSERVE: Buscar episodios e reflections.

        Episodes are captured by EpisodicMemoryStrategy.
        Reflections (insights) are auto-generated during consolidation!
        """
        return await self.observe(
            query=query,
            limit=limit,
            include_facts=False,
            include_episodes=True,
            include_global=False,
        )

    @trace_memory_operation("observe_global")
    async def observe_global(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        OBSERVE: Buscar no namespace global (company-wide patterns).

        Global patterns are shared across all users and agents.
        """
        return await self.observe(
            query=query,
            limit=limit,
            include_facts=False,
            include_episodes=False,
            include_global=True,
        )

    # ========================================================================
    # LEARN (Write to Memory)
    # ========================================================================

    @trace_memory_operation("learn")
    async def learn(
        self,
        content: str,
        category: str,
        origin_type: MemoryOriginType = MemoryOriginType.INFERENCE,
        source_type: MemorySourceType = MemorySourceType.AGENT_INFERENCE,
        emotional_weight: float = 0.5,
        confidence: float = 0.7,
        session_id: Optional[str] = None,
        event_type: str = "conversational",
        use_global: bool = False,
        tool_results: Optional[List[Dict]] = None,
        **extra_metadata,
    ) -> Optional[str]:
        """
        LEARN: Gravar evento no STM.

        AWS CUIDA DO RESTO:
        - SemanticStrategy extrai fatos automaticamente
        - EpisodicStrategy captura episodios + gera reflections

        Args:
            content: Conteudo da memoria (natural language)
            category: Categoria (column_mapping, import_pattern, etc)
            origin_type: Classificacao Veritas (FACT, INFERENCE, etc)
            source_type: Fonte da informacao
            emotional_weight: Peso Hebbian (0.0-1.0)
            confidence: Nivel de confianca (0.0-1.0)
            session_id: ID da sessao
            event_type: Tipo de evento para AgentCore
            use_global: Se True, usa namespace global
            tool_results: Resultados de tools (melhora EpisodicStrategy)

        Returns:
            Event ID or None if failed
        """
        if not self.client:
            logger.warning("[learn] Memory client not available")
            return None

        # Build NEXO metadata
        metadata = NexoMemoryMetadata(
            origin_agent=self.agent_id,
            actor_id=self.actor_id,
            session_id=session_id or f"{self.agent_id}-{datetime.utcnow().strftime('%Y%m%d')}",
            category=category,
            origin_type=origin_type,
            source_type=source_type,
            emotional_weight=emotional_weight,
            confidence_level=confidence,
        )

        # Build event data
        event_data = {
            "content": content,
            "role": "ASSISTANT",  # Required for AWS Strategy processing
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **metadata.to_dict(),
            **extra_metadata,
        }

        # Include tool results for better EpisodicStrategy extraction
        if tool_results:
            event_data["tool_results"] = tool_results

        # Determine namespace
        namespace = NS_GLOBAL if use_global else self._get_namespace(NS_EPISODES)

        try:
            event_id = await self.client.create_event(
                event_type=event_type,
                data=event_data,
                namespace=namespace,
                role="ASSISTANT",
            )
            logger.info(
                f"[learn] Created event: type={origin_type.value}, "
                f"category={category}, weight={emotional_weight}, namespace={namespace}"
            )
            return event_id
        except Exception as e:
            # AUDIT-003: Use debug_error for enriched error analysis
            debug_error(e, "memory_learn_event", {"category": category, "namespace": namespace})
            return None

    @trace_memory_operation("learn_fact")
    async def learn_fact(
        self,
        fact: str,
        category: str,
        emotional_weight: float = 0.8,
        confidence: float = 0.9,
        session_id: Optional[str] = None,
        use_global: bool = True,
        **extra_metadata,
    ) -> Optional[str]:
        """
        LEARN: Gravar FATO confirmado por humano (HIL).

        Facts have higher weight and confidence by default since
        they are confirmed by humans.

        Args:
            fact: O fato confirmado
            category: Categoria (column_mapping, user_preference, etc)
            emotional_weight: Peso Hebbian (default 0.8 = importante)
            confidence: Nivel de confianca (default 0.9 = alto)
            session_id: ID da sessao
            use_global: Se True, armazena no namespace global (recomendado)

        Returns:
            Event ID or None if failed
        """
        return await self.learn(
            content=fact,
            category=category,
            origin_type=MemoryOriginType.FACT,
            source_type=MemorySourceType.HUMAN_HIL,
            emotional_weight=emotional_weight,
            confidence=confidence,
            session_id=session_id,
            event_type="import_pattern",
            use_global=use_global,
            **extra_metadata,
        )

    @trace_memory_operation("learn_inference")
    async def learn_inference(
        self,
        inference: str,
        category: str,
        confidence: float = 0.6,
        emotional_weight: float = 0.4,
        session_id: Optional[str] = None,
        use_global: bool = False,
        **extra_metadata,
    ) -> Optional[str]:
        """
        LEARN: Gravar INFERENCIA do agente.

        Inferences have lower weight since not human-confirmed.
        They may be promoted to FACT if later confirmed by HIL.

        Args:
            inference: A inferencia do agente
            category: Categoria
            confidence: Nivel de confianca (default 0.6)
            emotional_weight: Peso Hebbian (default 0.4 = normal)
            session_id: ID da sessao
            use_global: Se True, armazena no namespace global

        Returns:
            Event ID or None if failed
        """
        return await self.learn(
            content=inference,
            category=category,
            origin_type=MemoryOriginType.INFERENCE,
            source_type=MemorySourceType.AGENT_INFERENCE,
            emotional_weight=emotional_weight,
            confidence=confidence,
            session_id=session_id,
            event_type="agent_observation",
            use_global=use_global,
            **extra_metadata,
        )

    @trace_memory_operation("learn_episode")
    async def learn_episode(
        self,
        episode_content: str,
        category: str,
        outcome: str = "success",
        emotional_weight: float = 0.6,
        session_id: Optional[str] = None,
        tool_results: Optional[List[Dict]] = None,
        **extra_metadata,
    ) -> Optional[str]:
        """
        LEARN: Gravar EPISODIO completo (import cycle).

        Episodes capture complete interactions and are used by
        EpisodicMemoryStrategy to generate REFLECTIONS (insights).

        Args:
            episode_content: Descricao do episodio
            category: Categoria (import_completed, mapping_learned, etc)
            outcome: Resultado (success, failure, partial)
            emotional_weight: Peso Hebbian
            session_id: ID da sessao
            tool_results: Resultados de tools usadas

        Returns:
            Event ID or None if failed
        """
        return await self.learn(
            content=episode_content,
            category=category,
            origin_type=MemoryOriginType.EPISODE,
            source_type=MemorySourceType.AGENT_INFERENCE,
            emotional_weight=emotional_weight,
            confidence=0.8,  # Episodes are captured facts
            session_id=session_id,
            event_type="import_completed",
            use_global=True,  # Episodes go to global for cross-learning
            tool_results=tool_results,
            outcome=outcome,
            **extra_metadata,
        )

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    @staticmethod
    def interpret_weight(weight: float) -> str:
        """
        Interpret Hebbian weight for debugging/logging.

        Returns: "noise", "normal", "important", or "critical"
        """
        return interpret_hebbian_weight(weight)

    def get_session_id(self) -> str:
        """Generate session ID for current agent/actor."""
        return f"{self.agent_id}-{self.actor_id}-{datetime.utcnow().strftime('%Y%m%d%H%M')}"


# ============================================================================
# CONVENIENCE FUNCTIONS (for simpler usage)
# ============================================================================

async def observe_patterns(
    query: str,
    agent_id: str = "system",
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Quick helper to observe global patterns without instantiating manager.

    Example:
        patterns = await observe_patterns("serial number mapping")
    """
    manager = AgentMemoryManager(agent_id=agent_id, use_global_namespace=True)
    return await manager.observe_global(query=query, limit=limit)


async def learn_pattern(
    pattern: str,
    category: str,
    agent_id: str,
    is_confirmed: bool = False,
) -> Optional[str]:
    """
    Quick helper to learn a pattern without full manager setup.

    Example:
        await learn_pattern(
            "SERIAL column maps to serial_number",
            category="column_mapping",
            agent_id="nexo_import",
            is_confirmed=True,  # Human confirmed
        )
    """
    manager = AgentMemoryManager(agent_id=agent_id, use_global_namespace=True)

    if is_confirmed:
        return await manager.learn_fact(
            fact=pattern,
            category=category,
            use_global=True,
        )
    else:
        return await manager.learn_inference(
            inference=pattern,
            category=category,
            use_global=True,
        )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Main class
    "AgentMemoryManager",

    # Convenience functions
    "observe_patterns",
    "learn_pattern",

    # Re-exports from genesis_kernel for convenience
    "MemoryOriginType",
    "MemorySourceType",
    "NexoMemoryMetadata",
]
