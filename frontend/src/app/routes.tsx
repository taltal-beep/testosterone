import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "./AppShell";
import { NotFoundPage } from "./NotFoundPage";
import { ComparePage } from "../features/compare/ComparePage";
import { CycleDetailPage } from "../features/cycles/CycleDetailPage";
import { CyclesPage } from "../features/cycles/CyclesPage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { QuickRunPage } from "../features/execution/QuickRunPage";
import { HistoryPage } from "../features/history/HistoryPage";
import { RunDetailPage } from "../features/run-detail/RunDetailPage";
import { AIIntegrationSettingsPage } from "../features/settings/AIIntegrationSettingsPage";

export const routes = [
  {
    path: "/",
    element: <AppShell />,
    children: [
      {
        index: true,
        element: <DashboardPage />
      },
      {
        path: "cycles",
        element: <CyclesPage />
      },
      {
        path: "cycles/:name",
        element: <CycleDetailPage />
      },
      {
        path: "runs",
        element: <HistoryPage />
      },
      {
        path: "runs/:runId",
        element: <RunDetailPage />
      },
      {
        path: "compare",
        element: <ComparePage />
      },
      {
        path: "quick-run",
        element: <QuickRunPage />
      },
      {
        path: "settings/ai",
        element: <AIIntegrationSettingsPage />
      },
      {
        path: "*",
        element: <NotFoundPage />
      }
    ]
  }
];

export const router = createBrowserRouter(routes, {
  // The static demo is served from a project subpath on GitLab Pages, so the
  // router has to resolve routes against Vite's base instead of "/".
  basename: import.meta.env.BASE_URL
});
