import { createClient } from "@/lib/supabase/client";

export type Blog = { id: string; topic: string; title: string; intro_summary: string; content: string; created_at: string };
export type DownloadFormat = "markdown" | "pdf";
const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

async function apiFetch(path: string, init: RequestInit = {}) {
  const { data } = await createClient().auth.getSession();
  if (!data.session?.access_token) {
    if (typeof window !== "undefined") window.location.assign("/login");
    throw new Error("Please sign in to continue.");
  }
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${data.session.access_token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      await createClient().auth.signOut();
      window.location.assign("/login");
    }
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail || `Request failed (${response.status})`);
  }
  return response;
}

export async function generateBlog(topic: string) {
  const response = await apiFetch("/generate-blog", { method: "POST", body: JSON.stringify({ topic }) });
  return response.json() as Promise<Blog>;
}
export async function generateBlogStream(topic: string, onEvent: (event: { node: string; status: string; message: string; result?: Blog }) => void) {
  const response = await apiFetch("/generate-blog/stream", { method: "POST", body: JSON.stringify({ topic }) });
  if (!response.body) throw new Error("Streaming is not supported by this browser.");
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
  while (true) { const { value, done } = await reader.read(); buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done }); const events = buffer.split("\n\n"); buffer = events.pop() ?? ""; for (const chunk of events) { const line = chunk.split("\n").find((item) => item.startsWith("data: ")); if (line) onEvent(JSON.parse(line.slice(6))); } if (done) break; }
  if (buffer.trim()) { const line = buffer.split("\n").find((item) => item.startsWith("data: ")); if (line) onEvent(JSON.parse(line.slice(6))); }
}
export async function listBlogs() { return (await apiFetch("/blogs")).json() as Promise<Blog[]>; }
export async function getBlog(id: string) { return (await apiFetch(`/blogs/${encodeURIComponent(id)}`)).json() as Promise<Blog>; }
export async function deleteBlog(id: string) { await apiFetch(`/blogs/${encodeURIComponent(id)}`, { method: "DELETE" }); }
export function downloadUrl(id: string, format: DownloadFormat) { return `${API_URL}/blogs/${encodeURIComponent(id)}/download/${format}`; }
export const markdownDownloadUrl = (id: string) => downloadUrl(id, "markdown");
export const pdfDownloadUrl = (id: string) => downloadUrl(id, "pdf");
export async function downloadBlogFile(id: string, format: DownloadFormat) {
  const response = await apiFetch(`/blogs/${encodeURIComponent(id)}/download/${format}`);
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] ?? `blog.${format === "pdf" ? "pdf" : "md"}`;
  return { blob: await response.blob(), filename };
}
