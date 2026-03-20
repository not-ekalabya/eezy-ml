import Link from "next/link";
import { MonolithShell, sharedSideNav } from "@/app/components/monolith-shell";
import { projects } from "@/app/components/monolith-data";
import { MonolithIcon } from "@/app/components/monolith-icon";

export default function Home() {
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
      <main className="min-h-[calc(100vh-64px)] flex-1 bg-[#131313] p-6 md:p-12">
        <div className="mx-auto max-w-6xl">
          <div className="mb-12 flex flex-col justify-between gap-6 md:flex-row md:items-end">
            <div>
              <h1 className="mb-2 text-4xl font-extrabold tracking-tighter text-white">
                Projects
              </h1>
              <p className="text-sm text-[color:var(--on-surface-variant)]">
                Manage and scale your cloud infrastructure modules.
              </p>
            </div>
            <Link
              href="/projects/new"
              className="flex w-full items-center justify-center gap-2 rounded-md bg-white px-6 py-3 font-medium text-black transition hover:bg-neutral-200 md:w-auto"
            >
              <MonolithIcon name="add" className="h-5 w-5" />
              Create New Project
            </Link>
          </div>

          <div className="space-y-2">
            <div className="grid grid-cols-12 px-4 py-3 text-[11px] font-bold uppercase tracking-[0.1em] text-white/55 md:px-6">
              <div className="col-span-6">Name</div>
              <div className="col-span-2">Status</div>
              <div className="col-span-2">Created Date</div>
              <div className="col-span-2 text-right">Actions</div>
            </div>

            {projects.map((project) => (
              <div
                key={project.id}
                className="group grid grid-cols-12 items-center rounded-lg bg-[color:var(--surface-container-low)] px-4 py-5 transition hover:bg-[color:var(--surface-container)] md:px-6"
              >
                <div className="col-span-6 flex items-center gap-3 md:gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded border border-white/10 bg-[color:var(--surface-container-highest)]">
                    <MonolithIcon
                      name={project.icon}
                      className="h-5 w-5 text-[color:var(--on-surface-variant)]"
                    />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-white">{project.id}</p>
                    <p className="text-[11px] text-[color:var(--on-surface-variant)]">
                      {project.type}
                    </p>
                  </div>
                </div>
                <div className="col-span-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={[
                        "h-2 w-2 rounded-full",
                        project.status === "Active"
                          ? "animate-pulse bg-white"
                          : "bg-[color:var(--outline-variant)]",
                      ].join(" ")}
                    />
                    <span
                      className={[
                        "text-xs font-medium",
                        project.status === "Active"
                          ? "text-white"
                          : "text-[color:var(--on-surface-variant)]",
                      ].join(" ")}
                    >
                      {project.status}
                    </span>
                  </div>
                </div>
                <div className="col-span-2 text-xs text-[color:var(--on-surface-variant)]">
                  {project.createdDate}
                </div>
                <div className="col-span-2 flex justify-end gap-2 opacity-45 transition group-hover:opacity-100">
                  <Link
                    href={`/projects/${project.id}/edit`}
                    className="rounded p-2 text-[color:var(--on-surface-variant)] transition hover:bg-[color:var(--surface-bright)] hover:text-white"
                  >
                    <MonolithIcon name="edit" className="h-[18px] w-[18px]" />
                  </Link>
                  <Link
                    href={`/projects/${project.id}/delete`}
                    className="rounded p-2 text-[color:var(--on-surface-variant)] transition hover:bg-[color:var(--error-container)]/20 hover:text-[color:var(--error)]"
                  >
                    <MonolithIcon name="delete" className="h-[18px] w-[18px]" />
                  </Link>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-16 rounded-xl border border-dashed border-white/20 bg-[color:var(--surface-container-lowest)] p-10 text-center">
            <MonolithIcon
              name="dashboard_customize"
              className="mx-auto mb-3 h-10 w-10 text-[color:var(--on-surface-variant)]"
            />
            <h3 className="font-medium text-white">Ready for more?</h3>
            <p className="mb-6 mt-1 text-sm text-[color:var(--on-surface-variant)]">
              Create a new architectural module to expand your monolith.
            </p>
            <button className="border border-white/25 px-6 py-2 text-xs font-bold uppercase tracking-widest text-white transition hover:bg-[color:var(--surface-container)]">
              Quick Start Guide
            </button>
          </div>
        </div>
      </main>
    </MonolithShell>
  );
}
