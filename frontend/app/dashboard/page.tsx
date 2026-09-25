import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import DashboardClient from "@/components/dashboard-client";
export default async function DashboardPage() { const { data: { user } } = await (await createClient()).auth.getUser(); if (!user) redirect("/login"); return <DashboardClient />; }
