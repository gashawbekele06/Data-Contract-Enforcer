export interface ReportData {
  report_id: string
  generated_at: string
  report_date: string
  data_health_score: number
  health_narrative: string
  validation_summary: {
    total_checks: number
    passed: number
    failed: number
    warned: number
    reports_analyzed: number
  }
  violations_this_week: {
    total: number
    by_severity: Record<string, number>
    top_violations: TopViolation[]
  }
  schema_changes_detected: SchemaChange[]
  ai_risk_assessment: AIRiskAssessment
  recommended_actions: RecommendedAction[]
}

export interface TopViolation {
  violation_id: string
  check_id: string
  severity: string
  system: string
  field: string
  message: string
  downstream_impact: string
}

export interface SchemaChange {
  contract_id: string
  change_type: string
  column: string
  backward_compatible: boolean
  compatibility_verdict: string
  required_action: string
}

export interface AIRiskAssessment {
  overall_ai_status: string
  embedding_drift_status: string
  embedding_drift_score: number | null
  embedding_threshold: number
  prompt_input_violation_rate: number | null
  llm_output_violation_rate: number | null
  llm_output_trend: string
  trace_schema_status: string
  narrative: string
}

export interface RecommendedAction {
  priority: number
  severity: string
  action: string
  affected_pipelines: string[]
}

export interface ValidationReport {
  report_id: string
  contract_id: string
  snapshot_id: string
  run_timestamp: string
  injected_violation: boolean
  total_checks: number
  passed: number
  failed: number
  warned: number
  errored: number
  results: CheckResult[]
}

export interface CheckResult {
  check_id: string
  column_name: string
  check_type: string
  status: 'PASS' | 'FAIL' | 'WARN' | 'ERROR'
  actual_value: string
  expected: string
  severity: string
  records_failing: number
  sample_failing: string[]
  message: string
}

export interface Violation {
  violation_id: string
  check_id: string
  contract_id: string
  column_name: string
  severity: string
  message: string
  actual_value: string
  expected: string
  records_failing: number
  detected_at: string
  blame_chain: BlameEntry[]
  blast_radius: BlastRadius
}

export interface BlameEntry {
  rank: number
  file_path: string
  commit_hash: string
  author: string
  commit_timestamp: string
  commit_message: string
  confidence_score: number
  lineage_hops?: number
}

export interface BlastRadius {
  registry_subscribers?: RegistrySubscriber[]
  affected_nodes: string[]
  affected_pipelines: string[]
  estimated_records: number
  blast_radius_source?: string
}

export interface RegistrySubscriber {
  subscriber_id: string
  subscriber_team: string
  validation_mode: string
  contact: string
  fields_consumed: string[]
  breaking_field: string
  breaking_reason: string
  contamination_depth?: number
}

export interface Subscription {
  contract_id: string
  subscriber_id: string
  subscriber_team: string
  fields_consumed: string[]
  breaking_fields: Array<{ field: string; reason: string } | string>
  validation_mode: string
  registered_at: string
  contact: string
}

export interface ContractFile {
  name: string
  contract_id: string
  title: string
  version: string
  owner: string
  clause_count: number
  downstream_count: number
  path: string
}

export interface DatasetSummary {
  contract_id: string
  label: string
  latest_passed: number
  latest_failed: number
  latest_total: number
  latest_timestamp: string
  pass_rate: number
}
