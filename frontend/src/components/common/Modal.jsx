import { X } from "lucide-react";

export default function Modal({ title, onClose, children }) { return <div className="db-modal-overlay" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}><section className="db-modal glass-card" role="dialog" aria-modal="true" aria-label={title}><div className="db-modal-heading"><h2>{title}</h2><button type="button" aria-label="Close" onClick={onClose}><X size={21}/></button></div>{children}</section></div>; }
