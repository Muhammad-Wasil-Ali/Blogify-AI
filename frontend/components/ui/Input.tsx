import type { InputHTMLAttributes } from "react";
export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) { return <input className={`w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-violet-500 focus:ring-4 focus:ring-violet-100 ${className}`} {...props} />; }
