import React from "react";
import Sidebar from "@/app/components/Sidebar/Sidebar";


export default function AdminLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="container">
      <Sidebar />
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}