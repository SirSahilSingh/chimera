from __future__ import annotations


def generate_recommendations(insights: list[dict]) -> list[dict]:
    recommendations = []
    for insight in insights:
        category = insight["category"]
        if category == "CALIBRATION":
            action = "Monitor stored prediction calibration and consider a future human-approved model evaluation."
        elif category == "PROVIDER":
            action = "Keep non-production provider outcomes separated from LIVE reporting."
        elif category == "OPERATIONAL":
            action = "Investigate the persisted lifecycle bottleneck before changing operations."
        elif category == "WARNING":
            action = "Collect more completed outcomes before drawing an operational conclusion."
        else:
            action = "Review the observed pattern with recovery operations."
        recommendations.append({"category": category, "recommendation": action, "evidence": insight["evidence"], "sample_size": insight["sample_size"], "limitation": insight["limitation"], "review_requirement": "REQUIRES HUMAN REVIEW"})
    return recommendations
