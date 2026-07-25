-- Add per-test-case AI token tracking fields
ALTER TABLE "TestCase" ADD COLUMN "ai_tokens_used" INTEGER NOT NULL DEFAULT 0;
ALTER TABLE "TestCase" ADD COLUMN "ai_cost_usd" DOUBLE PRECISION NOT NULL DEFAULT 0;

-- Add cost field to TestSuite (ai_tokens_used already existed)
ALTER TABLE "TestSuite" ADD COLUMN "ai_cost_usd" DOUBLE PRECISION NOT NULL DEFAULT 0;
