-- ─── Demo incidents for 12 new industries ──────────────────────────────────

INSERT INTO incidents (stage, severity, description, status, industry) VALUES

-- Energy & Grid Operations
('generation_dispatch',  'high',   'Grid demand exceeding generation capacity. Frequency deviation detected across Texas region.', 'open', 'energy'),
('transmission_routing', 'high',   'Transmission line congestion on I-10 corridor. Load balancing algorithm overloaded.', 'open', 'energy'),
('load_balancing',       'medium', 'Renewable intermittency causing voltage fluctuations. Battery storage buffer at 12%.', 'open', 'energy'),

-- Water & Utilities
('intake_processing',    'high',   'Raw water intake queue above safe capacity. Turbidity levels triggering extended treatment.', 'open', 'water'),
('treatment_filtration', 'high',   'Filtration throughput below minimum. Backwash cycle overdue by 6 hours.', 'open', 'water'),
('distribution_pumping', 'medium', 'Pump station 3 running at 94% capacity. Pressure dropping in zones 7-9.', 'open', 'water'),

-- Road & Traffic
('highway_merging',      'high',   'I-95 merge zone at standstill. Throughput dropped to 12% of capacity. Incident upstream.', 'open', 'traffic'),
('toll_processing',      'high',   'Electronic toll collection queue exceeded 200 vehicles. Manual lanes overwhelmed.', 'open', 'traffic'),
('signal_coordination',  'medium', 'Traffic signal sync failure at 3 intersections. Average delay 4x baseline.', 'open', 'traffic'),

-- Telecommunications
('call_routing',         'high',   'Call routing queue at 340% of normal. IVR overflow triggered. Average wait 18 minutes.', 'open', 'telecom'),
('network_provisioning', 'high',   'New connection provisioning backlog at 2,400 tickets. SLA breach in 4 hours.', 'open', 'telecom'),
('fault_resolution',     'medium', 'Field technician dispatch queue elevated. Average fault resolution time 3x SLA.', 'open', 'telecom'),

-- Manufacturing
('raw_material_intake',  'high',   'Incoming material inspection queue at 340 units. Conveyor line starvation imminent.', 'open', 'manufacturing'),
('assembly_line',        'high',   'Line 3 throughput dropped 40%. Robotic welder cycle time above threshold.', 'open', 'manufacturing'),
('quality_inspection',   'medium', 'QC rejection rate elevated. Rework queue building. Downstream packaging at risk.', 'open', 'manufacturing'),

-- Retail Operations
('checkout_processing',  'high',   'Average checkout wait 22 minutes. Self-checkout failure rate 34%. Abandonment rising.', 'open', 'retail'),
('inventory_replenishment','high', 'Stockout rate 18% across high-velocity SKUs. Replenishment cycle 2x above baseline.', 'open', 'retail'),
('returns_desk',         'medium', 'Returns processing queue at 180 items. Average resolution 45 minutes vs 15 min SLA.', 'open', 'retail'),

-- Food & Restaurant
('order_taking',         'high',   'Order queue at 47 tickets. Kitchen communication breakdown. Average wait 38 minutes.', 'open', 'food'),
('food_preparation',     'high',   'Prep throughput dropped 55%. Chef shortage during Friday dinner rush. 23 tables waiting.', 'open', 'food'),
('delivery_dispatch',    'medium', 'Delivery queue at 34 orders. Average dispatch time 28 minutes vs 8 minute target.', 'open', 'food'),

-- Pharmaceutical
('raw_material_testing', 'high',   'QC lab backlog at 48 batches. HPLC instrument downtime extending release cycle by 6hrs.', 'open', 'pharma'),
('manufacturing_batch',  'high',   'Batch processing queue exceeded GMP threshold. Contamination risk protocol activated.', 'open', 'pharma'),
('regulatory_review',    'medium', 'Documentation review backlog at 23 submissions. Approval throughput below weekly target.', 'open', 'pharma'),

-- Government Services
('application_intake',   'high',   'Permit application queue at 1,240. Processing time 34 days vs 10 day legal requirement.', 'open', 'government'),
('document_verification','high',   'Identity verification backlog at 890 cases. Staff shortage following budget cuts.', 'open', 'government'),
('payment_processing',   'medium', 'Fee collection system processing time elevated. Online portal queue timeout increasing.', 'open', 'government'),

-- Real Estate
('property_listing',     'high',   'New listing review queue at 340. Average approval time 8 days vs 48 hour target.', 'open', 'realestate'),
('inspection_scheduling','high',   'Home inspection backlog at 180 properties. Inspector availability critically low.', 'open', 'realestate'),
('closing_processing',   'medium', 'Title search and closing document queue elevated. Average 22 days vs 15 day SLA.', 'open', 'realestate'),

-- Education
('application_review',   'high',   'Student application queue at 4,200. Admissions staff processing rate below target by 40%.', 'open', 'education'),
('enrollment_processing','high',   'Course enrollment conflicts unresolved for 890 students. Registration system overloaded.', 'open', 'education'),
('financial_aid',        'medium', 'Financial aid processing backlog at 1,100 applications. Disbursement deadline at risk.', 'open', 'education'),

-- Media & Entertainment
('content_ingest',       'high',   'Content upload queue at 2,400 hours of video. Transcoding pipeline at 340% capacity.', 'open', 'media'),
('content_review',       'high',   'Moderation queue at 18,000 items. Auto-review failure rate elevated. SLA breach in 2hrs.', 'open', 'media'),
('distribution_delivery','medium', 'CDN cache miss rate elevated. Stream startup time 4x above baseline in APAC region.', 'open', 'media');
