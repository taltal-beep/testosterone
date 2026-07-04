import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../../lib/api-client";
import { Badge, Button, Card, EmptyState, PageHeader, Spinner } from "../../components/ui";
import { MuscleShrug } from "../../components/mascot";

export function CyclesPage() {
  const navigate = useNavigate();
  const query = useQuery({ queryKey: ["cycles"], queryFn: () => apiClient.listCycles() });

  if (query.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-300">
        <Spinner /> Loading cycles…
      </div>
    );
  }

  if (query.isError) {
    return (
      <EmptyState
        mascot={<MuscleShrug />}
        title="No testosterone.yaml found"
        message={
          <>
            The engine couldn&apos;t resolve a config file. Create one at the repo root with{" "}
            <code className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-xs text-brand-300">
              testo config init
            </code>{" "}
            and reload.
          </>
        }
      />
    );
  }

  const cycles = query.data?.items ?? [];

  return (
    <section>
      <PageHeader
        title="Cycles"
        subtitle={
          query.data?.config_path
            ? `Defined in ${query.data.config_path}`
            : "Every cycle defined in your configuration."
        }
      />
      {cycles.length === 0 ? (
        <EmptyState
          mascot={<MuscleShrug />}
          title="No cycles defined yet"
          message="Add a cycle to testosterone.yaml to see it here."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {cycles.map((cycle) => (
            <Card key={cycle.name} className="flex flex-col justify-between gap-3">
              <div>
                <Link
                  to={`/cycles/${encodeURIComponent(cycle.name)}`}
                  className="font-mono text-sm font-semibold text-brand-300 hover:text-brand-400 hover:underline"
                >
                  {cycle.name}
                </Link>
                <p className="mt-1.5 line-clamp-2 text-sm text-ink-300">
                  {cycle.description ?? "No description."}
                </p>
              </div>
              <div className="flex items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge>
                    {cycle.stage_count} stage{cycle.stage_count === 1 ? "" : "s"}
                  </Badge>
                  {cycle.equipment.map((eq) => (
                    <Badge key={eq} tone="brand">
                      {eq}
                    </Badge>
                  ))}
                </div>
                <Button
                  size="sm"
                  onClick={() => navigate(`/cycles/${encodeURIComponent(cycle.name)}?run=1`)}
                >
                  Run
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}
