import { useState } from "react"
import PageHeader from "@/components/shared/PageHeader"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Check, Zap, Rocket, Building2, ArrowRight, CreditCard, CalendarDays } from "lucide-react"

const plans = [
  {
    id: "starter",
    name: "Starter",
    description: "For individual developers getting started.",
    monthlyPrice: 0,
    yearlyPrice: 0,
    icon: Zap,
    iconColor: "text-muted-foreground",
    iconBg: "bg-muted",
    current: true,
    features: ["1 API project", "100 test runs/mo", "Basic reporting", "Community support", "Swagger import"],
  },
  {
    id: "pro",
    name: "Pro",
    description: "For growing teams with advanced needs.",
    monthlyPrice: 29,
    yearlyPrice: 290,
    icon: Rocket,
    iconColor: "text-muted-foreground",
    iconBg: "bg-muted",
    popular: true,
    features: [
      "Unlimited projects",
      "5,000 test runs/mo",
      "Security scanning (OWASP)",
      "CI/CD integrations",
      "Priority support",
      "Team collaboration (10 seats)",
      "Custom environments",
      "Webhook notifications",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    description: "For large organizations at scale.",
    monthlyPrice: 99,
    yearlyPrice: 990,
    icon: Building2,
    iconColor: "text-muted-foreground",
    iconBg: "bg-muted",
    features: [
      "Everything in Pro",
      "Unlimited test runs",
      "SSO & RBAC",
      "Custom SLA",
      "Dedicated account manager",
      "On-prem deployment",
      "Audit logs & compliance",
      "24/7 phone & chat support",
    ],
  },
]

const PlansPage = () => {
  const [billing, setBilling] = useState("monthly")

  return (
    <div className="space-y-6 p-6">
      {/* Header + billing toggle */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <PageHeader title="Subscription Plans" description="Choose the plan that fits your team." />

        <div className="inline-flex items-center gap-1 rounded-full border border-border/50 bg-muted/40 p-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setBilling("monthly")}
            className={`flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-medium transition-all duration-200 ${
              billing === "monthly"
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            }`}
          >
            <CreditCard className="h-3.5 w-3.5" /> Monthly
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setBilling("yearly")}
            className={`flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-medium transition-all duration-200 ${
              billing === "yearly"
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            }`}
          >
            <CalendarDays className="h-3.5 w-3.5" /> Yearly
            <Badge variant="outline" className="ml-1 px-1.5 py-0 text-[10px] border-primary/30 text-primary">-17%</Badge>
          </Button>
        </div>
      </div>

      {/* Plan cards */}
      <div className="grid gap-6 lg:grid-cols-3">
        {plans.map((plan) => {
          const Icon = plan.icon
          const price = billing === "monthly" ? plan.monthlyPrice : plan.yearlyPrice
          const period = billing === "monthly" ? "/mo" : "/yr"
          return (
            <Card
              key={plan.id}
              className={`relative flex flex-col rounded-xl border border-border/50 shadow-sm hover:shadow-md transition-all duration-200 ${
                plan.popular ? "border-primary/50 ring-1 ring-primary/10" : ""
              } ${plan.current ? "ring-1 ring-border/50" : ""}`}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <Badge variant="secondary" className="text-[11px] border border-primary/30 bg-primary/10 text-primary shadow-sm">
                    Most Popular
                  </Badge>
                </div>
              )}
              <CardContent className="flex flex-1 flex-col p-6 pt-8">
                <div className="flex items-center gap-3 mb-3">
                  <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${plan.iconBg}`}>
                    <Icon className={`h-5 w-5 ${plan.iconColor}`} />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-foreground">{plan.name}</h3>
                    {plan.current ? (
                      <Badge variant="outline" className="text-[10px] border-border/50 text-muted-foreground">
                        Current
                      </Badge>
                    ) : null}
                  </div>
                </div>
                <p className="text-sm text-muted-foreground mb-4">{plan.description}</p>

                <div className="mb-5 pb-5 border-b border-border/50">
                  {price === 0 ? (
                    <span className="text-3xl font-semibold text-foreground">Free</span>
                  ) : (
                    <>
                      <span className="text-3xl font-semibold text-foreground">${price}</span>
                      <span className="text-muted-foreground ml-1 text-sm">{period}</span>
                    </>
                  )}
                  {billing === "yearly" && price > 0 && (
                    <p className="mt-1 text-xs text-muted-foreground">${Math.round(price / 12)}/mo billed annually</p>
                  )}
                </div>

                <ul className="flex-1 space-y-2.5 mb-6">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm text-muted-foreground">
                      <Check className="h-4 w-4 mt-0.5 shrink-0 text-muted-foreground" />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>

                <Button
                  className="w-full gap-2 transition-all duration-200"
                  variant={plan.current ? "outline" : plan.popular ? "default" : "outline"}
                  disabled={plan.current}
                >
                  {plan.current ? "Current Plan" : <>{plan.popular ? "Upgrade to Pro" : "Upgrade"} <ArrowRight className="h-4 w-4" /></>}
                </Button>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}

export default PlansPage
