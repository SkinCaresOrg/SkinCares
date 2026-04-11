SIGNALS = [
    "hydration",  # water attraction / moisture
    "barrier",  # occlusion / lipid support
    "acne_control",  # antimicrobial / oil-related control
    "soothing",  # anti-inflammatory / calming
    "exfoliation",  # keratolytic / acid activity
    "antioxidant",  # oxidative stress protection
    "irritation_risk",  # allergens / preservatives / fragrance
]

COSING_FUNCTION_MAP = {
    # ---------------- HYDRATION ----------------
    "HUMECTANT": {"hydration": 1},
    "MOISTURISING": {"hydration": 1},
    # ---------------- BARRIER / EMOLLIENT ----------------
    "EMOLLIENT": {"barrier": 1},
    "SKIN PROTECTING": {"barrier": 1},
    "OCCLUSIVE": {"barrier": 1},
    "FILM FORMING": {"barrier": 0.5},
    "SKIN CONDITIONING - EMOLLIENT": {"barrier": 1},
    # ---------------- ACNE / MICROBIAL CONTROL ----------------
    "ANTIMICROBIAL": {"acne_control": 1},
    "ASTRINGENT": {"acne_control": 0.5},
    # ---------------- SOOTHING ----------------
    "SOOTHING": {"soothing": 1},
    # inferred from common CosIng usage in your list
    "SKIN CONDITIONING": {"soothing": 0.2},
    # ---------------- EXFOLIATION / KERATOLYTIC ----------------
    "KERATOLYTIC": {"exfoliation": 1},
    "BUFFERING": {"exfoliation": 0.3},  # acids often appear here in CosIng
    "SURFACTANT - CLEANSING": {"exfoliation": 0.1},
    # ---------------- ANTIOXIDANT ----------------
    "ANTIOXIDANT": {"antioxidant": 1},
    # ---------------- IRRITATION RISK (VERY IMPORTANT) ----------------
    "FRAGRANCE": {"irritation_risk": 1},
    "PERFUMING": {"irritation_risk": 1},
    "PRESERVATIVE": {"irritation_risk": 1},
}

#
HIGH_RISK_FLAGS = {
    "METHYLISOTHIAZOLINONE": 1,
    "METHYLCHLOROISOTHIAZOLINONE": 1,
}


def cosing_to_vector(functions):
    vector = {
        "hydration": 0,
        "barrier": 0,
        "acne_control": 0,
        "soothing": 0,
        "exfoliation": 0,
        "antioxidant": 0,
        "irritation_risk": 0,
    }

    for f in functions:
        f = f.strip().upper()

        if f in COSING_FUNCTION_MAP:
            for k, v in COSING_FUNCTION_MAP[f].items():
                vector[k] = max(vector[k], v)

        # extra heuristic boost
        if "FRAGRANCE" in f or "PERFUMING" in f:
            vector["irritation_risk"] = max(vector["irritation_risk"], 1)

        if "PRESERVATIVE" in f:
            vector["irritation_risk"] = max(vector["irritation_risk"], 1)

    return vector
