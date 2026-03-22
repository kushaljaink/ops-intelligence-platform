-- Refresh Construction Management demo incidents with PM-style workflow stages.
-- Run manually against Supabase/Postgres when you want seeded demo incidents updated.

DELETE FROM incidents
WHERE industry = 'construction'
  AND user_id IS NULL;

INSERT INTO incidents (stage, severity, description, status, industry, user_id) VALUES
('permits_approvals', 'high', 'Permit approval backlog at 7 submittals. Average review cycle is 58 hours, blocking site mobilization and pushing site prep start dates.', 'open', 'construction', NULL),
('site_prep', 'medium', 'Site prep sequence is slipping because erosion-control release is still pending. Two work areas are ready but cannot be opened without the approval package.', 'open', 'construction', NULL),
('foundation', 'medium', 'Concrete pour readiness is on hold pending anchor bolt confirmation and rebar inspection signoff. Foundation crew is at risk of losing a scheduled pour window.', 'open', 'construction', NULL),
('framing', 'high', 'Framing crew idle risk is rising. Layout is complete in only 1 of 4 planned zones because upstream foundation turnover is late and lumber delivery is partially held.', 'open', 'construction', NULL),
('mep_rough_in', 'high', 'MEP subcontractor delay is blocking rough-in across three rooms. Ductwork release is late and electrical rough-in cannot finish before the next inspection window.', 'open', 'construction', NULL),
('inspection', 'high', 'Inspection scheduling delay has created a 5-request backlog. Failed rough-in items from the last visit still need isolated rework before reinspection can proceed.', 'open', 'construction', NULL),
('finishing', 'medium', 'Material delivery hold on doors and ceiling grid is reducing daily completion throughput. Finishing crews are resequencing around unavailable areas to avoid downtime.', 'open', 'construction', NULL),
('handover', 'high', 'Punch-list backlog remains above turnover target with 18 open owner-facing items. Downstream handover dates are slipping because upstream finishes and closeout documentation are incomplete.', 'open', 'construction', NULL);
