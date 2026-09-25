import Sidebar from "@/components/Sidebar";
export default function ProfileLayout({ children }: { children: React.ReactNode }) { return <div className="min-h-screen bg-slate-50"><Sidebar /><main className="min-h-screen lg:pl-64">{children}</main></div>; }
