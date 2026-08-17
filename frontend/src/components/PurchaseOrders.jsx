import React from "react";
import { FileText, ExternalLink, CheckCircle, XCircle, Clock, ShieldAlert } from "lucide-react";

export default function PurchaseOrders({ orders = [], onApprove = () => {}, onReject = () => {} }) {
  const defaultOrders = [
    { id: "po-1025-a1", supplier_id: "mehta_traders", status: "PENDING_APPROVAL", total_value: 41000.0, created_at: "2026-08-17 12:45" },
    { id: "po-1024-b2", supplier_id: "apex_steel", status: "APPROVED", total_value: 18500.0, created_at: "2026-08-16 16:30" },
    { id: "po-1023-c3", supplier_id: "industrial_fasteners", status: "OVERDUE", total_value: 62000.0, created_at: "2026-08-14 09:15" }
  ];

  const orderList = orders.length > 0 ? orders : defaultOrders;

  const getStatusBadge = (status) => {
    switch (status) {
      case "APPROVED":
        return { label: "Approved", class: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30", icon: <CheckCircle className="w-3 h-3" /> };
      case "REJECTED":
        return { label: "Rejected", class: "bg-rose-500/20 text-rose-400 border-rose-500/30", icon: <XCircle className="w-3 h-3" /> };
      case "OVERDUE":
        return { label: "Overdue", class: "bg-amber-500/20 text-amber-400 border-amber-500/30", icon: <Clock className="w-3 h-3 animate-pulse" /> };
      default:
        return { label: "Pending Approval", class: "bg-blue-500/20 text-blue-400 border-blue-500/30", icon: <Clock className="w-3 h-3" /> };
    }
  };

  return (
    <div className="glass-panel p-5">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-semibold text-slate-200">Recent Purchase Orders & Approval Workflow</h3>
        </div>
        <span className="text-[11px] text-slate-400">{orderList.length} Active Orders</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="text-slate-400 border-b border-slate-800/80 uppercase tracking-wider text-[10px]">
              <th className="pb-2">PO ID</th>
              <th className="pb-2">Supplier</th>
              <th className="pb-2">Total Amount</th>
              <th className="pb-2">Risk Rating</th>
              <th className="pb-2">Status</th>
              <th className="pb-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50 text-slate-300">
            {orderList.map((po, idx) => {
              const badge = getStatusBadge(po.status);
              return (
                <tr key={idx} className="hover:bg-slate-800/30 transition-colors">
                  <td className="py-3 font-mono text-cyan-300 font-medium">#{po.id}</td>
                  <td className="py-3 font-medium text-slate-200 capitalize">{po.supplier_id?.replace('_', ' ')}</td>
                  <td className="py-3 font-bold text-slate-100">₹{parseFloat(po.total_value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                  <td className="py-3">
                    <span className="inline-flex items-center gap-1 text-[10px] text-purple-300 bg-purple-950/40 px-2 py-0.5 rounded border border-purple-500/30">
                      <ShieldAlert className="w-3 h-3 text-purple-400" /> Medium Risk
                    </span>
                  </td>
                  <td className="py-3">
                    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] border font-medium ${badge.class}`}>
                      {badge.icon} {badge.label}
                    </span>
                  </td>
                  <td className="py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <a
                        href={`http://localhost:7000/po-detail/${po.id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                        title="View PO Dashboard Detail"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                      {po.status === "PENDING_APPROVAL" && (
                        <>
                          <button
                            onClick={() => onApprove(po.id)}
                            className="px-2.5 py-1 rounded-lg bg-emerald-600/30 hover:bg-emerald-600/50 text-emerald-300 border border-emerald-500/40 text-[11px] font-semibold transition-all"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => onReject(po.id)}
                            className="px-2.5 py-1 rounded-lg bg-rose-600/30 hover:bg-rose-600/50 text-rose-300 border border-rose-500/40 text-[11px] font-semibold transition-all"
                          >
                            Reject
                          </button>
                        </>
                      )}
                    </div>
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
