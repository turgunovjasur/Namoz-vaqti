import { useEffect, useRef, useState } from "react";
import { Save, X } from "lucide-react";
import { api, ApiError, useRemote } from "./api";
import type { Capability, Role, RuleTemplate } from "./types";
import { Button, Failure, Loading, Message } from "./ui";

export function RoleEditor({
  role,
  defaultModel,
  onClose,
  onSaved,
}: {
  role: Role | null;
  defaultModel: Role["model"];
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const {
    data,
    error: loadError,
    loading,
    reload,
  } = useRemote<{ skills: Capability[] }>("/api/skills");
  const [name, setName] = useState(role?.name || ""),
    [description, setDescription] = useState(role?.description || ""),
    [rules, setRules] = useState(role?.common_rules || ""),
    [rulesReady, setRulesReady] = useState(!!role),
    [templateError, setTemplateError] = useState<Error | null>(null),
    [model, setModel] = useState(role?.model.model_id || defaultModel.model_id),
    [enabled, setEnabled] = useState(role?.enabled ?? true),
    [selected, setSelected] = useState<string[]>(
      role?.capabilities.map((c) => c.id) || [],
    ),
    [query, setQuery] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | null>(null),
    [dirty, setDirty] = useState(false);
  useEffect(() => {
    dialog.current?.showModal();
    return () => dialog.current?.close();
  }, []);
  useEffect(() => {
    if (role) return;
    let live = true;
    api<RuleTemplate>("/api/role-template")
      .then((t) => {
        if (live) {
          setRules(t.rules);
          setRulesReady(true);
        }
      })
      .catch((e) => {
        if (live) setTemplateError(e);
      });
    return () => {
      live = false;
    };
  }, [role]);
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (dirty) e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  function close() {
    if (
      !busy &&
      (!dirty || window.confirm("Saqlanmagan o‘zgarishlar bekor qilinsinmi?"))
    )
      onClose();
  }
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api(role ? `/api/roles/${role.id}` : "/api/roles", {
        method: role ? "PUT" : "POST",
        body: JSON.stringify({
          name,
          description,
          common_rules: rules,
          model_id: model,
          capability_ids: selected,
          enabled,
          expected_revision: role?.revision || 0,
          expected_model_version: role?.model.version || 0,
        }),
      });
      setDirty(false);
      await onSaved();
      onClose();
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
      aria-labelledby="role-editor-title"
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
    >
      <form
        onSubmit={save}
        className="role-form"
        onChange={() => setDirty(true)}
      >
        <div className="sheet-head">
          <span id="role-editor-title">
            {role ? "Rolni tahrirlash" : "Rol qo‘shish"}
          </span>
          <Button
            type="button"
            className="icon-button"
            aria-label="Rol formasini yopish"
            onClick={close}
            disabled={busy}
          >
            <X size={21} />
          </Button>
        </div>
        <div className="sheet-body">
          {loading ? (
            <Loading />
          ) : loadError ? (
            <Failure error={loadError} retry={reload} />
          ) : (
            <>
              <p className="muted intro">
                {role?.id === "assistant"
                  ? "Yagona yordamchi barcha foydalanuvchilarning xabarlarini qabul qiladi, agentlarga topshiriq beradi va natijani yetkazadi."
                  : "Har rol o‘z vazifasi, Gemini modeli va skilllari bilan alohida agent bo‘ladi. Yangi rol foydalanuvchilarga avtomatik biriktirilmaydi."}
              </p>
              <label className="form-field">
                Rol nomi
                <input
                  required
                  maxLength={100}
                  value={name}
                  disabled={
                    busy || (role?.system_role && role.id !== "assistant")
                  }
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
              <label className="form-field">
                Vazifasi
                <textarea
                  required
                  maxLength={2000}
                  rows={4}
                  value={description}
                  disabled={
                    busy || (role?.system_role && role.id !== "assistant")
                  }
                  onChange={(e) => setDescription(e.target.value)}
                />
              </label>
              <label className="form-field">
                Gemini modeli
                <select
                  value={model}
                  disabled={busy}
                  onChange={(e) => setModel(e.target.value)}
                >
                  {Array.from(
                    new Set([
                      model,
                      ...(role?.model.options || defaultModel.options),
                    ]),
                  ).map((m) => (
                    <option key={m}>{m}</option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                Umumiy qoidalar
                <textarea
                  maxLength={8000}
                  rows={7}
                  value={rules}
                  disabled={busy || !rulesReady}
                  onChange={(e) => setRules(e.target.value)}
                />
                <small>
                  Bu qoidalar faqat shu agentga tegishli. Ruxsatlar va bajarish
                  tekshiruvlari backendda qoladi.
                </small>
              </label>
              {templateError ? (
                <Message error>
                  Shablonni yuklab bo‘lmadi. Formani qayta oching.
                </Message>
              ) : null}
              {!role?.system_role ? (
                <label className="capability">
                  <input
                    type="checkbox"
                    checked={enabled}
                    disabled={busy}
                    onChange={(e) => setEnabled(e.target.checked)}
                  />
                  <span>
                    <strong>Rol faol</strong>
                    <small>
                      O‘chirilsa, unga biriktirilgan barcha foydalanuvchilar
                      uchun ishlash to‘xtaydi.
                    </small>
                  </span>
                </label>
              ) : (
                <p className="muted">
                  {role.id === "assistant"
                    ? "Yordamchi doim faol. Uni o‘chirib yoki nofaol qilib bo‘lmaydi. Nomi, vazifasi, modeli va umumiy qoidalarini tahrirlashingiz mumkin."
                    : "Tizim rolining nomi, vazifasi va skilllari himoyalangan."}
                </p>
              )}
              {!role?.system_role ? (
                <>
                  <h3>Skilllar · {selected.length} ta tanlandi</h3>
                  <p className="muted">
                    Bu rol nimalarni bajara olishini tanlang. Userga shu roldagi
                    ruxsatlar keyin alohida beriladi.
                  </p>
                  <label className="form-field">
                    Skill qidirish
                    <input
                      type="search"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </label>
                  <div className="skill-options">
                    {data?.skills
                      .filter((c) =>
                        (c.name + " " + c.description)
                          .toLocaleLowerCase()
                          .includes(query.toLocaleLowerCase()),
                      )
                      .map((c) => (
                        <label className="capability" key={c.id}>
                          <input
                            type="checkbox"
                            checked={selected.includes(c.id)}
                            disabled={busy}
                            onChange={(e) =>
                              setSelected((old) =>
                                e.target.checked
                                  ? [...old, c.id]
                                  : old.filter((id) => id !== c.id),
                              )
                            }
                          />
                          <span>
                            <strong>{c.name}</strong>
                            <small>{c.description}</small>
                            {c.entrypoints.includes("background") ? (
                              <small>Avtomatik yuborish</small>
                            ) : null}
                          </span>
                        </label>
                      ))}
                  </div>
                </>
              ) : null}
              {error ? (
                <Message error>
                  {error.message}
                  {error instanceof ApiError && error.status === 409 ? (
                    <p>
                      Formani yoping va rolni qayta oching; joriy tahrir
                      saqlanmadi.
                    </p>
                  ) : null}
                </Message>
              ) : null}
            </>
          )}
        </div>
        <div className="sheet-footer">
          <span className="muted">
            {busy
              ? "Model tekshirilmoqda va saqlanmoqda…"
              : role
                ? `Tahrir ${role.revision}`
                : "Alohida Gemini agent"}
          </span>
          <Button
            type="submit"
            className="primary"
            busy={busy}
            disabled={loading || !!loadError || !rulesReady || !dirty}
          >
            <Save size={16} />
            {role ? "Saqlash" : "Rol yaratish"}
          </Button>
        </div>
      </form>
    </dialog>
  );
}
