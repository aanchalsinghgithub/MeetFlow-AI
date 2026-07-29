from app.services.domain_classifier import DomainClassifier


def test_keyword_domain_classification() -> None:
    result = DomainClassifier().classify("Fix the authentication API timeout")

    assert result.domain == "Backend"
    assert result.confidence > 0.5
