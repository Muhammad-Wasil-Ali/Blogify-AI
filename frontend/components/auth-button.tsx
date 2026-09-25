"use client";
import { createClient } from "@/lib/supabase/client";
export function AuthButton({ label = "Sign in with Google" }: { label?: string }) {
  async function signIn() {
    await createClient().auth.signInWithOAuth({ provider: "google", options: { redirectTo: `${window.location.origin}/auth/callback` } });
  }
  return <button onClick={signIn} className="rounded-full bg-[#d9f99d] px-5 py-3 text-sm font-semibold text-[#17211f] shadow-sm transition hover:bg-[#bef264]">{label}</button>;
}
