import { NavLink, Route, Routes } from "react-router-dom";

import Compliance from "./pages/Compliance";
import ContractDetail from "./pages/ContractDetail";
import DriftMetrics from "./pages/DriftMetrics";
import ImpactMap from "./pages/ImpactMap";
import Overview from "./pages/Overview";

const navItems = [
  { to: "/", label: "Overview" },
  { to: "/drift", label: "Drift" },
  { to: "/compliance", label: "Compliance" },
  { to: "/impact", label: "Impact Map" },
];

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center gap-8">
          <span className="text-xl font-bold text-indigo-600">Sraosha</span>
          <div className="flex gap-4">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-indigo-50 text-indigo-700"
                      : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/contracts/:id" element={<ContractDetail />} />
          <Route path="/drift" element={<DriftMetrics />} />
          <Route path="/compliance" element={<Compliance />} />
          <Route path="/impact" element={<ImpactMap />} />
        </Routes>
      </main>
    </div>
  );
}
