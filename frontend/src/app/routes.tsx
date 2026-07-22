import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppShell } from "./AppShell";
import { ComparePage } from "../features/compare/ComparePage";
import { CycleDetailPage } from "../features/cycles/CycleDetailPage";
import { CyclesPage } from "../features/cycles/CyclesPage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { ExecutionPage } from "../features/execution/ExecutionPage";
import { HistoryPage } from "../features/history/HistoryPage";
import { RunDetailPage } from "../features/run-detail/RunDetailPage";
import { AIIntegrationSettingsPage } from "../features/settings/AIIntegrationSettingsPage";

export const router = createBrowserRouter([
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
        path: "advanced/execution",
        element: <ExecutionPage />
      },
      {
        path: "settings/ai",
        element: <AIIntegrationSettingsPage />
      },
      // Legacy paths kept as redirects so old bookmarks don't break.
      {
        path: "history",
        element: <Navigate to="/runs" replace />
      },
      {
        path: "runner",
        element: <Navigate to="/cycles" replace />
      },
      {
        path: "execution",
        element: <Navigate to="/advanced/execution" replace />
      }
    ]
  }
]);
