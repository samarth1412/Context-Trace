import { mockEvalSummary, mockTraceSummaries, mockTraces } from "@/lib/mock-data";
import type { DataSource, EvalSummary, TraceDetail, TraceSummary } from "@/lib/types";

type DataResult<T> = {
  data: T;
  source: DataSource;
  error?: string;
};

const API_URL = process.env.CONTEXTTRACE_API_URL ?? "http://localhost:8000";
const API_KEY = process.env.CONTEXTTRACE_API_KEY ?? "";
const EVAL_SET_ID = process.env.CONTEXTTRACE_EVAL_SET_ID ?? "";

async function fetchBackend<T>(path: string): Promise<T> {
  if (!API_KEY) {
    throw new Error("CONTEXTTRACE_API_KEY is not configured");
  }

  const response = await fetch(`${API_URL}${path}`, {
    headers: {
      Authorization: `Bearer ${API_KEY}`
    },
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status} for ${path}`);
  }

  return response.json() as Promise<T>;
}

export async function getTraceSummaries(): Promise<DataResult<TraceSummary[]>> {
  try {
    const traces = await fetchBackend<TraceSummary[]>("/v1/traces");
    return { data: traces, source: "backend" };
  } catch (error) {
    return { data: mockTraceSummaries, source: "mock", error: errorMessage(error) };
  }
}

export async function getTraceDetail(traceId: string): Promise<DataResult<TraceDetail>> {
  try {
    const trace = await fetchBackend<TraceDetail>(`/v1/traces/${traceId}`);
    return { data: trace, source: "backend" };
  } catch (error) {
    return {
      data: mockTraces.find((trace) => trace.id === traceId) ?? mockTraces[0],
      source: "mock",
      error: errorMessage(error)
    };
  }
}

export async function getEvalSummary(): Promise<DataResult<EvalSummary>> {
  try {
    if (!EVAL_SET_ID) {
      throw new Error("CONTEXTTRACE_EVAL_SET_ID is not configured");
    }
    const summary = await fetchBackend<EvalSummary>(`/v1/eval-sets/${EVAL_SET_ID}/summary`);
    return { data: summary, source: "backend" };
  } catch (error) {
    return { data: mockEvalSummary, source: "mock", error: errorMessage(error) };
  }
}

export async function getDashboardData() {
  const [traces, evalSummary] = await Promise.all([getTraceSummaries(), getEvalSummary()]);
  return { traces, evalSummary };
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unknown backend error";
}
