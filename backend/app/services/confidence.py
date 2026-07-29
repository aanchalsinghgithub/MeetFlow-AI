from app.schemas.task import ExtractedTask


def score_task(task: ExtractedTask, domain_confidence: float) -> float:
    score = 0.35
    if task.task:
        score += 0.18
    if task.owner:
        score += 0.14
    if task.mentioned_by:
        score += 0.08
    if task.requested_by:
        score += 0.08
    if task.deadline:
        score += 0.08
    if task.dependencies:
        score += 0.03
    score += domain_confidence * 0.06
    return round(min(score, 0.98), 2)
