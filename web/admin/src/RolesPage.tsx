import { useState } from "react";
import { api } from "./api";
import { Button, Message } from "./ui";
import { RoleEditor } from "./RoleEditor";
import { RuleTemplateEditor } from "./RuleTemplateEditor";
import { Layers, LockKeyhole } from "lucide-react";
import type { Role } from "./types";
export function RolesPage({
  roles,
  onRefresh,
}: {
  roles: Role[];
  onRefresh: () => Promise<void>;
}) {
  const [editing, setEditing] = useState<Role | null | undefined>(undefined),
    [error, setError] = useState<Error | null>(null),
    [busy, setBusy] = useState(false);
  async function edit(id: string) {
    setBusy(true);
    setError(null);
    try {
      const latest = await api<{ roles: Role[] }>("/api/roles");
      const role = latest.roles.find((r) => r.id === id);
      if (!role) throw new Error("Rol topilmadi; sahifani yangilang.");
      setEditing(role);
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">VIRTUAL JAMOA</div>
          <h1>Rollar va imkoniyatlar</h1>
          <p>Har bir rolning vazifasi va bajaradigan ishlari.</p>
        </div>
        <Button className="primary" onClick={() => setEditing(null)}>
          + Rol qo‘shish
        </Button>
      </header>
      <div className="info-strip">
        <Layers size={20} />
        <p>
          Bitta imkoniyat bir nechta rolga bog‘lanishi mumkin. Foydalanuvchiga
          ruxsatlar har bir rol ichida alohida beriladi.
        </p>
      </div>
      {error ? <Message error>{error.message}</Message> : null}
      <RuleTemplateEditor />
      <div className="catalog">
        {roles.map((role) => (
          <section className="surface catalog-role" key={role.id}>
            <div className="catalog-heading">
              <span className="role-mark">{role.name[0]}</span>
              <div>
                <h2>{role.name}</h2>
                <p>{role.description}</p>
              </div>
              {role.system_role ? (
                <span className="pill system">
                  <LockKeyhole size={12} />
                  Tizim roli
                </span>
              ) : (
                <span className="pill">
                  {role.capabilities.length} imkoniyat
                </span>
              )}
            </div>
            <div className="role-card-actions">
              <span className="muted">
                {role.reserved
                  ? "Oldingi sozlama saqlangan; boshqaruv Yordamchida"
                  : `${role.enabled ? "Faol" : "O‘chiq"} · ${role.model.model_id} · tahrir ${role.revision}`}
              </span>
              {!role.reserved ? (
                <Button onClick={() => edit(role.id)} busy={busy}>
                  Tahrirlash
                </Button>
              ) : null}
            </div>
            {role.system_role ? (
              <p className="system-description">
                {role.reserved
                  ? "Alohida ish boshqaruvchi chaqirilmaydi. Yordamchi yo‘naltiradi va natijani tekshiradi."
                  : "Barcha foydalanuvchilar bilan muloqot qiladi, rollarga yo‘naltiradi va natijani tekshiradi."}
              </p>
            ) : (
              <div className="catalog-caps">
                {role.capabilities.map((cap) => (
                  <div key={cap.id}>
                    <span className={`effect ${cap.effect}`}>
                      {cap.effect === "read"
                        ? "O‘qish"
                        : cap.effect === "write"
                          ? "O‘zgartirish"
                          : "AI javobi"}
                    </span>
                    <div>
                      <strong>{cap.name}</strong>
                      <p>{cap.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        ))}
      </div>
      {editing !== undefined ? (
        <RoleEditor
          role={editing}
          defaultModel={roles.find((r) => r.id === "assistant")!.model}
          onClose={() => setEditing(undefined)}
          onSaved={onRefresh}
        />
      ) : null}
    </>
  );
}
