"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { MonolithShell, sharedSideNav } from "@/app/components/monolith-shell";
import { getProjectStatusApi, listProjectsApi, predictProjectApi } from "@/lib/api";

type ProjectStatus = {
  project_name: string;
  instance_id: string;
  state: string;
  public_ip: string | null;
  instance_type: string;
  service_status: string;
  inference_url: string | null;
};

type Primitive = string | number | boolean | null;
type FeatureMode = "string" | "single-array" | "batch-array";

type RequestSchema = {
  properties?: {
    features?: {
      oneOf?: Array<{ type?: string; items?: { type?: string; items?: { type?: string } } }>;
    };
    max_new_tokens?: { default?: number };
    temperature?: { default?: number };
    top_p?: { default?: number };
    enable_thinking?: { default?: boolean };
  };
};

const FALLBACK_SCHEMA: RequestSchema = {
  properties: {
    features: {
      oneOf: [
        { type: "string" },
        { type: "array", items: { type: "string" } },
        { type: "array", items: { type: "array", items: { type: "string" } } },
      ],
    },
    max_new_tokens: { default: 96 },
    temperature: { default: 0.7 },
    top_p: { default: 0.9 },
    enable_thinking: { default: true },
  },
};

const REQUEST_SCHEMA_CANDIDATE_FILES = [
  "request_schema.json",
  "request.json",
  "request_jaon.json",
];

function parseRepoCoordinates(repoUrl: string): { owner: string; repo: string } | null {
  const normalized = repoUrl.trim().replace(/\.git$/, "");
  const sshMatch = normalized.match(/^git@github\.com:([^/]+)\/([^/]+)$/i);
  if (sshMatch) {
    return { owner: sshMatch[1], repo: sshMatch[2] };
  }

  const httpMatch = normalized.match(/^https?:\/\/github\.com\/([^/]+)\/([^/]+)$/i);
  if (httpMatch) {
    return { owner: httpMatch[1], repo: httpMatch[2] };
  }

  return null;
}

function hasProperty(schema: RequestSchema, name: "max_new_tokens" | "temperature" | "top_p" | "enable_thinking") {
  return Boolean(schema.properties?.[name]);
}

function inferFeatureModes(schema: RequestSchema): FeatureMode[] {
  const oneOf = schema.properties?.features?.oneOf;
  if (!oneOf || oneOf.length === 0) {
    return ["string", "single-array", "batch-array"];
  }

  const modes: FeatureMode[] = [];
  for (const variant of oneOf) {
    if (variant.type === "string") {
      modes.push("string");
      continue;
    }

    if (variant.type === "array" && variant.items?.type === "array") {
      modes.push("batch-array");
      continue;
    }

    if (variant.type === "array") {
      modes.push("single-array");
    }
  }

  return modes.length > 0 ? Array.from(new Set(modes)) : ["string", "single-array", "batch-array"];
}

function isPrimitive(value: unknown): value is Primitive {
  const t = typeof value;
  return value === null || t === "string" || t === "number" || t === "boolean";
}

function parseFeatures(mode: FeatureMode, prompt: string, arrayInput: string): string | Primitive[] | Primitive[][] {
  if (mode === "string") {
    const trimmed = prompt.trim();
    if (!trimmed) {
      throw new Error("features must be a non-empty string");
    }
    return trimmed;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(arrayInput);
  } catch {
    throw new Error("Features JSON is invalid");
  }

  if (!Array.isArray(parsed) || parsed.length === 0) {
    throw new Error("features must be a non-empty array");
  }

  if (mode === "single-array") {
    if (!parsed.every(isPrimitive)) {
      throw new Error("Each item in features must be a primitive value (string, number, boolean, or null)");
    }
    return parsed;
  }

  if (!parsed.every((row) => Array.isArray(row) && row.length > 0 && row.every(isPrimitive))) {
    throw new Error("Batch features must be a non-empty array of non-empty primitive arrays");
  }

  return parsed as Primitive[][];
}

async function fetchSchemaFromRepoRoot(payload: {
  owner: string;
  repo: string;
  githubToken: string;
}): Promise<{ schema: RequestSchema; sourceFile: string }> {
  for (const fileName of REQUEST_SCHEMA_CANDIDATE_FILES) {
    const response = await fetch(
      `https://api.github.com/repos/${payload.owner}/${payload.repo}/contents/${fileName}`,
      {
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${payload.githubToken}`,
        },
        cache: "no-store",
      },
    );

    if (!response.ok) {
      continue;
    }

    const body = (await response.json()) as { content?: string; encoding?: string };
    if (body.encoding !== "base64" || !body.content) {
      continue;
    }

    const raw = atob(body.content.replace(/\n/g, ""));
    const parsed = JSON.parse(raw) as RequestSchema;
    return { schema: parsed, sourceFile: fileName };
  }

  throw new Error(
    `Unable to find request schema in repository root. Tried: ${REQUEST_SCHEMA_CANDIDATE_FILES.join(", ")}`,
  );
}

export default function InferPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = Array.isArray(params.id) ? params.id[0] : params.id;
  const decodedProjectId = projectId ? decodeURIComponent(projectId) : "";

  const [prompt, setPrompt] = useState(
    "Tell me one short fact about model deployment. Answer with one short sentence.",
  );
  const [featureMode, setFeatureMode] = useState<FeatureMode>("string");
  const [arrayFeaturesInput, setArrayFeaturesInput] = useState('["Return", "only", "the", "word", "alpha."]');
  const [requestSchema, setRequestSchema] = useState<RequestSchema>(FALLBACK_SCHEMA);
  const [schemaSource, setSchemaSource] = useState("fallback schema");
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [maxNewTokens, setMaxNewTokens] = useState(96);
  const [temperature, setTemperature] = useState(0.7);
  const [topP, setTopP] = useState(0.9);
  const [enableThinking, setEnableThinking] = useState(true);
  const [timeout, setTimeout] = useState(30);
  const [status, setStatus] = useState<ProjectStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [querying, setQuerying] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [showRawJson, setShowRawJson] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function parsePredictionText(value: unknown): string {
    if (typeof value !== "string") {
      return "";
    }

    const trimmed = value.trim();
    if (!trimmed) {
      return "";
    }

    if (trimmed.includes("</think>")) {
      return trimmed.split("</think>").slice(1).join("</think>").trim();
    }

    // If only a reasoning block is present, show a clean fallback message.
    if (trimmed.startsWith("<think>")) {
      return "No final answer found in model output.";
    }

    return trimmed;
  }

  const featureModes = useMemo(() => inferFeatureModes(requestSchema), [requestSchema]);

  const previewRequestBody = useMemo(() => {
    try {
      const features = parseFeatures(featureMode, prompt, arrayFeaturesInput);
      const payload: Record<string, unknown> = { features };

      if (hasProperty(requestSchema, "max_new_tokens")) {
        payload.max_new_tokens = maxNewTokens;
      }
      if (hasProperty(requestSchema, "temperature")) {
        payload.temperature = temperature;
      }
      if (hasProperty(requestSchema, "top_p")) {
        payload.top_p = topP;
      }
      if (hasProperty(requestSchema, "enable_thinking")) {
        payload.enable_thinking = enableThinking;
      }

      return JSON.stringify(payload, null, 2);
    } catch {
      return "Invalid feature input. Fix input to preview request body.";
    }
  }, [arrayFeaturesInput, enableThinking, featureMode, maxNewTokens, prompt, requestSchema, temperature, topP]);

  useEffect(() => {
    if (!decodedProjectId) {
      setError("Project id is missing from the route");
      setLoading(false);
      return;
    }

    async function fetchStatus() {
      try {
        const data = await getProjectStatusApi(decodedProjectId);
        setStatus(data);
      } catch (e) {
        const message = e instanceof Error ? e.message : "Failed to load project status";

        if (message === "Not found") {
          try {
            const listing = await listProjectsApi();
            const projectExists = listing.projects.some((project) => project.name === decodedProjectId);

            if (projectExists) {
              setError(
                "Project exists, but backend infer routes are unavailable. "
                + "Restart backend with backend/start-dev.ps1 so SAM rebuilds updated routes.",
              );
            } else {
              setError(`Project '${decodedProjectId}' was not found in project-manager/list.`);
            }
          } catch {
            setError(
              "Backend infer routes are unavailable and project list lookup failed. "
              + "Restart backend with backend/start-dev.ps1.",
            );
          }
        } else {
          setError(message);
        }
      } finally {
        setLoading(false);
      }
    }

    fetchStatus();
  }, [decodedProjectId]);

  useEffect(() => {
    if (!decodedProjectId) {
      return;
    }

    let cancelled = false;

    async function fetchProjectRequestSchema() {
      try {
        setSchemaError(null);
        const listing = await listProjectsApi();
        const project = listing.projects.find((item) => item.name === decodedProjectId);
        if (!project) {
          throw new Error(`Project '${decodedProjectId}' not found`);
        }

        const coordinates = parseRepoCoordinates(project.repo_url || "");
        if (!coordinates || !project.github_token) {
          throw new Error("Missing GitHub repository URL or token; using fallback schema");
        }

        const { schema: parsed, sourceFile } = await fetchSchemaFromRepoRoot({
          owner: coordinates.owner,
          repo: coordinates.repo,
          githubToken: project.github_token,
        });
        if (!cancelled) {
          setRequestSchema(parsed);
          setSchemaSource(`${coordinates.owner}/${coordinates.repo}/${sourceFile}`);

          setMaxNewTokens(parsed.properties?.max_new_tokens?.default ?? 96);
          setTemperature(parsed.properties?.temperature?.default ?? 0.7);
          setTopP(parsed.properties?.top_p?.default ?? 0.9);
          setEnableThinking(parsed.properties?.enable_thinking?.default ?? true);
        }
      } catch (e) {
        if (!cancelled) {
          setRequestSchema(FALLBACK_SCHEMA);
          setSchemaSource("fallback schema");
          setSchemaError(e instanceof Error ? e.message : "Unable to load request schema");
        }
      }
    }

    fetchProjectRequestSchema();

    return () => {
      cancelled = true;
    };
  }, [decodedProjectId]);

  useEffect(() => {
    if (!featureModes.includes(featureMode) && featureModes.length > 0) {
      setFeatureMode(featureModes[0]);
    }
  }, [featureMode, featureModes]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!status?.public_ip) {
      setError("Inference URL not available");
      return;
    }

    setQuerying(true);
    setError(null);
    setResult(null);
    setShowRawJson(false);

    try {
      const features = parseFeatures(featureMode, prompt, arrayFeaturesInput);
      const requestBody: Record<string, unknown> = { features };
      if (hasProperty(requestSchema, "max_new_tokens")) {
        requestBody.max_new_tokens = maxNewTokens;
      }
      if (hasProperty(requestSchema, "temperature")) {
        requestBody.temperature = temperature;
      }
      if (hasProperty(requestSchema, "top_p")) {
        requestBody.top_p = topP;
      }
      if (hasProperty(requestSchema, "enable_thinking")) {
        requestBody.enable_thinking = enableThinking;
      }

      const data = await predictProjectApi({
        projectName: decodedProjectId,
        requestBody,
        signal: AbortSignal.timeout(timeout * 1000),
      });

      setResult(data.result || {});
    } catch (e) {
      if (e instanceof DOMException && e.name === "TimeoutError") {
        setError(`Request timed out after ${timeout}s`);
      } else {
        setError(e instanceof Error ? e.message : "Inference request failed");
      }
    } finally {
      setQuerying(false);
    }
  }

  if (loading) {
    return (
      <MonolithShell
        topLinks={[
          { label: "Projects", href: "/" },
          { label: "Deployments", href: "#" },
          { label: "Analytics", href: "#" },
        ]}
        activeTopLink="Projects"
        sideLinks={sharedSideNav}
        activeSideLink="Projects"
      >
        <div className="flex items-center justify-center py-16">
          <p className="text-sm text-white/60">Loading project status...</p>
        </div>
      </MonolithShell>
    );
  }

  if (!status || !status.public_ip) {
    return (
      <MonolithShell
        topLinks={[
          { label: "Projects", href: "/" },
          { label: "Deployments", href: "#" },
          { label: "Analytics", href: "#" },
        ]}
        activeTopLink="Projects"
        sideLinks={sharedSideNav}
        activeSideLink="Projects"
      >
        <div className="space-y-4 py-16">
          <div className="rounded-md border border-[color:var(--error)] bg-[color:var(--error)]/10 px-4 py-3">
            <p className="text-sm text-[color:var(--error)]">
              {error
                ? error
                : "Instance does not have a public IP address yet. "
                + "Please wait for the instance to fully initialize."}
            </p>
          </div>
          <button
            onClick={() => router.push("/")}
            className="text-sm font-medium text-[color:var(--on-surface-variant)] transition-colors hover:text-white"
          >
            Back to console
          </button>
        </div>
      </MonolithShell>
    );
  }

  const isServiceReady = status.service_status === "ready";
  const shortServiceStatus = status.service_status === "ready" ? "Ready" : "Starting";
  const parsedPrediction = parsePredictionText(result?.prediction);
  const parsedPredictions = Array.isArray(result?.predictions)
    ? result.predictions.map((item) => String(item)).join("\n")
    : "";

  return (
    <MonolithShell
      topLinks={[
        { label: "Projects", href: "/" },
        { label: "Deployments", href: "#" },
        { label: "Analytics", href: "#" },
      ]}
      activeTopLink="Projects"
      sideLinks={sharedSideNav}
      activeSideLink="Projects"
    >
      <div className="space-y-8 py-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-white">Query Inference Server</h1>
          <p className="mt-2 text-sm text-white/60">Project: {status.project_name}</p>
          <p className="mt-1 text-xs text-white/50">Request schema source: {schemaSource}</p>
          {schemaError ? <p className="mt-1 text-xs text-amber-400">{schemaError}</p> : null}
        </div>

        {/* Status Card */}
        <div className="rounded-lg border border-white/10 bg-[color:var(--surface-container-low)] p-6">
          <h2 className="mb-4 text-sm font-bold uppercase tracking-widest text-white/90">
            Instance Status
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-xs text-white/60">Instance Type</p>
              <p className="mt-1 text-sm font-medium text-white">{status.instance_type}</p>
            </div>
            <div>
              <p className="text-xs text-white/60">State</p>
              <p className="mt-1 text-sm font-medium text-white capitalize">{status.state}</p>
            </div>
            <div>
              <p className="text-xs text-white/60">Public IP</p>
              <p className="mt-1 text-sm font-mono text-white/85">{status.public_ip}</p>
            </div>
            <div>
              <p className="text-xs text-white/60">Service Status</p>
              <div className="mt-1 flex items-center gap-2">
                <div
                  className={`h-2 w-2 rounded-full ${isServiceReady ? "bg-green-500" : "bg-amber-500"}`}
                />
                <p className="text-sm font-medium text-white capitalize">{shortServiceStatus}</p>
              </div>
            </div>
          </div>
          {!isServiceReady && (
            <p className="mt-4 text-xs text-white/60">
              The inference service is still starting up. Please wait and refresh this page.
            </p>
          )}
        </div>

        {/* Query Form */}
        <form onSubmit={onSubmit} className="space-y-6">
          <div className="space-y-4 rounded-lg border border-white/10 bg-[color:var(--surface-container-low)] p-6">
            <h2 className="text-sm font-bold uppercase tracking-widest text-white/90">
              Query
            </h2>

            <div className="space-y-2">
              <label className="text-xs font-medium text-white/80">Features input type</label>
              <select
                value={featureMode}
                onChange={(event) => setFeatureMode(event.target.value as FeatureMode)}
                disabled={querying || !isServiceReady}
                className="w-full rounded-sm bg-[color:var(--surface-container-highest)] p-4 text-white focus:outline-none disabled:opacity-60"
              >
                {featureModes.includes("string") ? (
                  <option value="string">Single prompt string</option>
                ) : null}
                {featureModes.includes("single-array") ? (
                  <option value="single-array">Single prompt array (JSON)</option>
                ) : null}
                {featureModes.includes("batch-array") ? (
                  <option value="batch-array">Batch prompt arrays (JSON)</option>
                ) : null}
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-white/80">
                {featureMode === "string" ? "Prompt" : "Features JSON"}
              </label>
              {featureMode === "string" ? (
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  disabled={querying || !isServiceReady}
                  rows={4}
                  className="w-full rounded-sm bg-[color:var(--surface-container-highest)] p-4 text-white placeholder:text-neutral-600 focus:outline-none disabled:opacity-60"
                  placeholder="Enter your prompt..."
                />
              ) : (
                <textarea
                  value={arrayFeaturesInput}
                  onChange={(e) => setArrayFeaturesInput(e.target.value)}
                  disabled={querying || !isServiceReady}
                  rows={6}
                  className="w-full rounded-sm bg-[color:var(--surface-container-highest)] p-4 font-mono text-sm text-white placeholder:text-neutral-600 focus:outline-none disabled:opacity-60"
                  placeholder={featureMode === "single-array" ? '["Return", "only", "the", "word", "alpha."]' : '[["Return the word one."], ["Return the word two."]]'}
                />
              )}
            </div>

            {hasProperty(requestSchema, "max_new_tokens") ? (
              <div className="space-y-2">
                <label className="text-xs font-medium text-white/80">max_new_tokens</label>
                <input
                  type="number"
                  min="1"
                  value={maxNewTokens}
                  onChange={(e) => setMaxNewTokens(Math.max(1, parseInt(e.target.value, 10) || 96))}
                  disabled={querying || !isServiceReady}
                  className="w-full rounded-sm bg-[color:var(--surface-container-highest)] p-4 text-white placeholder:text-neutral-600 focus:outline-none disabled:opacity-60"
                />
              </div>
            ) : null}

            {hasProperty(requestSchema, "temperature") ? (
              <div className="space-y-2">
                <label className="text-xs font-medium text-white/80">temperature</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={temperature}
                  onChange={(e) => setTemperature(Math.max(0, parseFloat(e.target.value) || 0))}
                  disabled={querying || !isServiceReady}
                  className="w-full rounded-sm bg-[color:var(--surface-container-highest)] p-4 text-white placeholder:text-neutral-600 focus:outline-none disabled:opacity-60"
                />
              </div>
            ) : null}

            {hasProperty(requestSchema, "top_p") ? (
              <div className="space-y-2">
                <label className="text-xs font-medium text-white/80">top_p</label>
                <input
                  type="number"
                  min="0.0001"
                  max="1"
                  step="0.01"
                  value={topP}
                  onChange={(e) => setTopP(Math.max(0.0001, Math.min(1, parseFloat(e.target.value) || 0.9)))}
                  disabled={querying || !isServiceReady}
                  className="w-full rounded-sm bg-[color:var(--surface-container-highest)] p-4 text-white placeholder:text-neutral-600 focus:outline-none disabled:opacity-60"
                />
              </div>
            ) : null}

            {hasProperty(requestSchema, "enable_thinking") ? (
              <label className="flex cursor-pointer items-center gap-3 text-sm text-white/85">
                <input
                  type="checkbox"
                  checked={enableThinking}
                  onChange={(event) => setEnableThinking(event.target.checked)}
                  disabled={querying || !isServiceReady}
                  className="h-4 w-4 accent-white"
                />
                enable_thinking
              </label>
            ) : null}

            <div className="space-y-2">
              <label className="text-xs font-medium text-white/80">Request preview</label>
              <pre className="max-h-56 overflow-y-auto rounded-sm bg-[color:var(--surface-container-highest)] p-4 text-xs text-white/80">
                {previewRequestBody}
              </pre>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-white/80">Timeout (seconds)</label>
              <input
                type="number"
                min="1"
                max="600"
                value={timeout}
                onChange={(e) => setTimeout(Math.max(1, parseInt(e.target.value) || 30))}
                disabled={querying || !isServiceReady}
                className="w-full rounded-sm bg-[color:var(--surface-container-highest)] p-4 text-white placeholder:text-neutral-600 focus:outline-none disabled:opacity-60"
              />
            </div>

            <div className="flex gap-4">
              <button
                type="button"
                onClick={() => router.push("/")}
                disabled={querying}
                className="text-sm font-medium text-[color:var(--on-surface-variant)] transition-colors hover:text-white disabled:opacity-60"
              >
                Back to console
              </button>
              <button
                type="submit"
                disabled={querying || !isServiceReady}
                className="rounded-sm bg-white px-6 py-3 font-bold text-black transition hover:bg-neutral-200 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {querying ? "Querying..." : "Send Query"}
              </button>
            </div>
          </div>

          {error && (
            <div className="rounded-md border border-[color:var(--error)] bg-[color:var(--error)]/10 px-4 py-3">
              <p className="text-sm text-[color:var(--error)]">{error}</p>
            </div>
          )}

          {result && (
            <div className="space-y-4 rounded-lg border border-green-500/30 bg-green-500/10 p-6">
              <div className="flex items-center justify-between gap-4">
                <h3 className="text-sm font-bold uppercase tracking-widest text-green-400">
                  Parsed Response
                </h3>
                <label className="flex cursor-pointer items-center gap-2 text-xs text-white/80">
                  <input
                    type="checkbox"
                    checked={showRawJson}
                    onChange={(event) => setShowRawJson(event.target.checked)}
                    className="h-4 w-4 accent-white"
                  />
                  Show raw JSON
                </label>
              </div>

              <div className="rounded-md bg-[color:var(--surface-container-lowest)] p-4 text-sm leading-6 text-white/90">
                {parsedPrediction || parsedPredictions || "No parsed prediction text available."}
              </div>

              {showRawJson ? (
                <pre className="max-h-96 overflow-y-auto rounded-md bg-[color:var(--surface-container-lowest)] p-4 text-xs leading-5 text-white/80">
                  {JSON.stringify(result, null, 2)}
                </pre>
              ) : null}
            </div>
          )}
        </form>
      </div>

      <div className="pointer-events-none absolute inset-y-0 right-0 hidden w-1/3 bg-gradient-to-l from-white/10 to-transparent opacity-25 lg:block" />
    </MonolithShell>
  );
}
