from risk_framework import load_config


def config(**overrides):
    return load_config(overrides={"overall_simulation": {"runs": 200}, **overrides})


def rows(entity, category, scores):
    return [dict(entity_id=entity, category=category, risk_score=value, run_id=i)
            for i, value in enumerate(scores)]
