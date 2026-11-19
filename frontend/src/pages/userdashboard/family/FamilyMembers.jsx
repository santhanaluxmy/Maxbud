import { Users } from "lucide-react";
import GlassCard from "../../../components/common/GlassCard";

export default function FamilyMembers({ owner, members, saving, onPermissions, onRemove }) {
  return <GlassCard title={owner ? "Household members" : "Your membership"} subtitle={owner ? "Accepted members have their own accounts. Personal finances stay private." : "Your shared permissions are managed by the household owner."}>
    {!members.length ? <p role="status">No active memberships to display.</p> : <ul className="family-members-list">{members.map(member => <li className="family-member-card" key={member.id}>
      <div className="family-member-identity"><span className="family-member-avatar" aria-hidden="true"><Users size={21}/></span><div><h3>{member.full_name}</h3><p>{member.email}</p><div className="family-member-labels"><span className="family-invite-badge accepted">{member.role === "owner" ? "Owner" : "Member"}</span><span>{member.is_active ? "Active" : "Account inactive"}</span></div></div></div>
      {owner && member.role !== "owner" && <div className="family-member-controls"><fieldset disabled={saving}><legend>Shared permissions</legend><label><input type="checkbox" aria-label={`Allow shared reports for ${member.full_name}`} checked={member.can_view_shared} onChange={event => onPermissions(member, { can_view_shared: event.target.checked, can_add_shared: event.target.checked && member.can_add_shared })}/>View shared reports</label><label><input type="checkbox" aria-label={`Allow shared editing for ${member.full_name}`} checked={member.can_add_shared} disabled={!member.can_view_shared} onChange={event => onPermissions(member, { can_view_shared: member.can_view_shared, can_add_shared: event.target.checked })}/>Add shared records</label></fieldset><button className="db-outline-btn" disabled={saving} onClick={event => onRemove(member, event)} aria-label={`Remove ${member.full_name}`}>Remove member</button></div>}
    </li>)}</ul>}
  </GlassCard>;
}
