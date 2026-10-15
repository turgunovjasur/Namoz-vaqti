import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  LoaderCircle,
  RefreshCw,
  Users,
} from "lucide-react";
import type { ReactNode } from "react";
import type { Profile, Role } from "./types";
export function Button({
  children,
  busy = false,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { busy?: boolean }) {
  return (
    <button {...props} disabled={props.disabled || busy}>
      {busy ? <LoaderCircle size={16} className="spin" /> : null}
      {children}
    </button>
  );
}
export function Message({
  children,
  error = false,
}: {
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <div
      className={`message ${error ? "error" : "success"}`}
      role={error ? "alert" : "status"}
    >
      {error ? <AlertCircle size={17} /> : <CheckCircle2 size={17} />}
      <span>{children}</span>
    </div>
  );
}
export function Loading() {
  return (
    <div className="state" role="status">
      <LoaderCircle size={24} className="spin" />
      <p>Ma’lumotlar yuklanmoqda…</p>
    </div>
  );
}
export function Failure({ error, retry }: { error: Error; retry: () => void }) {
  return (
    <div className="state">
      <AlertCircle size={28} />
      <h3>Yuklash bajarilmadi</h3>
      <p>{error.message}</p>
      <Button onClick={retry}>
        <RefreshCw size={16} />
        Qayta urinish
      </Button>
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="state">
      <div className="empty-icon">
        <Users size={26} />
      </div>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function nameOf(user: Profile) {
  return user.display_name || `Foydalanuvchi #${user.telegram_user_id}`;
}
export function Avatar({ user }: { user: Profile }) {
  const initials = user.display_name
    ? user.display_name
        .split(/\s+/)
        .slice(0, 2)
        .map((s) => s[0])
        .join("")
        .toUpperCase()
    : "TG";
  return (
    <span className="avatar" aria-hidden="true">
      {initials}
    </span>
  );
}
export function RolePills({ user, roles }: { user: Profile; roles: Role[] }) {
  const enabled = user.roles.filter((r) => r.enabled);
  return (
    <div className="pills">
      {enabled.length ? (
        enabled.map((r) => (
          <span className="pill" key={r.role_id}>
            {roles.find((role) => role.id === r.role_id)?.name || r.role_id}
          </span>
        ))
      ) : (
        <span className="muted">Rol biriktirilmagan</span>
      )}
    </div>
  );
}
export function Next({
  more,
  onNext,
  onPrev,
  canPrev,
}: {
  more: boolean;
  onNext: () => void;
  onPrev: () => void;
  canPrev: boolean;
}) {
  return (
    <div className="paging">
      <span className="muted">
        {more ? "Keyingi sahifada yana bor" : "Ro‘yxat oxiri"}
      </span>
      <div>
        <Button onClick={onPrev} disabled={!canPrev}>
          Oldingi
        </Button>
        <Button onClick={onNext} disabled={!more}>
          Keyingi
          <ArrowRight size={14} />
        </Button>
      </div>
    </div>
  );
}
