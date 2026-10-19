-- Supabase exposes every table in the public schema through its REST API.
-- With RLS on and no policies, that API can read nothing; the backend connects
-- as the table owner, which bypasses RLS, so it is unaffected.
-- Migrations re-run on every `npm run migrate`, so tables added later are covered too.
DO $$
DECLARE t record;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tablename);
  END LOOP;
END $$;
