"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { MonolithShell, sharedSideNav } from "@/app/components/monolith-shell";
import { MonolithIcon } from "@/app/components/monolith-icon";
import {
  autoCreateProjectApi,
  getProjectLogsApi,
  setupProjectApi,
} from "@/lib/api";

const TERMINAL_STATUSES = new Set(["Success", "Failed", "TimedOut", "Cancelled"]);
const SERVER_RUNNING_HOOK_PATTERN = /=== Server is running \(PID: \d+\) ===/;

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function toUtf8ByteLength(value: string) {
  return new TextEncoder().encode(value).length;
}

function isSetupRetryable(message: string) {
  const lower = message.toLowerCase();
  return (
    lower.includes("expected 'running'") ||
    lower.includes("ssm pingstatus") ||
    lower.includes("not registered in ssm") ||
    lower.includes("failed to check instance state") ||
    lower.includes("failed to check ssm status")
  );
}

export default function CreateProjectPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [githubToken, setGithubToken] = useState("");
  const [instanceType, setInstanceType] = useState("t3.micro");
  const [submitting, setSubmitting] = useState(false);
  const [streamStatus, setStreamStatus] = useState("Idle");
  const [logs, setLogs] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [createdProjectName, setCreatedProjectName] = useState<string | null>(null);
  const logsRef = useRef<HTMLPreElement | null>(null);

  useEffect(() => {
    if (!logsRef.current) {
      return;
    }
    logsRef.current.scrollTop = logsRef.current.scrollHeight;
  }, [logs]);

  function appendLogs(chunk: string) {
    setLogs((prev) => prev + chunk);
  }

  async function invokeSetupWithRetry(projectName: string) {
    const maxAttempts = 40;
    const retryDelayMs = 15000;

    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      try {
        setStreamStatus(`Setup invocation attempt ${attempt}/${maxAttempts}`);
        return await setupProjectApi(projectName);
      } catch (e) {
        const message = e instanceof Error ? e.message : "Failed to invoke setup";
        if (isSetupRetryable(message) && attempt < maxAttempts) {
          appendLogs(`[setup] Instance not ready yet (${message}). Retrying in ${retryDelayMs / 1000}s...\n`);
          await sleep(retryDelayMs);
          continue;
        }
        throw new Error(message);
      }
    }

    throw new Error("Timed out waiting for instance to become ready for setup");
  }

  async function streamSetupLogs(projectName: string, commandId: string, startByte: number) {
    const pollSeconds = 2;
    const timeoutMs = 30 * 60 * 1000;
    const deadline = Date.now() + timeoutMs;
    let nextByte = startByte;
    let idlePolls = 0;
    let lastStatus = "Pending";
    let recentOutput = "";

    while (Date.now() < deadline) {
      const payload = await getProjectLogsApi({
        projectName,
        commandId,
        startByte: nextByte,
      });

      const chunk = payload.logs || "";
      const status = payload.command_status || "Pending";

      if (chunk) {
        appendLogs(chunk);
        nextByte = payload.next_byte;
        idlePolls = 0;
        recentOutput = (recentOutput + chunk).slice(-2048);

        if (SERVER_RUNNING_HOOK_PATTERN.test(recentOutput)) {
          return {
            status: "Success",
            hookDetected: true,
            commandResponseCode: payload.command_response_code,
            commandStderr: payload.command_stderr,
          };
        }
      } else {
        idlePolls += 1;
      }

      if (status !== lastStatus) {
        appendLogs(`\n[command status: ${status}]\n`);
        lastStatus = status;
        setStreamStatus(status);
      }

      if (TERMINAL_STATUSES.has(status) && idlePolls >= 2) {
        return {
          status,
          hookDetected: false,
          commandResponseCode: payload.command_response_code,
          commandStderr: payload.command_stderr,
        };
      }

      await sleep(pollSeconds * 1000);
    }

    return {
      status: "TimedOut",
      hookDetected: false,
      commandResponseCode: null,
      commandStderr: "Client log stream timed out",
    };
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    setLogs("");
    setCreatedProjectName(null);

    try {
      const projectName = name.trim();
      appendLogs(`[auto_create] Creating project '${projectName}' with ${instanceType}...\n`);
      setStreamStatus("Creating project");

      const createResponse = await autoCreateProjectApi({
        name: projectName,
        repo_url: repoUrl.trim(),
        github_token: githubToken,
        instance_type: instanceType,
      });

      const createdName = createResponse.project?.name || projectName;
      setCreatedProjectName(createdName);
      appendLogs(`[auto_create] Created '${createdName}' on instance ${createResponse.project.instance_id}.\n`);

      appendLogs("[setup] Waiting for instance/SSM to become ready...\n");
      const setupResponse = await invokeSetupWithRetry(createdName);

      if (setupResponse.logs) {
        appendLogs(setupResponse.logs);
      }

      if (!setupResponse.command_id) {
        throw new Error("Setup response did not include command_id");
      }

      appendLogs(`\n[setup] Streaming logs for command ${setupResponse.command_id}...\n`);
      setStreamStatus("Streaming setup logs");

      const startByte = toUtf8ByteLength(setupResponse.logs || "");
      const streamResult = await streamSetupLogs(
        createdName,
        setupResponse.command_id,
        startByte,
      );

      if (streamResult.status !== "Success") {
        const stderr = streamResult.commandStderr ? `\n${streamResult.commandStderr}` : "";
        throw new Error(`Setup failed with status ${streamResult.status}.${stderr}`);
      }

      setStreamStatus("Success");
      setSuccess(`Project '${createdName}' is set up and ready.`);
      appendLogs("\n[setup] Completed successfully.\n");
      router.refresh();
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to create and setup project";
      setStreamStatus("Failed");
      setError(message);
      appendLogs(`\n[error] ${message}\n`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <MonolithShell
      topLinks={[
        { label: "Projects", href: "/" },
        { label: "Settings", href: "#" },
        { label: "Infrastructure", href: "#" },
      ]}
      activeTopLink="Projects"
      sideLinks={sharedSideNav}
      activeSideLink="Projects"
    >
      <main className="relative min-h-[calc(100vh-64px)] flex-1 overflow-hidden bg-[#131313] p-6 md:p-12 lg:p-24">
        <div className="mx-auto w-full max-w-3xl">
          <div className="mb-14">
            <h1 className="mb-4 text-4xl font-extrabold tracking-tighter text-white md:text-5xl">
              Initialize Project
            </h1>
            <p className="max-w-xl text-lg leading-relaxed text-[color:var(--on-surface-variant)]">
              Provision new compute resources and link your source control to
              the Monolith Cloud backbone.
            </p>
          </div>

          <form className="space-y-10" onSubmit={onSubmit}>
            <section className="space-y-8">
              <div>
                <label className="mb-3 block text-[10px] font-bold uppercase tracking-widest text-[color:var(--on-surface-variant)]">
                  Project Name
                </label>
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  required
                  disabled={submitting}
                  className="w-full rounded-sm bg-[color:var(--surface-container-highest)] p-4 text-white placeholder:text-neutral-600 focus:outline-none disabled:opacity-60"
                  placeholder="monolith-prod-cluster"
                />
              </div>

              <div>
                <label className="mb-3 block text-[10px] font-bold uppercase tracking-widest text-[color:var(--on-surface-variant)]">
                  GitHub Repository URL
                </label>
                <div className="relative">
                  <MonolithIcon
                    name="link"
                    className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-neutral-500"
                  />
                  <input
                    value={repoUrl}
                    onChange={(event) => setRepoUrl(event.target.value)}
                    required
                    disabled={submitting}
                    className="w-full rounded-sm bg-[color:var(--surface-container-highest)] p-4 pl-12 text-white placeholder:text-neutral-600 focus:outline-none disabled:opacity-60"
                    placeholder="https://github.com/org/repo"
                  />
                </div>
              </div>

              <div>
                <label className="mb-3 block text-[10px] font-bold uppercase tracking-widest text-[color:var(--on-surface-variant)]">
                  GitHub Access Token
                </label>
                <div className="relative">
                  <MonolithIcon
                    name="lock"
                    className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-neutral-500"
                  />
                  <input
                    type="password"
                    value={githubToken}
                    onChange={(event) => setGithubToken(event.target.value)}
                    disabled={submitting}
                    className="w-full rounded-sm bg-[color:var(--surface-container-highest)] p-4 pl-12 text-white placeholder:text-neutral-600 focus:outline-none disabled:opacity-60"
                    placeholder="ghp_********************"
                  />
                </div>
              </div>
            </section>

            <section className="rounded-lg border border-white/10 bg-[color:var(--surface-container-low)] p-6 md:p-8">
              <div className="mb-8 flex items-center gap-3">
                <MonolithIcon name="dns" className="h-5 w-5 text-white" />
                <h2 className="text-sm font-bold uppercase tracking-widest text-white">
                  Compute Resources
                </h2>
              </div>

              <label className="mb-3 block text-[10px] font-bold uppercase tracking-widest text-[color:var(--on-surface-variant)]">
                AWS Instance Type
              </label>
              <select
                value={instanceType}
                onChange={(event) => setInstanceType(event.target.value)}
                disabled={submitting}
                className="w-full cursor-pointer rounded-sm bg-[color:var(--surface-container)] p-4 text-white focus:outline-none disabled:opacity-60"
              >
                <option value="t3.micro">t3.micro (Standard General Purpose)</option>
                <option value="t3.small">t3.small (Development)</option>
                <option value="t3.medium">t3.medium (Balanced)</option>
                <option value="t3.large">t3.large (High Throughput)</option>
                <option value="m5.large">m5.large (Balanced CPU)</option>
                <option value="c5.xlarge">c5.xlarge (Compute Optimized)</option>
                <option value="g4dn.xlarge">g4dn.xlarge (GPU Acceleration)</option>
              </select>

              <div className="mt-6 flex items-start gap-3 rounded-md bg-[color:var(--surface-container-highest)]/35 p-4">
                <MonolithIcon name="info" className="h-5 w-5 text-neutral-500" />
                <p className="text-xs leading-normal text-[color:var(--on-surface-variant)]">
                  Resources will be provisioned in the default monolith-vnet-01
                  VPC. Automated health checks will be configured by default.
                </p>
              </div>
            </section>

            <div className="flex flex-col items-center justify-between gap-4 border-t border-white/5 pt-8 md:flex-row">
              <button
                type="button"
                onClick={() => router.push("/")}
                disabled={submitting}
                className="text-sm font-medium text-[color:var(--on-surface-variant)] transition-colors hover:text-white disabled:opacity-60"
              >
                Cancel and return to console
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-sm bg-white px-10 py-4 font-bold text-black transition hover:bg-neutral-200 disabled:cursor-not-allowed disabled:opacity-60 md:w-auto"
              >
                {submitting ? "Creating + Setup..." : "Create Resource"}
              </button>
            </div>

            {error ? (
              <p className="text-sm text-[color:var(--error)]">{error}</p>
            ) : null}

            {success ? (
              <div className="flex items-center justify-between gap-4 rounded-md border border-white/10 bg-[color:var(--surface-container-low)] px-4 py-3">
                <p className="text-sm text-white/85">{success}</p>
                <button
                  type="button"
                  onClick={() => router.push("/")}
                  className="rounded bg-white px-4 py-2 text-xs font-bold uppercase tracking-wide text-black"
                >
                  View Projects
                </button>
              </div>
            ) : null}
          </form>

          {(submitting || logs || createdProjectName) ? (
            <section className="mt-10 rounded-lg border border-white/10 bg-[color:var(--surface-container-low)] p-5">
              <div className="mb-3 flex items-center justify-between gap-4">
                <h3 className="text-sm font-bold uppercase tracking-widest text-white/90">
                  Setup Logs{createdProjectName ? `: ${createdProjectName}` : ""}
                </h3>
                <span className="text-xs text-white/60">Status: {streamStatus}</span>
              </div>
              <pre
                ref={logsRef}
                className="max-h-96 overflow-y-auto whitespace-pre-wrap rounded-md bg-[color:var(--surface-container-lowest)] p-4 text-xs leading-5 text-white/80"
              >
                {logs || "Waiting for setup output..."}
              </pre>
            </section>
          ) : null}
        </div>

        <div className="pointer-events-none absolute inset-y-0 right-0 hidden w-1/3 bg-gradient-to-l from-white/10 to-transparent opacity-25 lg:block" />
      </main>
    </MonolithShell>
  );
}
