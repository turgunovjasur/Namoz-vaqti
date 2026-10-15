import { Layers, LockKeyhole } from "lucide-react";
import type { Role } from "./types";
export function RolesPage({ roles }: { roles: Role[] }) {
  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">VIRTUAL JAMOA</div>
          <h1>Rollar va imkoniyatlar</h1>
          <p>Har bir rolning vazifasi va bajaradigan ishlari.</p>
        </div>
        <span className="header-count">{roles.length} ta rol</span>
      </header>
      <div className="info-strip">
        <Layers size={20} />
        <p>
          Bitta imkoniyat bir nechta rolga bog‘lanishi mumkin. Foydalanuvchiga
          ruxsatlar har bir rol ichida alohida beriladi.
        </p>
      </div>
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
            {role.system_role ? (
              <p className="system-description">
                Barcha foydalanuvchilar uchun yoqilgan. Foydalanuvchi profilidan
                o‘chirib bo‘lmaydi.
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
    </>
  );
}
