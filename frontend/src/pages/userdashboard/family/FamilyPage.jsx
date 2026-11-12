import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Users } from "lucide-react";
import { api } from "../../../api/client";
import GlassCard from "../../../components/common/GlassCard";
import EmptyState from "../../../components/common/EmptyState";
import Loading from "../../../components/common/Loading";
import Modal from "../../../components/common/Modal";
import "../dashboard/Dashboard.css";
import "./FamilyPage.css";

const blank = { full_name: "", email: "", password: "", confirm_password: "" };

export default function FamilyPage() {
  const [family, setFamily] = useState(null);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(blank);
  const [saving, setSaving] = useState(false);
  const [revision, setRevision] = useState(0);
  const busy = useRef(false);
  const dialog = useRef(null);
  const opener = useRef(null);
  const owner = family?.role === "owner";

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([api("/family", { signal: controller.signal }), api("/family/members", { signal: controller.signal })])
      .then(([info, list]) => { if (!controller.signal.aborted) { setFamily(info); setMembers(list); setError(""); } })
      .catch((err) => { if (!controller.signal.aborted) { setFamily(null); setMembers([]); setError(err.message); } })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [revision]);

  useEffect(() => {
    if (!modal) return;
    const previous = document.activeElement;
    const node = dialog.current.closest('[role="dialog"]');
    const elements = () => [...node.querySelectorAll("input, button")].filter((item) => !item.disabled);
    elements()[0]?.focus();
    function keydown(event) {
      if (event.key === "Escape" && !busy.current) setModal(null);
      if (event.key === "Tab") {
        const items = elements(), first = items[0], last = items.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    }
    node.addEventListener("keydown", keydown);
    return () => { node.removeEventListener("keydown", keydown); (opener.current || previous)?.focus(); };
  }, [modal]);

  function open(value, event) {
    opener.current = event.currentTarget;
    setError(""); setNotice(""); setForm(blank); setModal(value);
  }

  async function submit(event) {
    event.preventDefault();
    if (busy.current) return;
    if (modal === "add" && form.password !== form.confirm_password) { setError("Passwords do not match."); return; }
    busy.current = true; setSaving(true); setError("");
    try {
      if (modal === "add") {
        await api("/family/members", { method: "POST", data: { ...form, full_name: form.full_name.trim(), email: form.email.trim().toLowerCase() } });
        setNotice("Family member added. They can sign in with their email and password.");
      } else {
        await api(`/family/members/${modal.id}`, { method: "DELETE" });
        setNotice("Membership removed. Their personal account and financial records are preserved.");
      }
      setForm(blank); setModal(null); setLoading(true); setRevision((value) => value + 1);
    } catch (err) { setError(err.message); }
    finally { busy.current = false; setSaving(false); }
  }

  const add = (event) => open("add", event);
  return <main className="db-main family-page" aria-busy={loading}>
    <div className="db-page-intro"><div><span className="db-page-subtitle">MAXBUD / YOUR WORKSPACE</span><h1>Family Management</h1><p>Manage your household membership and keep personal finances private.</p></div>
      {owner && <button type="button" className="db-primary-btn" disabled={loading || family.available_slots === 0} onClick={add}><Plus size={17}/>Add Member</button>}
    </div>
    {error && <div className="family-feedback" role="alert">{error} <button type="button" onClick={() => { setLoading(true); setRevision((value) => value + 1); }}>Retry</button> <Link to="/login">Sign in</Link></div>}
    {notice && <p className="family-feedback" role="status">{notice}</p>}
    {loading ? <Loading>Loading family membership…</Loading> : family && <>
      <GlassCard title={family.name} subtitle="Family overview"><dl className="family-overview">
        {[["Plan", family.plan === "premium" ? "Premium" : "Free"], ["Owner", family.owner_name], ["Active members", family.total_active_members], ["Maximum members", family.max_members], ["Available slots", family.available_slots], ["Currency", family.currency]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      </dl>{owner && family.available_slots === 0 && <p role="status">Family member limit reached ({family.max_members} users including the owner).{family.plan === "free" && " Premium supports up to 7 users. Upgrades are not available in this build."}</p>}</GlassCard>
      <GlassCard title={owner ? "Family members" : "Your membership"} subtitle={owner ? "Each member signs in to their own personal account." : "Only the owner can manage family members and view family totals."}>
        {owner && members.length <= 1 && <><EmptyState icon={Users} title="No family members yet." text="Add a member to help your household budget together."/><button type="button" className="db-primary-btn" onClick={add} disabled={family.available_slots === 0}>Add Member</button></>}
        <div className="family-table-wrap"><table className="family-table"><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Joined</th>{owner && <th>Action</th>}</tr></thead><tbody>{members.map((member) => <tr key={member.id}><td>{member.full_name}</td><td>{member.email}</td><td>{member.role === "owner" ? "Owner" : "Member"}</td><td>{member.is_active ? "Active" : "Inactive"}</td><td>{member.joined_at ? new Date(member.joined_at).toLocaleDateString() : "Not recorded"}</td>{owner && <td>{member.role !== "owner" && <button type="button" className="db-secondary-btn" onClick={(event) => open(member, event)} aria-label={`Remove ${member.full_name}`}>Remove</button>}</td>}</tr>)}</tbody></table></div>
      </GlassCard>
    </>}
    {modal && <Modal title={modal === "add" ? "Add family member" : "Remove family member"} onClose={() => { if (!busy.current) { setModal(null); setForm(blank); } }}><div ref={dialog}>
      <form className="family-form" onSubmit={submit}>
        {modal === "add" ? <>{[["full_name", "Full Name", "text"], ["email", "Email Address", "email"], ["password", "Password", "password"], ["confirm_password", "Confirm Password", "password"]].map(([key, label, type]) => <label key={key} htmlFor={`family-${key}`}>{label}<input id={`family-${key}`} name={key} type={type} value={form[key]} onChange={(event) => setForm({ ...form, [key]: event.target.value })} required disabled={saving} minLength={key === "full_name" ? 2 : type === "password" ? 8 : undefined} maxLength={key === "full_name" ? 100 : key === "email" ? 254 : 128} autoComplete={type === "password" ? "new-password" : "off"} pattern={key === "password" ? "(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9])(?=.*[^A-Za-z0-9]).{8,128}" : undefined}/></label>)}<p>Use 8–128 characters with uppercase, lowercase, a number and a symbol.</p></> : <p>Remove <strong>{modal.full_name}</strong> from the family? Their personal account and financial records will be preserved. Family access ends immediately.</p>}
        {error && <p role="alert">{error}</p>}
        <div className="family-actions"><button className="db-secondary-btn" type="button" disabled={saving} onClick={() => { setModal(null); setForm(blank); }}>Cancel</button><button className="db-primary-btn" type="submit" disabled={saving}>{saving ? "Saving…" : modal === "add" ? "Add Member" : "Remove Member"}</button></div>
      </form>
    </div></Modal>}
  </main>;
}
