-- Add user_id to incidents (NULL = demo data visible to all)
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS user_id UUID DEFAULT NULL;

-- Add user_id to workflow_metrics
ALTER TABLE workflow_metrics ADD COLUMN IF NOT EXISTS user_id UUID DEFAULT NULL;

-- Add user-specific api_keys table for webhook authentication
CREATE TABLE IF NOT EXISTS user_api_keys (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL,
  api_key TEXT NOT NULL UNIQUE DEFAULT encode(gen_random_bytes(32), 'hex'),
  label TEXT DEFAULT 'Default',
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for fast user filtering
CREATE INDEX IF NOT EXISTS idx_incidents_user_id ON incidents(user_id);
CREATE INDEX IF NOT EXISTS idx_metrics_user_id ON workflow_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key ON user_api_keys(api_key);
