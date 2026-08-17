import React from "react";
import { Package, ShoppingBag, ShieldAlert, AlertTriangle } from "lucide-react";

export default function DashboardStats({ analytics = {} }) {
  const stats = [
    {
      title: "Total Inventory SKUs",
      value: analytics.total_skus || "18",
      sub: "Across 3 warehouses",
      icon: <Package className="w-5 h-5 text-cyan-400" />,
      border: "border-cyan-500/20"
    },
    {
      title: "Active Purchase Orders",
      value: analytics.active_orders || "12",
      sub: "Total PO Value: ₹4,82,500",
      icon: <ShoppingBag className="w-5 h-5 text-emerald-400" />,
      border: "border-emerald-500/20"
    },
    {
      title: "Low Stock Items",
      value: analytics.low_stock_count || "3",
      sub: "Requires urgent PO draft",
      icon: <AlertTriangle className="w-5 h-5 text-amber-400" />,
      border: "border-amber-500/20"
    },
    {
      title: "Supplier Risk Score",
      value: "Low-Med",
      sub: "94.2% On-Time Delivery",
      icon: <ShieldAlert className="w-5 h-5 text-purple-400" />,
      border: "border-purple-500/20"
    }
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {stats.map((item, idx) => (
        <div key={idx} className={`glass-panel p-4 flex items-center justify-between border ${item.border}`}>
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">{item.title}</p>
            <h3 className="text-2xl font-bold text-slate-100 mt-1">{item.value}</h3>
            <p className="text-[11px] text-slate-500 mt-1">{item.sub}</p>
          </div>
          <div className="p-3 rounded-xl bg-slate-800/60 border border-slate-700/50">
            {item.icon}
          </div>
        </div>
      ))}
    </div>
  );
}
