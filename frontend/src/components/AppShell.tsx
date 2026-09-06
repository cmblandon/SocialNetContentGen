"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const NAV_ITEMS = [
  { href: "/", label: "Pipeline" },
  { href: "/calendar", label: "Calendario" },
  { href: "/cases", label: "Casos cubiertos" },
  { href: "/settings", label: "Configuración" },
];

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  if (pathname === "/login") {
    return <>{children}</>;
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">AD</div>
          <div className="brand-name">
            Archivo
            <span>Desclasificado</span>
          </div>
        </div>
        <nav className="primary-nav">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-item${pathname === item.href ? " active" : ""}`}
            >
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="avatar">👤</div>
          <div className="who">Editorial</div>
        </div>
      </aside>
      <main>{children}</main>
    </div>
  );
}
