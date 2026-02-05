import { useEffect, useState } from "react";
import {
  AuditEntry,
  AuditFilters,
  UserSummary,
  createInvite,
  deleteUser,
  listAudit,
  listUsers,
  resetUserInvite,
  revokeInvite,
  updateUserRole
} from "../api/client";

const auditEventOptions = [
  "login_success",
  "login_fail",
  "schedule_run",
  "schedule_export",
  "schedule_import",
  "config_save",
  "config_import",
  "config_export",
  "invite_created",
  "invite_revoked",
  "reset_invite",
  "role_updated",
  "user_deleted"
];

const formatDateTime = (value?: string | null) => {
  if (!value) return "";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString(undefined, {
    year: "2-digit",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
};

const friendlyError = (err: any, fallback: string) => {
  const status = err?.response?.status;
  if (status === 401) return "Invalid username or password";
  if (status === 422) return "Validation failed. Please check your inputs.";
  if (status === 409 && err?.response?.data?.detail) return String(err.response.data.detail);
  if (status === 409) return "Conflict: value already in use.";
  return err?.message ?? fallback;
};

export default function AdminPanel() {
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [auditFeed, setAuditFeed] = useState<AuditEntry[]>([]);
  const [auditEvent, setAuditEvent] = useState<string>("");
  const [auditUserId, setAuditUserId] = useState<string>("");
  const [auditSearch, setAuditSearch] = useState<string>("");
  const [auditLimit, setAuditLimit] = useState<number>(50);
  const [inviteLicense, setInviteLicense] = useState<string>("DEMO");
  const [inviteRole, setInviteRole] = useState<string>("user");
  const [inviteResult, setInviteResult] = useState<string>("");
  const [copyNotice, setCopyNotice] = useState<string>("");

  const copyText = async (text: string) => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        setCopyNotice("Copied to clipboard");
        return;
      }
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopyNotice("Copied to clipboard");
    } catch {
      setCopyNotice("Copy failed");
    }
  };

  const loadUsers = async () => {
    try {
      const data = await listUsers();
      setUsers(data);
    } catch {
      // ignore
    }
  };

  const loadAudit = async (overrides: AuditFilters = {}) => {
    try {
      const filters: AuditFilters = {
        limit: auditLimit,
        event: auditEvent || undefined,
        user_id: auditUserId ? Number(auditUserId) : undefined,
        search: auditSearch.trim() ? auditSearch.trim() : undefined,
        ...overrides
      };
      const data = await listAudit(filters);
      setAuditFeed(data);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    loadUsers();
    loadAudit();
  }, []);

  const userNameMap = users.reduce<Record<number, string>>((acc, u) => {
    acc[u.id] = u.username;
    return acc;
  }, {});

  return (
    <div className="card" style={{ marginTop: "1rem" }}>
      <h3>Admin</h3>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.75rem" }}>
        <strong>User tools</strong>
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.25rem", alignItems: "center" }}>
            <input
              placeholder="License key"
              id="admin-invite-license"
              name="admin-invite-license"
              value={inviteLicense}
              onChange={(e) => setInviteLicense(e.target.value)}
              style={{ maxWidth: "120px" }}
            />
            <select
              id="admin-invite-role"
              name="admin-invite-role"
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
              style={{ maxWidth: "120px" }}
            >
            <option value="user">User</option>
            <option value="admin">Admin</option>
          </select>
          <button
            className="secondary-btn"
            onClick={async () => {
              try {
                const res = await createInvite({
                  username: "",
                  license_key: inviteLicense,
                  role: inviteRole
                });
                setInviteResult(res.token);
              } catch (err: any) {
                setInviteResult(friendlyError(err, "Failed to create invite"));
              }
            }}
          >
            Create invite
          </button>
        </div>
        {inviteResult && (
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span className="muted">Invite token:</span>
            <code>{inviteResult}</code>
            <button className="secondary-btn" onClick={() => copyText(inviteResult)}>
              Copy
            </button>
            {copyNotice && <span className="muted">{copyNotice}</span>}
          </div>
        )}
      </div>
      <div style={{ marginBottom: "0.5rem", display: "flex", gap: "0.5rem" }}>
        <button className="secondary-btn" onClick={loadUsers}>
          Refresh users
        </button>
      </div>
      <div style={{ overflowX: "auto", marginBottom: "1rem" }}>
        {users.length === 0 ? (
          <p className="muted">No users found.</p>
        ) : (
          <table cellPadding={6} style={{ minWidth: "780px", borderCollapse: "collapse", fontSize: "0.9rem" }}>
            <thead>
              <tr>
                <th>Public ID</th>
                <th>Username</th>
                <th>Role</th>
                <th>Status</th>
                <th>Last Login</th>
                <th>Invite Expires</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.public_id || u.id}</td>
              <td>{u.username}</td>
              <td>
                <select
                  id={`admin-user-role-${u.id}`}
                  name={`admin-user-role-${u.id}`}
                  disabled={u.username?.toLowerCase() === "admin" || u.id === 1}
                  title={
                    u.username?.toLowerCase() === "admin" || u.id === 1
                      ? "Master admin cannot be changed"
                      : undefined
                  }
                  value={u.role}
                  onChange={async (e) => {
                    const newRole = e.target.value;
                    try {
                      await updateUserRole(u.id, newRole);
                          loadUsers();
                        } catch {
                          /* ignore */
                        }
                      }}
                    >
                      <option value="user">User</option>
                      <option value="admin">Admin</option>
                    </select>
                  </td>
                  <td>{u.status}</td>
                  <td>{formatDateTime(u.last_login)}</td>
                  <td>{u.status === "active" ? "-" : formatDateTime(u.invite_expires_at)}</td>
                  <td
                    style={{
                      display: "flex",
                      gap: "0.35rem",
                      flexWrap: "nowrap",
                      alignItems: "center",
                      justifyContent: "flex-start"
                    }}
                  >
                    <button
                      className="secondary-btn"
                      onClick={async () => {
                        try {
                          await revokeInvite({ username: u.username, license_key: "" });
                          loadUsers();
                        } catch {
                          /* ignore */
                        }
                      }}
                    >
                      Revoke invite
                    </button>
                    <button
                      className="secondary-btn"
                      onClick={async () => {
                        try {
                          await deleteUser(u.id);
                          loadUsers();
                        } catch {
                          /* ignore */
                        }
                      }}
                    >
                      Delete
                    </button>
                    <button
                      className="secondary-btn"
                      onClick={async () => {
                        try {
                          const res = await resetUserInvite(u.id);
                          setInviteResult(`Reset token for ${u.username}: ${res.token}`);
                          loadUsers();
                        } catch (err: any) {
                          setInviteResult(err?.message ?? "Failed to reset invite");
                        }
                      }}
                    >
                      Reset password
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <div>
        <h4>Recent activity</h4>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "0.75rem",
            alignItems: "flex-end",
            margin: "0.5rem 0 0.75rem"
          }}
        >
          <label className="field" style={{ minWidth: "160px" }}>
            <span className="muted small-note">Event</span>
            <select value={auditEvent} onChange={(e) => setAuditEvent(e.target.value)}>
              <option value="">All events</option>
              {auditEventOptions.map((event) => (
                <option key={event} value={event}>
                  {event}
                </option>
              ))}
            </select>
          </label>
          <label className="field" style={{ minWidth: "160px" }}>
            <span className="muted small-note">User</span>
            <select value={auditUserId} onChange={(e) => setAuditUserId(e.target.value)}>
              <option value="">All users</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.username}
                </option>
              ))}
            </select>
          </label>
          <label className="field" style={{ minWidth: "220px", flex: "1 1 220px" }}>
            <span className="muted small-note">Search</span>
            <input
              value={auditSearch}
              onChange={(e) => setAuditSearch(e.target.value)}
              placeholder="event, detail, IP, location"
            />
          </label>
          <label className="field" style={{ width: "110px" }}>
            <span className="muted small-note">Limit</span>
            <input
              type="number"
              min={1}
              max={500}
              value={auditLimit}
              onChange={(e) => setAuditLimit(Math.max(1, Number(e.target.value) || 1))}
            />
          </label>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button className="secondary-btn" onClick={() => loadAudit()}>
              Apply
            </button>
            <button
              className="secondary-btn"
              onClick={() => {
                setAuditEvent("");
                setAuditUserId("");
                setAuditSearch("");
                setAuditLimit(50);
                loadAudit({ limit: 50, event: undefined, user_id: undefined, search: undefined });
              }}
            >
              Clear
            </button>
            <button className="secondary-btn" onClick={() => loadAudit()}>
              Refresh
            </button>
          </div>
        </div>
        {auditFeed.length === 0 ? (
          <p className="muted">No audit entries.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table cellPadding={6} style={{ minWidth: "820px", borderCollapse: "collapse", fontSize: "0.9rem" }}>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Event</th>
                  <th>User ID</th>
                  <th>Detail</th>
                  <th>Location</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {auditFeed.map((a) => (
                  <tr key={a.id}>
                    <td>{formatDateTime(a.created_at)}</td>
                    <td>{a.event}</td>
                    <td>{a.user_id != null ? `${userNameMap[a.user_id] ?? a.user_id}` : "-"}</td>
                    <td>{a.detail || "-"}</td>
                    <td>{a.location || "-"}</td>
                    <td>{a.ip_v4 || a.ip || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
