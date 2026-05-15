import {
  useState,
  type ReactNode,
} from "react";

import Sidebar from "../components/sidebar/Sidebar";

type Props = {
  children: ReactNode;
};

export default function MainLayout({
  children,
}: Props) {
  const [mobileOpen, setMobileOpen] =
    useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-[#0e1117] text-white">
      {/* Mobile Overlay */}
      {mobileOpen && (
        <div
          onClick={() =>
            setMobileOpen(false)
          }
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
        />
      )}

      {/* Sidebar */}
      <div
        className={`fixed lg:relative z-50 h-full transition-transform duration-300 ${
          mobileOpen
            ? "translate-x-0"
            : "-translate-x-full lg:translate-x-0"
        }`}
      >
        <Sidebar
          closeMobileSidebar={() =>
            setMobileOpen(false)
          }
        />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile Topbar */}
        <div className="lg:hidden h-14 border-b border-[#30363d] flex items-center px-4 bg-[#11141a]">
          <button
            onClick={() =>
              setMobileOpen(true)
            }
            className="text-2xl"
          >
            ☰
          </button>

          <div className="ml-4 flex items-center gap-2">
            <span className="text-xl">
              🤖
            </span>

            <span className="font-semibold">
              DocTubeAI
            </span>
          </div>
        </div>

        <main className="flex-1 overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}