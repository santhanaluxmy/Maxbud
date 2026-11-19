import { useId, useState } from "react";
import { ChevronDown, Plus } from "lucide-react";

export default function MerchantSelector({ value, suggestions, onChange }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const query = value.trim();
  const matches = suggestions.filter(row => row.merchant.toLowerCase().includes(query.toLowerCase())).slice(0, 8);
  const isNew = query && !suggestions.some(row => row.merchant.toLowerCase() === query.toLowerCase());
  const options = [...matches, ...(isNew ? [{ merchant: query, isNew: true }] : [])];
  function choose(row) {
    onChange(row.merchant, row.category);
    setOpen(false);
    setActive(0);
  }
  return <div className="merchant-selector" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
    <label htmlFor={id}>Merchant</label>
    <div className="merchant-input-wrap"><input id={id} role="combobox" aria-autocomplete="list" aria-expanded={open} aria-controls={`${id}-options`} aria-activedescendant={open && options[active] ? `${id}-${active}` : undefined} autoComplete="off" required maxLength={150} placeholder="Search or add a merchant" value={value} onFocus={() => setOpen(true)} onChange={event => { onChange(event.target.value); setOpen(true); setActive(0); }} onKeyDown={event => {
      if (event.key === "Escape") { event.preventDefault(); setOpen(false); }
      if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); setOpen(true); setActive(previous => options.length ? (previous + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length : 0); }
      if (event.key === "Enter" && open && options[active]) { event.preventDefault(); choose(options[active]); }
    }}/><ChevronDown size={17} aria-hidden="true"/></div>
    {open && <ul id={`${id}-options`} role="listbox" aria-label="Merchant suggestions" className="merchant-options">
      {options.length ? options.map((row, index) => <li key={`${row.merchant}-${row.isNew || false}`} id={`${id}-${index}`} role="option" aria-selected={index === active} onMouseDown={event => event.preventDefault()} onMouseMove={() => setActive(index)} onClick={() => choose(row)}>{row.isNew ? <><Plus size={15}/> Use “{row.merchant}” as a new merchant</> : row.merchant}</li>) : <li role="presentation">Type a merchant name to add one.</li>}
    </ul>}
  </div>;
}
