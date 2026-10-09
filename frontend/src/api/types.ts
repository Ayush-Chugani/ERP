export type Me = {
  user_id: number;
  username: string;
  email: string;
  full_name: string;
  is_superuser: boolean;
  must_change_password: boolean;
  mfa_enabled: boolean;
  roles: string[];
  permissions: string[];
  access_modules: string[];
  student_ids: number[];
  employee_ids: number[];
};

export type Page<T> = { count: number; page: number; page_size: number; next: number | null; previous: number | null; results: T[] };
export type Row = Record<string, unknown> & { labels?: Record<string, string>; actions?: ActionInfo[]; workflow_status?: string | null };

export type ActionInfo = { name: string; label: string; remarks: 'none' | 'optional' | 'required'; danger?: boolean };
export type Can = { read: boolean; create: boolean; update: boolean; delete: boolean; export: boolean };

export type ResourceSummary = {
  path: string;
  table: string;
  title: string;
  module: string;
  label_columns: string[];
  list_columns: string[];
  status_column: string | null;
  read_only: boolean;
  searchable: boolean;
  can: Can;
  actions: (ActionInfo & { from: string[]; to: string })[];
};

export type ColumnMeta = {
  name: string;
  label: string;
  kind: 'string' | 'text' | 'int' | 'decimal' | 'bool' | 'date' | 'datetime' | 'time' | 'json' | 'enum';
  required: boolean;
  nullable: boolean;
  readonly: boolean;
  max_length: number | null;
  choices: string[] | null;
  primary: boolean;
  references: { path: string; title: string } | null;
};

export type ResourceMeta = ResourceSummary & { primary_key: string; columns: ColumnMeta[] };
export type MetaGroups = { groups: { title: string; resources: ResourceSummary[] }[] };

export type Tile = { label: string; value: number; link: string };
export type Dashboard = { tiles: Tile[]; unread_notifications: number };
export type Notice = { notification_id: number; title: string; body: string | null; link: string | null; created_at: string; read_at: string | null };
