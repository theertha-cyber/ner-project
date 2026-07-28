"""One-off generator for tests/fixtures/retrieval_eval/{corpus,golden_set,embeddings}.
Run manually and commit the output; not imported by application or test code.

Embeddings are a deterministic synthetic bag-of-hashed-words vector, not a real
semantic embedding model — this keeps the golden set fully offline and reproducible
with no API dependency, at the cost of not reflecting true semantic similarity beyond
lexical overlap. See tests/fixtures/retrieval_eval/README.md.
"""
import hashlib
import json
import math
import os

DIM = 1536
EMBEDDING_MODEL = "synthetic-hash-embedding-v1"

DOCS = [
    ("doc-shipping-rates", "Shipping Rates Overview", [
        "Fictive Freight Co. calculates shipping rates using package weight, dimensional weight, and destination zone. Standard ground shipping starts at 8 dollars for packages under 5 pounds.",
        "Expedited air shipping rates are calculated separately and include a fuel surcharge that adjusts monthly based on the national average diesel price index.",
    ]),
    ("doc-package-tracking", "Package Tracking", [
        "Every shipment receives a tracking number that customers can use on the Fictive Freight Co. website or mobile app to see real-time location updates.",
        "Tracking updates are generated at each scan checkpoint: origin facility, regional hub, local delivery station, and final delivery confirmation.",
    ]),
    ("doc-customs-clearance", "Customs Clearance", [
        "International shipments crossing a border require a completed customs declaration form listing item value, country of origin, and harmonized tariff code.",
        "Customs clearance delays are most commonly caused by missing invoices, undervalued declarations, or restricted item classifications.",
    ]),
    ("doc-driver-policies", "Driver Policies", [
        "Fictive Freight Co. drivers must complete a pre-trip vehicle inspection checklist before every route and log hours of service electronically.",
        "Drivers are required to obtain a signature or photo proof of delivery for every package marked as signature-required.",
    ]),
    ("doc-fuel-surcharge", "Fuel Surcharge Policy", [
        "The fuel surcharge is a percentage added to the base shipping rate that fluctuates weekly according to published national diesel fuel prices.",
        "Fuel surcharge percentages are published on the first business day of each week and applied automatically to all new shipments.",
    ]),
    ("doc-warehouse-locations", "Warehouse Locations", [
        "Fictive Freight Co. operates regional distribution warehouses in Denver, Atlanta, and Columbus, each serving a multi-state delivery radius.",
        "The Denver warehouse specializes in cold-chain storage for temperature-sensitive freight including pharmaceuticals and perishable goods.",
    ]),
    ("doc-insurance-claims", "Insurance Claims Process", [
        "Customers filing an insurance claim for a lost or damaged shipment must submit photos of the damage and the original purchase receipt within 30 days.",
        "Insurance claims are reviewed by the claims department within 10 business days and approved claims are reimbursed via the original payment method.",
    ]),
    ("doc-delivery-sla", "Delivery Service Level Agreements", [
        "Standard ground delivery has a service level agreement of 3 to 5 business days depending on origin and destination zones.",
        "Expedited service guarantees next-business-day delivery for shipments tendered before the 5pm cutoff at an origin facility.",
    ]),
    ("doc-hazmat-rules", "Hazardous Materials Shipping Rules", [
        "Shipments containing hazardous materials must be labeled according to Department of Transportation classification codes and packaged in approved containers.",
        "Hazmat shipments require an additional handling fee and can only be tendered at facilities certified for hazardous materials acceptance.",
    ]),
    ("doc-returns-policy", "Returns and Reverse Logistics", [
        "Fictive Freight Co. offers a reverse logistics service that generates a prepaid return label for customers sending merchandise back to a retailer.",
        "Return shipments are scanned at intake and the retailer is notified automatically once the returned package reaches the sorting facility.",
    ]),
    ("doc-invoicing", "Invoicing and Billing", [
        "Business accounts receive a consolidated weekly invoice itemizing every shipment, applicable surcharges, and any accessorial fees.",
        "Invoice disputes must be submitted through the billing portal within 60 days of the invoice date to be eligible for adjustment.",
    ]),
    ("doc-membership-tiers", "Membership Tiers", [
        "Fictive Freight Co. offers Silver, Gold, and Platinum membership tiers, each unlocking progressively larger shipping rate discounts.",
        "Platinum members receive priority customer support, waived residential delivery fees, and free package insurance up to 500 dollars per shipment.",
    ]),
    ("doc-address-corrections", "Address Correction Fees", [
        "An address correction fee applies whenever a shipment label address does not match the delivery address and must be corrected in transit.",
        "Customers can avoid address correction fees by verifying the delivery address using the address validation tool before generating a shipping label.",
    ]),
    ("doc-signature-requirements", "Signature Requirements", [
        "Shipments valued over 200 dollars automatically require an adult signature at the delivery address unless the sender opts out.",
        "If no one is available to sign, the driver leaves a delivery attempt notice and the package is held at the local station for pickup.",
    ]),
    ("doc-carbon-offset", "Carbon Offset Program", [
        "Customers can opt into the carbon offset program at checkout, adding a small fee that funds reforestation and renewable energy projects.",
        "The carbon offset program has funded the planting of over two hundred thousand trees since its launch, according to the annual sustainability report.",
    ]),
]


def _embed(text: str) -> list:
    vec = [0.0] * DIM
    words = [w.strip(".,").lower() for w in text.split() if len(w.strip(".,")) > 2]
    for w in words:
        h = hashlib.md5(w.encode("utf-8")).digest()
        idx = int.from_bytes(h[:4], "big") % DIM
        sign = 1.0 if h[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def main():
    out_dir = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "retrieval_eval")
    out_dir = os.path.abspath(out_dir)

    corpus_records = []
    chunk_embeddings = {}
    for doc_id, title, chunks in DOCS:
        corpus_records.append({
            "document_id": doc_id,
            "title": title,
            "chunks": [{"chunk_index": i, "chunk_text": text} for i, text in enumerate(chunks)],
        })
        for i, text in enumerate(chunks):
            chunk_embeddings[f"{doc_id}::{i}"] = _embed(text)

    golden_records = []
    query_embeddings = {}
    for doc_id, title, chunks in DOCS:
        query_text = f"What are the rules for {title.lower()}?"
        query_id = f"q-{doc_id}"
        golden_records.append({
            "query_id": query_id,
            "query": query_text,
            "relevant": [
                {"document_id": doc_id, "chunk_index": 0, "grade": 3},
                {"document_id": doc_id, "chunk_index": 1, "grade": 2},
            ],
            "notes": f"Single-topic query targeting {doc_id}.",
        })
        query_embeddings[query_id] = _embed(query_text + " " + " ".join(chunks))

        specific_query_text = f"Tell me more details: {chunks[1][:80]}"
        specific_query_id = f"q-{doc_id}-detail"
        golden_records.append({
            "query_id": specific_query_id,
            "query": specific_query_text,
            "relevant": [
                {"document_id": doc_id, "chunk_index": 1, "grade": 3},
                {"document_id": doc_id, "chunk_index": 0, "grade": 1},
            ],
            "notes": f"Chunk-specific follow-up query targeting {doc_id} chunk 1.",
        })
        query_embeddings[specific_query_id] = _embed(specific_query_text)

    for extra_id, text in [
        ("q-no-match-1", "What is the capital of a fictional planet named Zorlax?"),
        ("q-no-match-2", "Explain the rules of competitive chess tournaments."),
    ]:
        golden_records.append({
            "query_id": extra_id,
            "query": text,
            "relevant": [],
            "notes": "Deliberate no-judgment query for skip-handling coverage.",
        })
        query_embeddings[extra_id] = _embed(text)

    with open(os.path.join(out_dir, "corpus.jsonl"), "w", encoding="utf-8") as f:
        for rec in corpus_records:
            f.write(json.dumps(rec) + "\n")

    with open(os.path.join(out_dir, "golden_set.jsonl"), "w", encoding="utf-8") as f:
        for rec in golden_records:
            f.write(json.dumps(rec) + "\n")

    with open(os.path.join(out_dir, "embeddings.json"), "w", encoding="utf-8") as f:
        json.dump({
            "embedding_model": EMBEDDING_MODEL,
            "dimension": DIM,
            "queries": query_embeddings,
            "chunks": chunk_embeddings,
        }, f)

    print(f"Wrote {len(corpus_records)} documents, {len(golden_records)} queries to {out_dir}")


if __name__ == "__main__":
    main()
