import { useEffect, useState } from "react";
import {
  ArrowRight,
  Clock3,
  Command,
  Cpu,
  Layers,
  LogOut,
  ShieldCheck,
  Users,
} from "lucide-react";
import { api, setCsrf } from "./api";
import type { Profile, Role } from "./types";
import { Avatar, Button, Failure, Loading } from "./ui";
import { UsersPage } from "./UsersPage";
import { RolesPage } from "./RolesPage";
import { ModelsPage } from "./ModelsPage";
import { HistoryPage } from "./HistoryPage";

const ticket = new URLSearchParams(window.location.hash.slice(1)).get("login");
if (window.location.hash)
  window.history.replaceState(null, "", window.location.pathname);
let bootstrap: Promise<{ admin: Profile; roles: Role[] }> | null = null;
function boot() {
  return (bootstrap ??= (async () => {
    if (ticket) {
      const auth = await api<{ csrf_token: string }>("/api/auth/exchange", {
        method: "POST",
        body: JSON.stringify({ token: ticket }),
      });
      setCsrf(auth.csrf_token);
    }
    const [session, catalog] = await Promise.all([
      api<{ admin: Profile; csrf_token: string }>("/api/session"),
      api<{ roles: Role[] }>("/api/roles"),
    ]);
    setCsrf(session.csrf_token);
    return { admin: session.admin, roles: catalog.roles };
  })());
}
const sections = [
  { id: "users", label: "Foydalanuvchilar", Icon: Users },
  { id: "roles", label: "Rollar", Icon: Layers },
  { id: "models", label: "AI modellari", Icon: Cpu },
  { id: "history", label: "O‘zgarishlar tarixi", Icon: Clock3 },
] as const;
type Section = (typeof sections)[number]["id"];
export function App() {
  const [ready, setReady] = useState<{ admin: Profile; roles: Role[] } | null>(
      null,
    ),
    [error, setError] = useState<Error | null>(null),
    [section, setSection] = useState<Section>("users"),
    [loggingOut, setLoggingOut] = useState(false);
  useEffect(() => {
    let live = true;
    boot()
      .then((value) => {
        if (live) setReady(value);
      })
      .catch((e) => {
        if (live) setError(e);
      });
    const expire = () => {
      setReady(null);
      setError(
        new Error(
          "Kirish muddati tugadi. Botga /admin yuborib, yangi havola oling.",
        ),
      );
    };
    window.addEventListener("admin-session-expired", expire);
    return () => {
      live = false;
      window.removeEventListener("admin-session-expired", expire);
    };
  }, []);
  function updateCatalog(roles: Role[]) {
    setReady((old) => (old ? { ...old, roles } : old));
  }
  async function refreshRoles() {
    const catalog = await api<{ roles: Role[] }>("/api/roles");
    setReady((old) => (old ? { ...old, roles: catalog.roles } : old));
  }
  async function logout() {
    setLoggingOut(true);
    try {
      await api("/api/auth/logout", { method: "POST" });
      setCsrf("");
      setReady(null);
      setError(
        new Error(
          "Hisobdan chiqdingiz. Qayta kirish uchun botga /admin yuboring.",
        ),
      );
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoggingOut(false);
    }
  }
  if (!ready)
    return (
      <div className="login-page">
        <div className="login-brand">
          <span className="brand-mark">
            <Command size={22} />
          </span>
          Yordamchi<span>ADMIN</span>
        </div>
        <section className="login-card">
          <span className="login-lock">
            <ShieldCheck size={32} />
          </span>
          <div className="eyebrow">XAVFSIZ BOSHQARUV</div>
          <h1>Jamoangizni bir joydan boshqaring.</h1>
          {error ? (
            <>
              <p className="login-error" role="alert">
                {error.message}
              </p>
              <div className="login-instruction">
                <span>1</span>
                <p>
                  Telegram botingizni oching va <code>/admin</code> yuboring.
                </p>
              </div>
              <div className="login-instruction">
                <span>2</span>
                <p>Bot bergan bir martalik havolani shu qurilmada oching.</p>
              </div>
              <p className="muted">
                Havola 5 daqiqa amal qiladi. Faqat biriktirilgan administrator
                kira oladi.
              </p>
              <Button
                className="primary"
                onClick={() => window.location.reload()}
              >
                Sahifani yangilash
                <ArrowRight size={16} />
              </Button>
            </>
          ) : (
            <Loading />
          )}
        </section>
        <p className="login-caption">
          Rollar · Imkoniyatlar · Gemini modellari
        </p>
      </div>
    );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a href="/" className="brand" aria-label="Yordamchi admin bosh sahifa">
          <span className="brand-mark">
            <Command size={23} />
          </span>
          <span>
            Yordamchi<small>ADMIN PANEL</small>
          </span>
        </a>
        <div className="sidebar-caption">ISH MAYDONI</div>
        <nav aria-label="Asosiy navigatsiya">
          {sections.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setSection(id)}
              className={section === id ? "active" : ""}
              aria-current={section === id ? "page" : undefined}
            >
              <Icon size={19} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <ShieldCheck size={19} />
          <p>
            Ruxsatlar serverda tekshiriladi.
            <br />
            Har bir o‘zgarish tarixda saqlanadi.
          </p>
        </div>
        <div className="admin-account">
          <Avatar user={ready.admin} />
          <div>
            <strong>Administrator</strong>
            <span>
              {ready.admin.username
                ? `@${ready.admin.username}`
                : ready.admin.telegram_user_id}
            </span>
          </div>
          <Button
            className="icon-button"
            aria-label="Hisobdan chiqish"
            onClick={logout}
            busy={loggingOut}
          >
            <LogOut size={17} />
          </Button>
        </div>
      </aside>
      <main>
        <div className="topbar">
          <span>
            Yordamchi <span className="separator">/</span> Admin panel
          </span>
          <span>
            <ShieldCheck size={14} />
            Administrator
          </span>
        </div>
        <div className="main-content">
          {error ? (
            <Failure error={error} retry={() => setError(null)} />
          ) : null}
          {section === "users" ? (
            <UsersPage roles={ready.roles} onCatalog={updateCatalog} />
          ) : section === "roles" ? (
            <RolesPage roles={ready.roles} onRefresh={refreshRoles} />
          ) : section === "models" ? (
            <ModelsPage roles={ready.roles} />
          ) : (
            <HistoryPage roles={ready.roles} />
          )}
        </div>
        <footer className="app-footer">
          Yordamchi <span>Virtual jamoa boshqaruvi</span>
        </footer>
      </main>
    </div>
  );
}
