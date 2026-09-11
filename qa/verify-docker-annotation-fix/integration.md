# CAP-6 Integration Evidence

- Portal-to-gateway reachability: PASS (portal HTTP 200; gateway health HTTP 200).
- Gateway-to-database health: PASS (`database.status=healthy`, `reachable`).
- Annotation service health: PASS (HTTP 200, `status=ok`).
- Portal image: rebuilt successfully as `ner-project-portal:latest`; image ID `sha256:b33d0a280131a0eb942e42f0162cfdea236a0bcfba0d079fed54bf8e5f902915`.
- CAP-5 source/build evidence: CAP-5 commit `99bce39`; focused CAP-5 tests passed.
- Confirmed-span persistence count for deployed gestures: NOT OBSERVED. No claim is made because authenticated gesture traces were not captured.
# CAP-6 Integration Verification

- Timestamp: 2026-09-11T09:53:44Z
- Portal, gateway, and annotation health boundaries are reachable after Compose recreation.
- Source-level CAP-5 corroboration confirms one create-span request for same-token click and multi-token drag, with the drag inclusive range preserved.
- No authenticated deployed request trace or resulting persisted confirmed-span count was captured; this remains unverified rather than passed.
