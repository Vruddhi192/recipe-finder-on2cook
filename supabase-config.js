/* ==========================================================================
   SUPABASE CONFIG
   --------------------------------------------------------------------------
   1. Create a project at https://supabase.com (free tier is enough).
   2. Go to Project Settings -> API.
   3. Copy the "Project URL" and the "anon public" key below.
   4. Run schema.sql (in this same folder) in the Supabase SQL Editor once,
      before testing signup/login.
   ========================================================================== */

const SUPABASE_URL = "https://xqkzzztzhbhbiujhupsv.supabase.co"; // e.g. https://abcdxyz.supabase.co
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inhxa3p6enR6aGJoYml1amh1cHN2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI4MDIyNjEsImV4cCI6MjA5ODM3ODI2MX0.bCxpZUU43TR013N4Piummgf1wyBFqJ9mAIgJF-3pWSE";

// `supabase` here is the global UMD export loaded via the CDN <script> tag
// in each HTML file (see index.html / login.html / dashboard.html head).
const sb = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});
