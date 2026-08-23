create table if not exists oauth_tokens (
  id uuid primary key,
  user_id uuid not null,
  provider text not null,
  access_token_enc bytea not null,
  refresh_token_enc bytea not null,
  expires_at timestamptz not null
);

create table if not exists courses (
  id text primary key,
  user_id uuid not null,
  name text not null,
  section text
);

create table if not exists assignments (
  id text primary key,
  course_id text not null references courses(id),
  title text not null,
  due_at timestamptz not null,
  submission_state text not null,
  status text not null,
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create table if not exists agent_runs (
  id uuid primary key,
  assignment_id text not null references assignments(id),
  state text not null,
  attempt integer not null default 0,
  error text,
  started_at timestamptz not null,
  finished_at timestamptz
);

create table if not exists generated_files (
  id uuid primary key,
  assignment_id text not null references assignments(id),
  kind text not null check (kind in ('digest', 'scaffold', 'user_submission')),
  filename text not null,
  storage_path text not null,
  created_at timestamptz not null
);

create table if not exists approval_requests (
  id uuid primary key,
  agent_run_id uuid not null references agent_runs(id),
  type text not null check (type in ('digest_ready', 'ready_to_submit')),
  telegram_message_id text not null,
  responded boolean not null default false,
  response text,
  created_at timestamptz not null
);

create index if not exists idx_assignments_due_at on assignments (due_at);
create index if not exists idx_agent_runs_assignment_started on agent_runs (assignment_id, started_at desc);
create index if not exists idx_generated_files_assignment_kind on generated_files (assignment_id, kind);
