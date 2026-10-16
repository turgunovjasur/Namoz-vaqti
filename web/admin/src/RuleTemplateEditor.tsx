import { useState } from "react";
import { api, useRemote } from "./api";
import type { RuleTemplate } from "./types";
import { Button, Failure, Loading, Message } from "./ui";
function TemplateForm({
  initial,
  onReload,
}: {
  initial: RuleTemplate;
  onReload: () => void;
}) {
  const [rules, setRules] = useState(initial.rules),
    [current, setCurrent] = useState(initial),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | null>(null),
    [saved, setSaved] = useState(false);
  async function save() {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const value = await api<RuleTemplate>("/api/role-template", {
        method: "PUT",
        body: JSON.stringify({ rules, expected_revision: current.revision }),
      });
      setCurrent(value);
      setSaved(true);
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <p className="muted">
        Yangi rol yaratilganda shu matn uning formasiga ko‘chiriladi. Mavjud
        agentlarning qoidalari o‘zgarmaydi.
      </p>
      <label className="form-field">
        Yangi rollar uchun umumiy qoidalar
        <textarea
          rows={7}
          maxLength={8000}
          value={rules}
          onChange={(e) => {
            setRules(e.target.value);
            setSaved(false);
          }}
          disabled={busy}
        />
      </label>
      <div className="template-actions">
        <span className="muted">Shablon tahriri {current.revision}</span>
        <Button
          className="primary"
          onClick={save}
          busy={busy}
          disabled={rules === current.rules}
        >
          Shablonni saqlash
        </Button>
      </div>
      {error ? (
        <Message error>
          {error.message}
          <Button
            onClick={() => {
              if (
                window.confirm("Tahrir bekor qilinib, yangi shablon olinsinmi?")
              )
                onReload();
            }}
          >
            Qayta yuklash
          </Button>
        </Message>
      ) : saved ? (
        <Message>Shablon saqlandi.</Message>
      ) : null}
    </>
  );
}
export function RuleTemplateEditor() {
  const { data, error, loading, reload } =
    useRemote<RuleTemplate>("/api/role-template");
  return (
    <details className="surface template-editor">
      <summary>Umumiy qoidalar shabloni</summary>
      {loading ? (
        <Loading />
      ) : error ? (
        <Failure error={error} retry={reload} />
      ) : data ? (
        <TemplateForm key={data.revision} initial={data} onReload={reload} />
      ) : null}
    </details>
  );
}
