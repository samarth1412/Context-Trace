import { Check } from "lucide-react";
import Link from "next/link";
import { SiteShell } from "@/components/site/site-shell";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";

const plans = [
  {
    name: "Local",
    price: "$0",
    description: "For private development, local reports, and SDK evaluation.",
    features: ["Local trace store", "HTML reports", "CLI evals", "No hosted backend required"]
  },
  {
    name: "Team",
    price: "Soon",
    description: "For shared projects, hosted traces, dashboards, and eval history.",
    features: ["Shared projects", "Hosted dashboard", "Eval set summaries", "External RAG API testing"]
  },
  {
    name: "Enterprise",
    price: "Custom",
    description: "For regulated teams that need private deployment and deeper controls.",
    features: ["VPC or self-hosted", "Custom retention", "Provider controls", "Security review support"]
  }
];

export default function PricingPage() {
  return (
    <SiteShell>
      <main className="mx-auto max-w-7xl px-4 py-12 md:px-7">
        <header className="mb-8 max-w-3xl">
          <div className="text-sm font-semibold uppercase text-primary">Pricing</div>
          <h1 className="mt-2 text-4xl font-semibold tracking-normal">Start locally. Scale when teams need shared reliability reports.</h1>
          <p className="mt-4 text-base leading-7 text-muted-foreground">
            ContextTrace is SDK-first. The local workflow stays useful even before hosted plans are
            enabled.
          </p>
        </header>
        <div className="grid gap-4 lg:grid-cols-3">
          {plans.map((plan) => (
            <Card key={plan.name} className="flex flex-col">
              <CardHeader>
                <CardTitle>{plan.name}</CardTitle>
              </CardHeader>
              <div className="text-3xl font-semibold">{plan.price}</div>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">{plan.description}</p>
              <div className="mt-5 grid gap-3">
                {plan.features.map((feature) => (
                  <div key={feature} className="flex items-center gap-2 text-sm">
                    <Check className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                    {feature}
                  </div>
                ))}
              </div>
            </Card>
          ))}
        </div>
        <div className="mt-8 rounded-lg border bg-white p-5">
          <h2 className="text-xl font-semibold tracking-normal">Not ready for hosted mode?</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Use `ContextTrace(mode="local")` for file-backed traces and exportable HTML reports.
          </p>
          <Link
            href="/docs/quickstart"
            className="mt-4 inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
          >
            Install SDK
          </Link>
        </div>
      </main>
    </SiteShell>
  );
}

