import { useEffect, useRef, useState } from "react";
import { ChevronDown, LockKeyhole, Save, X } from "lucide-react";
import { api, ApiError } from "./api";
import type { GrantDraft, Profile, Role } from "./types";
import { Avatar, Button, Message, nameOf } from "./ui";

function drafts(user: Profile, roles: Role[]): GrantDraft[] {
  return roles
    .filter((r) => !r.system_role)
    .map((r) => {
      const a = user.roles.find((a) => a.role_id === r.id);
      return {
        role_id: r.id,
        enabled: a?.enabled || false,
        capability_ids: [...(a?.capability_ids || [])].sort(),
        expected_revision: a?.revision || 0,
      };
    });
}
export function UserEditor({
  user,
  roles,
  onClose,
  onSaved,
}: {
  user: Profile;
  roles: Role[];
  onClose: () => void;
  onSaved: (user: Profile) => void;
}) {
  const [baseline, setBaseline] = useState(user),
    [draft, setDraft] = useState(() => drafts(user, roles)),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | null>(null),
    [saved, setSaved] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const original = drafts(baseline, roles),
    changed = draft.filter(
      (d, i) => JSON.stringify(d) !== JSON.stringify(original[i]),
    );
  const dirty = changed.length > 0;
  useEffect(() => {
    dialog.current?.showModal();
    return () => dialog.current?.close();
  }, []);
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  function close() {
    if (busy) return;
    if (!dirty || window.confirm("Saqlanmagan o‘zgarishlar bekor qilinsinmi?"))
      onClose();
  }
  function update(role: string, fn: (d: GrantDraft) => GrantDraft) {
    setSaved(false);
    setDraft((all) => all.map((d) => (d.role_id === role ? fn(d) : d)));
  }
  function reset() {
    setDraft(drafts(baseline, roles));
    setError(null);
    setSaved(false);
  }
  async function save() {
    setBusy(true);
    setError(null);
    try {
      const value = await api<Profile>(
        `/api/users/${user.user_id}/assignments`,
        { method: "PUT", body: JSON.stringify({ changes: changed }) },
      );
      setBaseline(value);
      setDraft(drafts(value, roles));
      setSaved(true);
      onSaved(value);
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  }
  async function refresh() {
    if (
      dirty &&
      !window.confirm(
        "So‘nggi ma’lumotni olish joriy tahrirni bekor qiladi. Davom etilsinmi?",
      )
    )
      return;
    setBusy(true);
    try {
      const value = await api<Profile>(`/api/users/${user.user_id}`);
      setBaseline(value);
      setDraft(drafts(value, roles));
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <dialog
      className="inspector"
      ref={dialog}
      aria-labelledby="editor-title"
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
    >
      <div className="sheet-head">
        <span>Foydalanuvchi profili</span>
        <Button
          className="icon-button"
          aria-label="Profilni yopish"
          onClick={close}
          disabled={busy}
        >
          <X size={21} />
        </Button>
      </div>
      <div className="sheet-body">
        <div className="identity large">
          <Avatar user={baseline} />
          <div>
            <h2 id="editor-title">{nameOf(baseline)}</h2>
            {baseline.username ? <p>@{baseline.username}</p> : null}
            <p>
              Telegram ID:{" "}
              <span className="mono">{baseline.telegram_user_id}</span>
            </p>
            <span className="pill">
              {baseline.profile_type === "admin"
                ? "Administrator"
                : "Foydalanuvchi"}
            </span>
          </div>
        </div>
        <h3>Rollar va imkoniyatlar</h3>
        <p className="muted intro">
          Rolni yoqing va unga beriladigan imkoniyatlarni tanlang.
        </p>
        {error ? (
          <Message error>
            {error.message}
            {error instanceof ApiError && error.status === 409 ? (
              <Button onClick={refresh} busy={busy}>
                So‘nggi ma’lumotni olish
              </Button>
            ) : null}
          </Message>
        ) : null}
        {saved ? <Message>Rollar va imkoniyatlar saqlandi.</Message> : null}
        <div className="role-editor">
          {draft.map((d) => {
            const role = roles.find((r) => r.id === d.role_id)!;
            return (
              <details
                className={`role-edit ${d.enabled ? "enabled" : ""}`}
                key={role.id}
                open={d.enabled}
              >
                <summary>
                  <div>
                    <strong>{role.name}</strong>
                    <span>
                      {d.capability_ids.length} / {role.capabilities.length}{" "}
                      imkoniyat
                    </span>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-label={`${role.name} rolini yoqish`}
                    aria-checked={d.enabled}
                    className={`switch ${d.enabled ? "on" : ""}`}
                    disabled={busy}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      update(role.id, (old) => ({
                        ...old,
                        enabled: !old.enabled,
                      }));
                    }}
                  >
                    <span />
                  </button>
                  <ChevronDown className="chevron" size={16} />
                </summary>
                <div className="capabilities">
                  <p className="muted">{role.description}</p>
                  {!d.enabled ? (
                    <p className="muted">
                      Rol o‘chiq. Tanlangan imkoniyatlar saqlanadi.
                    </p>
                  ) : null}
                  {role.capabilities.map((cap) => (
                    <label className="capability" key={cap.id}>
                      <input
                        type="checkbox"
                        checked={d.capability_ids.includes(cap.id)}
                        disabled={busy || !d.enabled}
                        onChange={(e) =>
                          update(role.id, (old) => ({
                            ...old,
                            capability_ids: (e.target.checked
                              ? [...old.capability_ids, cap.id]
                              : old.capability_ids.filter((id) => id !== cap.id)
                            ).sort(),
                          }))
                        }
                      />
                      <span>
                        <strong>{cap.name}</strong>
                        <small>{cap.description}</small>
                      </span>
                    </label>
                  ))}
                </div>
              </details>
            );
          })}
        </div>
        <div className="system-note">
          <LockKeyhole size={16} />
          <span>
            {roles
              .filter((r) => r.system_role)
              .map((r) => r.name)
              .join(" va ")}{" "}
            — barcha foydalanuvchilar uchun doimiy tizim rollari.
          </span>
        </div>
      </div>
      <div className="sheet-footer">
        <span className="muted">
          {dirty
            ? `${changed.length} ta rol o‘zgartirildi`
            : "O‘zgarishlar saqlangan"}
        </span>
        <div>
          <Button onClick={reset} disabled={!dirty || busy}>
            Bekor qilish
          </Button>
          <Button
            className="primary"
            onClick={save}
            busy={busy}
            disabled={!dirty}
          >
            <Save size={16} />
            Saqlash
          </Button>
        </div>
      </div>
    </dialog>
  );
}
