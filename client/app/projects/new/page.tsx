"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { MonolithShell, sharedSideNav } from "@/app/components/monolith-shell";
import { MonolithIcon } from "@/app/components/monolith-icon";
import { autoCreateProjectApi } from "@/lib/api";

export default function CreateProjectPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [githubToken, setGithubToken] = useState("");
  const [instanceType, setInstanceType] = useState("t3.micro");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await autoCreateProjectApi({
        name: name.trim(),
        repo_url: repoUrl.trim(),
        github_token: githubToken,
        instance_type: instanceType,
      });
      router.push("/");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create project");
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
                  className="w-full rounded-sm bg-[color:var(--surface-container-highest)] p-4 text-white placeholder:text-neutral-600 focus:outline-none"
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
                    className="w-full rounded-sm bg-[color:var(--surface-container-highest)] p-4 pl-12 text-white placeholder:text-neutral-600 focus:outline-none"
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
                    className="w-full rounded-sm bg-[color:var(--surface-container-highest)] p-4 pl-12 text-white placeholder:text-neutral-600 focus:outline-none"
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
                className="w-full cursor-pointer rounded-sm bg-[color:var(--surface-container)] p-4 text-white focus:outline-none"
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
                className="text-sm font-medium text-[color:var(--on-surface-variant)] transition-colors hover:text-white"
              >
                Cancel and return to console
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-sm bg-white px-10 py-4 font-bold text-black transition hover:bg-neutral-200 md:w-auto"
              >
                {submitting ? "Creating..." : "Create Resource"}
              </button>
            </div>

            {error ? (
              <p className="text-sm text-[color:var(--error)]">{error}</p>
            ) : null}
          </form>
        </div>

        <div className="pointer-events-none absolute inset-y-0 right-0 hidden w-1/3 bg-gradient-to-l from-white/10 to-transparent opacity-25 lg:block" />
      </main>
    </MonolithShell>
  );
}
