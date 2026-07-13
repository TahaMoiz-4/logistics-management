/**
 * Route map. /login is public; everything else lives inside the authenticated
 * AppShell and is guarded by RequireAuth. Non-dashboard sections are
 * placeholders until their build pass.
 */
import { Navigate, Route, Routes } from "react-router-dom";
import { RequireAuth } from "@/auth/RequireAuth";
import { AppShell } from "@/components/shell/AppShell";
import { LoginPage } from "@/pages/LoginPage";
import { DashboardPage } from "@/pages/dashboard/DashboardPage";
import { OrdersPage } from "@/pages/orders/OrdersPage";
import { PlansListPage } from "@/pages/plans/PlansListPage";
import { NewPlanPage } from "@/pages/plans/NewPlanPage";
import { PlanLivePage } from "@/pages/plans/PlanLivePage";
import { PlanDetailPage } from "@/pages/plans/PlanDetailPage";
import { TrackingPage } from "@/pages/tracking/TrackingPage";
import { FleetPage } from "@/pages/fleet/FleetPage";
import { WorkersPage } from "@/pages/workers/WorkersPage";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="orders" element={<OrdersPage />} />
        <Route path="plans" element={<PlansListPage />} />
        <Route path="plans/new" element={<NewPlanPage />} />
        <Route path="plans/:id/live" element={<PlanLivePage />} />
        <Route path="plans/:id" element={<PlanDetailPage />} />
        <Route path="tracking" element={<TrackingPage />} />
        <Route path="fleet" element={<FleetPage />} />
        <Route path="workers" element={<WorkersPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
