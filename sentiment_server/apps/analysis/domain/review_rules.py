from decimal import Decimal


REVIEW_CONFIDENCE_THRESHOLD = Decimal("0.70")


def is_high_confidence(confidence):
    if confidence is None:
        return False
    return Decimal(str(confidence)) >= REVIEW_CONFIDENCE_THRESHOLD


def is_effectively_reviewed(result):
    return is_high_confidence(result.confidence) or result.reviewed_at is not None
