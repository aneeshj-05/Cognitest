import { useState } from "react"
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Check, Zap, Rocket, Building2, ArrowRight, CreditCard, CalendarDays } from "lucide-react"

const plans = [
  {
    id: "starter",
    name: "Starter",
    description: "For individual developers getting started with API testing.",
    monthlyPrice: 0,
    yearlyPrice: 0,
    icon: Zap,
    iconColor: "text-emerald-500",
    iconBg: "bg-emerald-500/10",
    features: [
      "5 API projects",
      "100 test runs per month",
      "Basic pass/fail reporting",
      "Community support",
      "Swagger / OpenAPI import",
    ],
    cta: "Get Started Free",
  },
  {
    id: "pro",
    name: "Pro",
    description: "For growing teams that need advanced testing and security.",
    monthlyPrice: 29,
    yearlyPrice: 290,
    icon: Rocket,
    iconColor: "text-blue-500",
    iconBg: "bg-blue-500/10",
    popular: true,
    features: [
      "Unlimited projects",
      "5,000 test runs per month",
      "OWASP security scanning",
      "CI/CD pipeline integrations",
      "Priority email support",
      "Team collaboration (10 seats)",
      "Custom environments",
      "Webhook notifications",
    ],
    cta: "Start Pro Trial",
  },
  {
    id: "enterprise",
    name: "Enterprise",
    description: "For large organizations that need full control and compliance.",
    monthlyPrice: 99,
    yearlyPrice: 990,
    icon: Building2,
    iconColor: "text-amber-500",
    iconBg: "bg-amber-500/10",
    features: [
      "Everything in Pro",
      "Unlimited test runs",
      "SSO & role-based access",
      "Custom SLA agreement",
      "Dedicated account manager",
      "On-premise deployment option",
      "Audit logs & compliance",
      "24/7 phone & chat support",
    ],
    cta: "Contact Sales",
  },
]

const faqs = [
  { q: "Can I switch plans later?", a: "Yes. You can upgrade, downgrade, or cancel your plan at any time from the dashboard." },
  { q: "Is there a free trial for Pro?", a: "Yes — Pro comes with a 14-day free trial. No credit card required to start." },
  { q: "What payment methods do you accept?", a: "We accept all major credit cards, PayPal, and wire transfer for Enterprise plans." },
  { q: "Do you offer discounts for startups?", a: "Yes! We have a startup program with 50% off Pro for the first year. Contact us for details." },
]

const PricingPage = () => {
  const [billing, setBilling] = useState("monthly")

  return (
    <div className="min-h-screen bg-background">
      {/* Hero */}
      <section className="py-16 sm:py-24 text-center px-4">
        <Badge className="mb-4 bg-emerald-500/10 text-emerald-600 border-emerald-500/20 text-xs">
          Simple, transparent pricing
        </Badge>
        <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-foreground mb-4">
          Choose the right plan for your team
        </h1>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto mb-8">
          Start free and scale as you grow. Every plan includes AI-powered test generation, detailed reporting, and Swagger/OpenAPI support.
        </p>

        {/* Billing toggle */}
        <div className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/40 p-1">
          <button
            onClick={() => setBilling("monthly")}
            className={`flex items-center gap-1.5 rounded-full px-5 py-2 text-sm font-medium transition-all ${
              billing === "monthly"
                ? "bg-black text-white shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <CreditCard className="h-3.5 w-3.5" /> Monthly
          </button>
          <button
            onClick={() => setBilling("yearly")}
            className={`flex items-center gap-1.5 rounded-full px-5 py-2 text-sm font-medium transition-all ${
              billing === "yearly"
                ? "bg-black text-white shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <CalendarDays className="h-3.5 w-3.5" /> Yearly
            <Badge variant="outline" className="ml-1 text-[10px] border-emerald-500/40 text-emerald-600 py-0 px-1.5">
              Save 17%
            </Badge>
          </button>
        </div>
      </section>

      {/* Plan cards */}
      <section className="max-w-6xl mx-auto px-4 pb-16">
        <div className="grid gap-8 lg:grid-cols-3">
          {plans.map((plan) => {
            const Icon = plan.icon
            const price = billing === "monthly" ? plan.monthlyPrice : plan.yearlyPrice
            const period = billing === "monthly" ? "/mo" : "/yr"
            return (
              <Card
                key={plan.id}
                className={`relative flex flex-col border transition-all hover:shadow-xl ${
                  plan.popular
                    ? "border-black shadow-lg scale-[1.02] ring-1 ring-black/10"
                    : "border-border/60 hover:border-border"
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Badge className="bg-black text-white text-[11px] shadow-lg px-3">
                      Most Popular
                    </Badge>
                  </div>
                )}
                <CardContent className="flex flex-1 flex-col p-8 pt-10">
                  {/* Icon + name */}
                  <div className="flex items-center gap-3 mb-4">
                    <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${plan.iconBg}`}>
                      <Icon className={`h-6 w-6 ${plan.iconColor}`} />
                    </div>
                    <div>
                      <h3 className="text-xl font-bold text-foreground">{plan.name}</h3>
                    </div>
                  </div>

                  <p className="text-sm text-muted-foreground mb-6 leading-relaxed">{plan.description}</p>

                  {/* Price */}
                  <div className="mb-6 pb-6 border-b border-border/40">
                    {price === 0 ? (
                      <span className="text-4xl font-extrabold text-foreground">Free</span>
                    ) : (
                      <>
                        <span className="text-4xl font-extrabold text-foreground">${price}</span>
                        <span className="text-muted-foreground ml-1.5 text-base">{period}</span>
                      </>
                    )}
                    {billing === "yearly" && price > 0 && (
                      <p className="mt-1.5 text-xs text-emerald-600 font-medium">
                        ${Math.round(price / 12)}/mo billed annually
                      </p>
                    )}
                  </div>

                  {/* Features */}
                  <ul className="flex-1 space-y-3 mb-8">
                    {plan.features.map((f) => (
                      <li key={f} className="flex items-start gap-2.5 text-sm text-muted-foreground">
                        <Check className="h-4 w-4 mt-0.5 shrink-0 text-emerald-500" />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>

                  {/* CTA */}
                  <Link to="/login">
                    <Button
                      className={`w-full gap-2 text-sm font-semibold ${
                        plan.popular
                          ? "bg-black hover:bg-black/85 text-white"
                          : ""
                      }`}
                      variant={plan.popular ? "default" : "outline"}
                      size="lg"
                    >
                      {plan.cta} <ArrowRight className="h-4 w-4" />
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            )
          })}
        </div>
      </section>

      {/* FAQ */}
      <section className="max-w-3xl mx-auto px-4 pb-24">
        <h2 className="text-2xl font-bold text-center mb-8">Frequently Asked Questions</h2>
        <div className="space-y-4">
          {faqs.map((item, i) => (
            <div key={i} className="rounded-xl border border-border/60 p-5">
              <h3 className="font-semibold text-foreground mb-1.5">{item.q}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{item.a}</p>
            </div>
          ))}
        </div>
        <div className="text-center mt-10">
          <p className="text-muted-foreground text-sm mb-4">Have more questions?</p>
          <Link to="/contact">
            <Button variant="outline" className="gap-2">
              Contact Us <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </div>
      </section>
    </div>
  )
}

export default PricingPage
