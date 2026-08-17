import React from "react";
import { Package, AlertCircle, CheckCircle2 } from "lucide-react";

export default function InventoryTable({ items = [] }) {
  const defaultItems = [
    { sku: "PLT-A36-6", item_name: "Steel Plate A36 6mm", warehouse_id: "WH-NORTH", stock_level: 75, reorder_point: 100, unit_of_measure: "Sheets" },
    { sku: "SCR-M8-001", item_name: "Hex Bolt M8 50mm", warehouse_id: "WH-SOUTH", stock_level: 4500, reorder_point: 2000, unit_of_measure: "Units" },
    { sku: "ALU-6061-T6", item_name: "Aluminum Bar 6061-T6", warehouse_id: "WH-WEST", stock_level: 45, reorder_point: 50, unit_of_measure: "Bars" }
  ];

  const dataList = items.length > 0 ? items : defaultItems;

  return (
    <div className="glass-panel p-5">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
        <div className="flex items-center gap-2">
          <Package className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-semibold text-slate-200">Real-Time Inventory & Stock Alerts</h3>
        </div>
        <span className="text-[11px] text-slate-400">{dataList.length} Items Monitored</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="text-slate-400 border-b border-slate-800/80 uppercase tracking-wider text-[10px]">
              <th className="pb-2">SKU</th>
              <th className="pb-2">Item Description</th>
              <th className="pb-2">Warehouse</th>
              <th className="pb-2">Stock Level</th>
              <th className="pb-2">Reorder Point</th>
              <th className="pb-2">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50 text-slate-300">
            {dataList.map((item, idx) => {
              const isLow = item.stock_level <= item.reorder_point;
              return (
                <tr key={idx} className="hover:bg-slate-800/30 transition-colors">
                  <td className="py-2.5 font-mono text-cyan-300 font-medium">{item.sku}</td>
                  <td className="py-2.5 font-medium text-slate-200">{item.item_name || "Industrial Component"}</td>
                  <td className="py-2.5 text-slate-400">{item.warehouse_id}</td>
                  <td className="py-2.5 font-bold text-slate-100">{item.stock_level?.toLocaleString()}</td>
                  <td className="py-2.5 text-slate-400">{item.reorder_point?.toLocaleString()}</td>
                  <td className="py-2.5">
                    {isLow ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] bg-amber-500/20 text-amber-400 border border-amber-500/30 font-medium">
                        <AlertCircle className="w-3 h-3" /> Reorder Flag
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-medium">
                        <CheckCircle2 className="w-3 h-3" /> Healthy Stock
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
