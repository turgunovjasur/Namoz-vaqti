import { useState } from "react";
import { Clock3, ShieldCheck } from "lucide-react";
import { useRemote } from "./api";
import type { AuditPage, Change, Role } from "./types";
import { Empty, Failure, Loading, Next } from "./ui";
function ChangeDetails({ change, roles }: { change: Change; roles: Role[] }) {
  const role = roles.find((r) => r.id === change.detail.role_id);
  if (change.action === "set_grants") {
    const caps = Array.isArray(change.detail.capability_ids)
      ? (change.detail.capability_ids as string[])
      : [];
    return (
      <>
        <strong>
          {role?.name || String(change.detail.role_id)} —{" "}
          {change.detail.enabled ? "yoqildi" : "o‘chirildi"}
        </strong>
        <p>
          {caps.length
            ? caps
                .map(
                  (id) =>
                    role?.capabilities.find((c) => c.id === id)?.name || id,
                )
                .join(", ")
            : "Imkoniyat tanlanmagan"}
        </p>
        <span className="version">Tahrir {String(change.detail.revision)}</span>
      </>
    );
  }
  if (change.action === "set_model")
    return (
      <>
        <strong>
          {role?.name || String(change.detail.role_id)} modeli almashtirildi
        </strong>
        <p className="mono">{String(change.detail.model_id)}</p>
      </>
    );
  if (change.action === "create_role" || change.action === "update_role")
    return (
      <>
        <strong>
          {String(change.detail.name)} —{" "}
          {change.action === "create_role"
            ? "rol yaratildi"
            : "rol tahrirlandi"}
        </strong>
        <p>
          {String(change.detail.model_id)} ·{" "}
          {(change.detail.capability_ids as string[]).length} skill · tahrir{" "}
          {String(change.detail.revision)}
        </p>
      </>
    );
  if (change.action === "set_role_template")
    return (
      <strong>
        Umumiy qoidalar shabloni yangilandi · tahrir{" "}
        {String(change.detail.revision)}
      </strong>
    );
  return <strong>{change.action}</strong>;
}
export function HistoryPage({ roles }: { roles: Role[] }) {
  const [cursors, setCursors] = useState<number[]>([]);
  const { data, error, loading, reload } = useRemote<AuditPage>(
    `/api/history?before_id=${cursors.at(-1) || 0}`,
  );
  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">NAZORAT</div>
          <h1>O‘zgarishlar tarixi</h1>
          <p>Kim, qachon va qaysi sozlamani o‘zgartirganini ko‘ring.</p>
        </div>
        <span className="connection">
          <ShieldCheck size={15} />
          Audit jurnali
        </span>
      </header>
      <section className="surface">
        {loading ? (
          <Loading />
        ) : error ? (
          <Failure error={error} retry={reload} />
        ) : data?.changes.length ? (
          <>
            <div className="history-list">
              {data.changes.map((change) => (
                <article className="history-item" key={change.id}>
                  <div className="history-icon">
                    <Clock3 size={18} />
                  </div>
                  <div className="history-detail">
                    <ChangeDetails change={change} roles={roles} />
                    <div className="audit-identity">
                      <span>
                        Admin:{" "}
                        <b className="mono">{change.actor_telegram_id}</b>
                      </span>
                      {change.target_telegram_id ? (
                        <span>
                          Foydalanuvchi:{" "}
                          <b className="mono">{change.target_telegram_id}</b>
                        </span>
                      ) : (
                        <span>Barcha foydalanuvchilar</span>
                      )}
                    </div>
                  </div>
                  <time dateTime={change.created_at}>
                    {new Intl.DateTimeFormat("uz-UZ", {
                      year: "numeric",
                      month: "2-digit",
                      day: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    }).format(new Date(change.created_at))}
                  </time>
                </article>
              ))}
            </div>
            <Next
              more={data.more}
              canPrev={cursors.length > 0}
              onPrev={() => setCursors((c) => c.slice(0, -1))}
              onNext={() => setCursors((c) => [...c, data.changes.at(-1)!.id])}
            />
          </>
        ) : (
          <Empty title="Hozircha o‘zgarishlar yo‘q">
            Rol, imkoniyat yoki model o‘zgartirilganda tarix shu yerda
            ko‘rinadi.
          </Empty>
        )}
      </section>
    </>
  );
}
