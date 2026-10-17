# Performance and scalability

No benchmark report, load test or production latency measurement is checked in. Values below are configuration bounds, not measured performance.

## Current bounds and likely bottlenecks

- PostgreSQL connect timeout is five seconds; pool size/overflow are SQLAlchemy defaults and not explicitly tuned here.
- Upload defaults to 15,000,000 bytes; parser defaults cap 250 pages and two million extracted characters.
- OCR renders at default 200 DPI, uses an external local binary and up to 30 seconds/page; OCR is CPU/memory intensive.
- Embeddings batch up to 32 texts by default on CPU, with chunks capped at 1200 characters.
- Qdrant candidate retrieval defaults to 30; final top-K defaults to 5; context max 12,000 chars.
- LLM timeout default 90 seconds; browser assistant timeout 110 seconds.
- Worker polls every two seconds and claims one job per `process_one` invocation; horizontal scaling depends on DB locking/lease behavior and external idempotency.
- Rate limits are in-process and reset on restart; replicas do not share enforcement.

## Hypotheses to measure

Likely bottlenecks include OCR rendering, cold model load, synchronous Boto3 operations in thread pools, PostgreSQL FTS under larger data, queue poll/claim throughput, Qdrant network latency, and provider generation latency. These are hypotheses. Establish representative synthetic workloads and measure p50/p95/p99 API latency, queue age, per-stage time, memory, DB pool waits, provider errors, and document-size effects before tuning. Do not report fabricated metrics.
