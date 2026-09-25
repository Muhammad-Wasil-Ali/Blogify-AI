import type { ButtonHTMLAttributes } from "react";
export function Button({ className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement>) { return <button className={`rounded-xl bg-violet-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-violet-700 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-50 ${className}`} {...props} />; }
