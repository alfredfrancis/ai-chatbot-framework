"""A tiny OTLP/HTTP receiver: accepts POST /v1/traces and /v1/metrics (protobuf), counts the requests and keeps
what they carried, decoded. Used by the telemetry integration test and the live checks.

GET /_received returns {"requests": {"traces": n, "metrics": n}, "spans": [...], "metrics": [...]}, where a
span is {name, trace_id, span_id, parent_span_id, kind, status, attributes, service, instance} (ids in hex)
and a metric point is {name, attributes, value}. DELETE /_received clears it.

Run standalone: python -m tests.fakes.fake_otlp --port 4318
"""

from __future__ import annotations

import argparse
import gzip
from typing import Any

from fastapi import FastAPI, Request, Response
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue

app = FastAPI()
REQUESTS = {"traces": 0, "metrics": 0}
SPANS: list[dict[str, Any]] = []
POINTS: list[dict[str, Any]] = []


def _value(v: AnyValue) -> Any:
    kind = v.WhichOneof("value")
    if kind == "array_value":
        return [_value(x) for x in v.array_value.values]
    return getattr(v, kind) if kind else None


def _attrs(kvs) -> dict[str, Any]:
    return {kv.key: _value(kv.value) for kv in kvs}


async def _body(request: Request) -> bytes:
    body = await request.body()
    return gzip.decompress(body) if request.headers.get("content-encoding") == "gzip" else body


@app.post("/v1/traces")
async def traces(request: Request):
    req = ExportTraceServiceRequest.FromString(await _body(request))
    REQUESTS["traces"] += 1
    for rs in req.resource_spans:
        resource = _attrs(rs.resource.attributes)
        service, instance = resource.get("service.name"), resource.get("service.instance.id")
        for ss in rs.scope_spans:
            for s in ss.spans:
                SPANS.append(
                    {
                        "name": s.name,
                        "trace_id": s.trace_id.hex(),
                        "span_id": s.span_id.hex(),
                        "parent_span_id": s.parent_span_id.hex(),
                        "kind": s.kind,
                        "status": s.status.code,  # 0 unset, 1 ok, 2 error
                        "attributes": _attrs(s.attributes),
                        "service": service,
                        "instance": instance,
                    }
                )
    return Response(ExportTraceServiceRequest().SerializeToString(), media_type="application/x-protobuf")


@app.post("/v1/metrics")
async def metrics(request: Request):
    req = ExportMetricsServiceRequest.FromString(await _body(request))
    REQUESTS["metrics"] += 1
    for rm in req.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                data = getattr(m, m.WhichOneof("data"))
                for p in data.data_points:
                    value = p.count if m.WhichOneof("data") == "histogram" else (p.as_int or p.as_double)
                    POINTS.append({"name": m.name, "attributes": _attrs(p.attributes), "value": value})
    return Response(ExportMetricsServiceRequest().SerializeToString(), media_type="application/x-protobuf")


@app.get("/_received")
def received():
    return {"requests": REQUESTS, "spans": SPANS, "metrics": POINTS}


@app.delete("/_received")
def clear():
    REQUESTS.update(traces=0, metrics=0)
    SPANS.clear()
    POINTS.clear()
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=4318)
    args = p.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
