import { useState } from "react";
import {
  ArrowUpRight,
  Search,
  SlidersHorizontal,
  UserRoundCheck,
  Users,
} from "lucide-react";
import { useDebounced, useRemote } from "./api";
import type { Profile, Role, UsersPage as Page } from "./types";
import {
  Avatar,
  Button,
  Empty,
  Failure,
  Loading,
  nameOf,
  Next,
  RolePills,
} from "./ui";
import { UserEditor } from "./UserEditor";

export function UsersPage({ roles }: { roles: Role[] }) {
  const [search, setSearch] = useState(""),
    [filter, setFilter] = useState(""),
    [cursors, setCursors] = useState<number[]>([]),
    [selected, setSelected] = useState<Profile | null>(null);
  const q = useDebounced(search),
    after = cursors.at(-1) || 0;
  const params = new URLSearchParams({
    q,
    after_id: String(after),
    limit: "20",
  });
  if (filter) params.set("role_id", filter);
  const { data, error, loading, reload } = useRemote<Page>(
    `/api/users?${params}`,
  );
  const specialists = roles.filter((r) => !r.system_role),
    capCount = new Set(
      specialists.flatMap((r) => r.capabilities.map((c) => c.id)),
    ).size;
  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">BOSHQARUV</div>
          <h1>Foydalanuvchilar</h1>
          <p>Har bir foydalanuvchiga mos rollar va imkoniyatlar.</p>
        </div>
        <span className="connection">
          <span />
          Server bilan bog‘langan
        </span>
      </header>
      <div className="stats">
        <div>
          <span>Foydalanuvchilar</span>
          <strong>{data ? data.counts.users : "—"}</strong>
          <Users size={22} />
        </div>
        <div>
          <span>Rol biriktirilgan</span>
          <strong>{data ? data.counts.assigned_users : "—"}</strong>
          <UserRoundCheck size={22} />
        </div>
        <div>
          <span>Mutaxassis rollar</span>
          <strong>
            {specialists.length}
            <small> / {capCount} imkoniyat</small>
          </strong>
          <SlidersHorizontal size={22} />
        </div>
      </div>
      <section
        className="surface users-surface"
        aria-label="Foydalanuvchilar ro‘yxati"
      >
        <div className="table-toolbar">
          <label className="search">
            <Search size={18} />
            <input
              aria-label="Foydalanuvchini qidirish"
              placeholder="Ism, @username yoki Telegram ID"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setCursors([]);
              }}
            />
          </label>
          <select
            aria-label="Rol bo‘yicha saralash"
            value={filter}
            onChange={(e) => {
              setFilter(e.target.value);
              setCursors([]);
            }}
          >
            <option value="">Barcha rollar</option>
            {specialists.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
          <Button
            className="icon-button"
            aria-label="Ro‘yxatni yangilash"
            onClick={reload}
          >
            <span className="refresh-symbol">↻</span>
          </Button>
        </div>
        {loading ? (
          <Loading />
        ) : error ? (
          <Failure error={error} retry={reload} />
        ) : data?.users.length ? (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>FOYDALANUVCHI</th>
                    <th>TELEGRAM ID</th>
                    <th>ROLLAR</th>
                    <th>PROFIL</th>
                    <th>
                      <span className="sr-only">Ochish</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.users.map((user) => (
                    <tr key={user.user_id} onClick={() => setSelected(user)}>
                      <td>
                        <button
                          className="person-button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelected(user);
                          }}
                        >
                          <div className="identity">
                            <Avatar user={user} />
                            <div>
                              <strong>{nameOf(user)}</strong>
                              <span>
                                {user.username
                                  ? `@${user.username}`
                                  : "Telegram foydalanuvchisi"}
                              </span>
                            </div>
                          </div>
                        </button>
                      </td>
                      <td className="mono id-cell">{user.telegram_user_id}</td>
                      <td>
                        <RolePills user={user} roles={roles} />
                      </td>
                      <td>
                        <span
                          className={`account-kind ${user.profile_type === "admin" ? "admin" : ""}`}
                        >
                          {user.profile_type === "admin" ? "Admin" : "User"}
                        </span>
                      </td>
                      <td>
                        <ArrowUpRight
                          className="row-arrow"
                          size={17}
                          aria-hidden="true"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Next
              more={data.more}
              canPrev={cursors.length > 0}
              onPrev={() => setCursors((c) => c.slice(0, -1))}
              onNext={() =>
                setCursors((c) => [...c, data.users.at(-1)!.user_id])
              }
            />
          </>
        ) : (
          <Empty title="Foydalanuvchi topilmadi">
            {search || filter
              ? "Qidiruv yoki rol filtrini o‘zgartiring."
              : "Botga /start yuborgan foydalanuvchilar shu yerda ko‘rinadi."}
          </Empty>
        )}
      </section>
      <p className="page-footnote">
        Profilni ochish uchun foydalanuvchini tanlang. Yordamchi barcha
        foydalanuvchilar bilan muloqot qiladi.
      </p>
      {selected ? (
        <UserEditor
          key={selected.user_id}
          user={selected}
          roles={roles}
          onClose={() => setSelected(null)}
          onSaved={(value) => {
            setSelected(value);
            reload();
          }}
        />
      ) : null}
    </>
  );
}
