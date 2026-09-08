from opportunity_engine import apply_opportunity_engine as _base_apply


def apply_opportunity_engine(frame):
    out = _base_apply(frame)
    if out is None or out.empty:
        return out
    # The existing UI has four component cards. Point those cards at the new
    # engine's corresponding component scores while retaining all eight new
    # components in the payload for the detailed opportunity view.
    if "opportunity_technical_score" in out:
        out["trader_similarity_score"] = out["opportunity_technical_score"]
        out["technical_score"] = out["opportunity_technical_score"]
    if "opportunity_analysts_score" in out:
        out["analyst_consensus_score"] = out["opportunity_analysts_score"]
    if "opportunity_fundamentals_score" in out:
        out["fundamental_score"] = out["opportunity_fundamentals_score"]
    out["overall_score"] = out["opportunity_score"]
    return out
