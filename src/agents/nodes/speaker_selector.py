from langgraph.graph import END
from langgraph.types import Command
from loguru import logger

from src.agents.agents import speaker_selector_agent
from src.agents.state import GraphState


def speaker_selector_node(state: GraphState) -> str:
    if state.get("resolved", False):
        logger.debug("Answer already refined, terminating conversation.")
        return Command(goto=END, update={"next": END, "resolved": False})

    executed = state.get("executed_agents", [])
    pipeline = state.get("pipeline", []) or []
    remaining = [a for a in pipeline if a not in executed]

    context = (
        f"planned_pipeline: {pipeline}\n"
        f"executed_agents: {executed}\n"
        f"remaining_pipeline: {remaining}"
    )

    speaker = None
    try:
        result = speaker_selector_agent.invoke({"context": context})
        speaker = result.speaker if result else None
    except Exception as e:
        logger.warning(f"Speaker Selector structured output failed: {e}")

    # Minimal safety net: only engages when the LLM returns nothing or an
    # already-executed name. No plan parsing, no ordering logic.
    if speaker is None or speaker in executed:
        if speaker in executed:
            logger.warning(f"Speaker Selector picked already-executed '{speaker}', overriding.")
        speaker = remaining[0] if remaining else "answer_refiner"
        if speaker == "answer_refiner" and "answer_refiner" in executed:
            speaker = "END"
        logger.warning(f"Speaker Selector fallback chose: {speaker}")

    logger.debug(f"Speaker Selector selected next speaker: {speaker}")
    if speaker == "END":
        speaker = END

    return Command(goto=speaker, update={"next": speaker})
