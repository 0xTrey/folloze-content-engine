from __future__ import annotations

BANNED_TERMS = [
    "buyer experience platform",
    "revolutionary",
    "cutting-edge",
    "set it and forget it",
    "generator ai",
    "abm platform",
]

PROOF_POINTS = ["$6.3M", "$10M", "98%", "$750K", "5x faster", "478 MQLs"]

# GEO kill-list: marketing fluff that LLMs penalize for citation-worthiness.
GEO_KILL_LIST = [
    "streamline",
    "empower",
    "unlock",
    "leverage",
    "seamless",
    "cutting-edge",
    "game-changer",
    "best-in-class",
    "synergy",
    "holistic",
    "robust",
    "turnkey",
    "paradigm shift",
    "thought leader",
    "disrupt",
    "innovative",
    "revolutionize",
    "transformative",
    "next-generation",
    "future-proof",
]

ENTITY_REQUIRED = ["folloze"]
ENTITY_FORBIDDEN = [
    "microsite builder",
    "buyer experience platform",
    "agentic",
    "page builder",
]

# Emotion-first detection: pain words should appear before product words in intro.
PAIN_SIGNALS = [
    "struggle",
    "frustrated",
    "overwhelm",
    "chaos",
    "broken",
    "failing",
    "behind",
    "waste",
    "missed",
    "losing",
    "painful",
    "stuck",
    "burned",
    "anxiety",
    "risk",
    "fear",
    "confusion",
    "pressure",
    "bottleneck",
    "gap",
    "disconnect",
    "lag",
    "friction",
    "blind spot",
    "costly",
    "outdated",
    "complex",
    "manual",
    "slow",
    "unreliable",
]

PRODUCT_SIGNALS = [
    "folloze",
    "platform",
    "solution",
    "product",
    "tool",
    "software",
    "feature",
    "dashboard",
    "module",
    "integration",
    "workflow",
]
