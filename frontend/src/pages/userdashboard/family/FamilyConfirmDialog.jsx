import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

export default function FamilyConfirmDialog({ title, children, confirmLabel, confirmation, onConfirm, onClose }) {
  const dialog = useRef(null);
  const busy = useRef(false);
  const close = useRef(onClose);
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { close.current = onClose; }, [onClose]);
  useEffect(() => {
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const element = dialog.current;
    const controls = () => [...element.querySelectorAll("input,button:not([disabled])")];
    controls()[0]?.focus();
    function keydown(event) {
      if (event.key === "Escape" && !busy.current) close.current();
      if (event.key !== "Tab") return;
      const items = controls(), first = items[0], last = items.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
    element.addEventListener("keydown", keydown);
    return () => { element.removeEventListener("keydown", keydown); document.body.style.overflow = overflow; previous?.focus(); };
  }, []);
  async function submit(event) {
    event.preventDefault();
    if (busy.current || (confirmation && value !== confirmation)) return;
    busy.current = true; setSaving(true); setError("");
    try { if (await onConfirm() !== false) onClose(); }
    catch (error) { setError(error.message); }
    finally { busy.current = false; setSaving(false); }
  }
  return <div className="family-confirm-overlay" onMouseDown={event => { if (event.target === event.currentTarget && !busy.current) onClose(); }}>
    <section ref={dialog} className="family-confirm-dialog" role="dialog" aria-modal="true" aria-label={title}>
      <div className="family-confirm-heading"><h2>{title}</h2><button className="db-outline-btn" aria-label="Close confirmation" disabled={saving} onClick={onClose}><X size={18}/></button></div>
      <form onSubmit={submit} className="family-form">{children}
        {confirmation && <label>Type “{confirmation}” to confirm<input autoComplete="off" value={value} disabled={saving} onChange={event => setValue(event.target.value)}/></label>}
        {error && <p role="alert">{error}</p>}
        <div className="family-actions"><button type="button" className="db-outline-btn" disabled={saving} onClick={onClose}>Cancel</button><button className="db-primary-btn family-danger-button" disabled={saving || Boolean(confirmation && value !== confirmation)}>{saving ? "Please wait…" : confirmLabel}</button></div>
      </form>
    </section>
  </div>;
}
