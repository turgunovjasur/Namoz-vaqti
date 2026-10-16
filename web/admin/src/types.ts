export type Assignment = {
  role_id: string;
  enabled: boolean;
  capability_ids: string[];
  revision: number;
};
export type Profile = {
  user_id: number;
  telegram_user_id: number;
  profile_type: "admin" | "user";
  display_name: string | null;
  username: string | null;
  is_active: boolean;
  roles: Assignment[];
};
export type Capability = {
  id: string;
  name: string;
  description: string;
  effect: "read" | "write" | "generate";
  entrypoints: ("conversation" | "background")[];
  guidance: string;
};
export type Role = {
  id: string;
  name: string;
  description: string;
  system_role: boolean;
  agent_id: string;
  common_rules: string;
  enabled: boolean;
  revision: number;
  reserved: boolean;
  model: Model;
  capabilities: Capability[];
};
export type Model = {
  role_id: string;
  model_id: string;
  version: number;
  options: string[];
};
export type Change = {
  id: number;
  actor_telegram_id: number;
  target_telegram_id: number | null;
  action: string;
  detail: Record<string, unknown>;
  created_at: string;
};
export type UsersPage = {
  users: Profile[];
  more: boolean;
  counts: { users: number; assigned_users: number };
};
export type AuditPage = { changes: Change[]; more: boolean };
export type GrantDraft = {
  role_id: string;
  enabled: boolean;
  capability_ids: string[];
  expected_revision: number;
};

export type RuleTemplate = { rules: string; revision: number };
