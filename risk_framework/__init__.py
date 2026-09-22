"""Third-party risk assessment aggregation, independent of agents and frontends."""
from .config import Config, load_config
from .io import load_assessments, load_json, to_json
from .models import Assessment, CategoryResult, EntityResult, OverallResult, Scoreboard
from .scoring import normalize_weights, rank_entities, score_category
from .service import RiskFramework
from .validation import ValidationError

__all__ = [
    "Assessment", "CategoryResult", "Config", "EntityResult", "OverallResult",
    "RiskFramework", "Scoreboard", "ValidationError", "load_assessments", "load_config",
    "load_json", "normalize_weights", "rank_entities", "score_category", "to_json",
]
