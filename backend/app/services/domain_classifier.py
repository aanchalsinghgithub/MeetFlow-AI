from dataclasses import dataclass

from app.services.team_mapping import load_team_mapping


@dataclass
class DomainResult:
    domain: str
    confidence: float
    reason: str


class DomainClassifier:
    def __init__(self) -> None:
        self.mapping = load_team_mapping()

    def classify(self, text: str) -> DomainResult:
        normalized = text.lower()
        best_domain = "Product"
        best_score = 0.35
        best_hits: list[str] = []

        for domain, config in self.mapping.items():
            hits = [keyword for keyword in config.get("keywords", []) if keyword.lower() in normalized]
            if hits:
                score = min(0.92, 0.55 + len(hits) * 0.12)
                if score > best_score:
                    best_domain = self._display_name(domain)
                    best_score = score
                    best_hits = hits

        if best_hits:
            return DomainResult(best_domain, best_score, f"keyword match: {', '.join(best_hits)}")

        return DomainResult(best_domain, best_score, "fallback product/context classification")

    @staticmethod
    def _display_name(domain: str) -> str:
        names = {
            "ai_ml": "AI/ML",
            "qa": "QA",
            "aws": "AWS",
            "devops": "DevOps",
        }
        return names.get(domain, domain.replace("_", " ").title())
