"""
Cost Calculator Service
Calculates per-call cost from provider pricing and computes gross margins.
Now reads rates dynamically from the configured providers.
"""
import os
import sys
from decimal import Decimal
from typing import Optional
import structlog

# Ensure we can import from agent
agent_path = os.path.join(os.path.dirname(__file__), "..", "..", "agent")
if agent_path not in sys.path:
    sys.path.insert(0, agent_path)

from providers.stt import get_stt_provider
from providers.tts import get_tts_provider
from providers.llm import get_llm_provider

logger = structlog.get_logger(__name__)

INR_PER_USD = Decimal(os.getenv("INR_PER_USD", "84"))

def _get_stt_rate() -> Decimal:
    """Get STT rate per minute dynamically."""
    provider_name = os.getenv("STT_PROVIDER", "sarvam").lower()
    if provider_name == "sarvam":
        return Decimal("0.0030")  # Sarvam rate
    return Decimal("0.0043")      # Deepgram fallback

def _get_tts_rate() -> Decimal:
    """Get TTS rate per character dynamically."""
    provider_name = os.getenv("TTS_PROVIDER", "sarvam").lower()
    if provider_name == "sarvam":
        return Decimal("0.000010")  # Sarvam rate
    return Decimal("0.0003")      # ElevenLabs fallback

def _get_llm_rates() -> dict:
    """Get LLM rates per token dynamically."""
    # Assuming gpt-4o-mini baseline or configurable models
    return {"input": Decimal("0.00000015"), "output": Decimal("0.00000060")}


def calculate_stt_cost(duration_seconds: float) -> Decimal:
    rate = _get_stt_rate()
    minutes = Decimal(str(duration_seconds)) / Decimal("60")
    return (minutes * rate).quantize(Decimal("0.000001"))

def calculate_llm_cost(input_tokens: int, output_tokens: int) -> Decimal:
    rates = _get_llm_rates()
    cost = (Decimal(str(input_tokens)) * rates["input"] + Decimal(str(output_tokens)) * rates["output"])
    return cost.quantize(Decimal("0.000001"))

def calculate_tts_cost(characters: int) -> Decimal:
    rate = _get_tts_rate()
    return (Decimal(str(characters)) * rate).quantize(Decimal("0.000001"))

def calculate_total_call_cost(
    duration_seconds: float,
    tts_characters: int,
    llm_input_tokens: int,
    llm_output_tokens: int,
    revenue_inr: float = 0.0,
) -> dict:
    """
    Calculate complete per-call cost breakdown, variable cost, and gross margin.
    """
    stt_cost = calculate_stt_cost(duration_seconds)
    tts_cost = calculate_tts_cost(tts_characters)
    llm_cost = calculate_llm_cost(llm_input_tokens, llm_output_tokens)
    
    # Telephony cost (e.g. Exotel baseline)
    telephony_cost_usd = (Decimal(str(duration_seconds)) / Decimal("60")) * Decimal("0.002")
    
    total_variable_cost_usd = stt_cost + tts_cost + llm_cost + telephony_cost_usd
    total_variable_cost_inr = (total_variable_cost_usd * INR_PER_USD).quantize(Decimal("0.01"))
    
    revenue_inr_dec = Decimal(str(revenue_inr))
    gross_contribution_inr = revenue_inr_dec - total_variable_cost_inr
    gross_margin_pct = (gross_contribution_inr / revenue_inr_dec * Decimal("100")) if revenue_inr_dec > 0 else Decimal("0")

    result = {
        "stt_cost_usd": float(stt_cost),
        "tts_cost_usd": float(tts_cost),
        "llm_cost_usd": float(llm_cost),
        "telephony_cost_usd": float(telephony_cost_usd),
        "total_variable_cost_usd": float(total_variable_cost_usd),
        "total_variable_cost_inr": float(total_variable_cost_inr),
        "revenue_inr": float(revenue_inr_dec),
        "gross_contribution_inr": float(gross_contribution_inr),
        "gross_margin_pct": float(gross_margin_pct.quantize(Decimal("0.01"))),
    }

    logger.debug("call_cost_calculated", **result)
    return result

async def persist_call_cost(call_id: str, cost_breakdown: dict, db_session) -> None:
    from sqlalchemy import text
    try:
        db_session.execute(
            text("""
                UPDATE usage_logs
                SET
                    stt_cost_usd = :stt_cost_usd,
                    tts_cost_usd = :tts_cost_usd,
                    llm_cost_usd = :llm_cost_usd,
                    cost_usd     = :total_variable_cost_usd
                WHERE call_id = :call_id
            """),
            {
                "call_id": call_id,
                **cost_breakdown,
            },
        )

        db_session.execute(
            text("UPDATE call_records SET call_cost_usd = :cost WHERE call_id = :call_id"),
            {"cost": cost_breakdown["total_variable_cost_usd"], "call_id": call_id},
        )

        db_session.commit()
        logger.info("call_cost_persisted", call_id=call_id, total_usd=cost_breakdown["total_variable_cost_usd"])

    except Exception as exc:
        logger.error("call_cost_persist_failed", call_id=call_id, error=str(exc))
