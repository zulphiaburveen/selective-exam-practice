-- Run once in Supabase SQL Editor BEFORE deploying the Python changes.
-- The original answer keys and existing attempt data remain unchanged.
ALTER TABLE public.attempts
ADD COLUMN IF NOT EXISTS option_order jsonb NOT NULL DEFAULT '{}'::jsonb;
