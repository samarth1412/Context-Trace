import { AppShell } from "@/components/dashboard/app-shell";
import { LoadingPanel } from "@/components/dashboard/loading-panel";

export default function TracesLoading() {
  return (
    <AppShell>
      <LoadingPanel />
    </AppShell>
  );
}
