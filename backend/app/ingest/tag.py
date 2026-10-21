"""Rule-based document tagging. In production this is an LLM/classifier pass with the
rules as a fallback; for the synthetic corpus, filename + text rules are exact."""
import re

TYPE_RULES = [
    ("cmc", re.compile(r"^cmc_|Module 3\.2\.P", re.I)),
    ("ha_letter", re.compile(r"^ha_letter|Food and Drug Administration|Medicines Agency|PMDA", re.I)),
    ("stability_protocol", re.compile(r"^stability_protocol|Stability Protocol", re.I)),
    ("spec", re.compile(r"^spec_|Excipient Specification", re.I)),
]
PRODUCT_RE = re.compile(r"\bHT-\d{3}\b")
ECTD_RE = re.compile(r"\b3\.2\.[PS](?:\.\d+)*\b")


def tag(filename: str, text: str) -> dict:
    doc_type = next((t for t, rx in TYPE_RULES if rx.search(filename)), None) or \
        next((t for t, rx in TYPE_RULES if rx.search(text[:2000])), "other")
    product = PRODUCT_RE.search(filename) or PRODUCT_RE.search(text)
    ectd = ECTD_RE.search(text[:2000])
    return {"doc_type": doc_type,
            "product": product.group(0) if product and doc_type != "spec" else None,
            "ectd_section": ectd.group(0) if ectd else None}
