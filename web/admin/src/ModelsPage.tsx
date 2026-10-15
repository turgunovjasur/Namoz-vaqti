import { useState } from "react";
import { Cpu, Info, Save } from "lucide-react";
import { api, ApiError, useRemote } from "./api";
import type { Model, Role } from "./types";
import { Button, Failure, Loading, Message } from "./ui";
function ModelRow({
  model,
  role,
  onReload,
}: {
  model: Model;
  role: Role;
  onReload: () => void;
}) {
  const [choice, setChoice] = useState(model.model_id),
    [current, setCurrent] = useState(model),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | null>(null),
    [success, setSuccess] = useState(false);
  async function save() {
    setBusy(true);
    setError(null);
    setSuccess(false);
    try {
      const value = await api<Model>(`/api/models/${role.id}`, {
        method: "PUT",
        body: JSON.stringify({
          model_id: choice,
          expected_version: current.version,
        }),
      });
      setCurrent({ ...value, options: model.options });
      setSuccess(true);
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="model-row">
      <div className="model-description">
        <span className="role-mark">
          <Cpu size={20} />
        </span>
        <div>
          <h2>{role.name}</h2>
          <p>{role.description}</p>
          <span className="version">
            Versiya {current.version} · Global sozlama
          </span>
        </div>
      </div>
      <div className="model-controls">
        <label htmlFor={`model-${role.id}`}>Gemini modeli</label>
        <div>
          <select
            id={`model-${role.id}`}
            value={choice}
            disabled={busy}
            onChange={(e) => {
              setChoice(e.target.value);
              setSuccess(false);
              setError(null);
            }}
          >
            {Array.from(new Set([current.model_id, ...model.options])).map(
              (id) => (
                <option key={id}>{id}</option>
              ),
            )}
          </select>
          <Button
            className="primary"
            onClick={save}
            busy={busy}
            disabled={choice === current.model_id}
          >
            <Save size={15} />
            {busy ? "Tekshirilmoqda…" : "Saqlash"}
          </Button>
        </div>
        {error ? (
          <Message error>
            {error.message}
            {error instanceof ApiError && error.status === 409 ? (
              <Button onClick={onReload}>Sozlamalarni yangilash</Button>
            ) : null}
          </Message>
        ) : success ? (
          <Message>Model tekshirildi va saqlandi.</Message>
        ) : null}
      </div>
    </section>
  );
}
export function ModelsPage({ roles }: { roles: Role[] }) {
  const { data, error, loading, reload } = useRemote<{ models: Model[] }>(
    "/api/models",
  );
  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">AI SOZLAMALARI</div>
          <h1>Har rolga mos model</h1>
          <p>Yordamchi va mutaxassislar ishlatadigan Gemini modellari.</p>
        </div>
      </header>
      <div className="info-strip">
        <Info size={20} />
        <p>
          Bu sozlama <strong>barcha foydalanuvchilarga</strong> ta’sir qiladi.
          Saqlashdan oldin model Gemini orqali tekshiriladi; bu API sarfiga
          kirishi mumkin. Yangi model ro‘yxati serverdagi GEMINI_ALLOWED_MODELS
          orqali belgilanadi.
        </p>
      </div>
      <div className="surface">
        {loading ? (
          <Loading />
        ) : error ? (
          <Failure error={error} retry={reload} />
        ) : (
          data?.models.map((model) => (
            <ModelRow
              key={`${model.role_id}:${model.version}`}
              model={model}
              role={roles.find((r) => r.id === model.role_id)!}
              onReload={reload}
            />
          ))
        )}
      </div>
    </>
  );
}
