/** Shared types mirroring the deployed ReleaseGuard contract output. */

export type CheckStatus =
  | "PASS"
  | "FAIL"
  | "FETCH_FAILED"
  | "INSUFFICIENT_EVIDENCE"
  | string;

export type Verdict = "VERIFIED" | "REJECTED" | "INCONCLUSIVE" | string;

export interface CheckResult {
  check_name: string;
  status: CheckStatus;
  evidence: string;
  reason: string;
}

export interface Verification {
  id: string;
  project_name: string;
  version: string;
  evidence_url: string;
  policy_text: string;
  /** PENDING | RUNNING | COMPLETED | FAILED */
  status: string;
  /** VERIFIED | REJECTED | INCONCLUSIVE (healthiest known value or "") */
  verdict: string;
  reason_code: string;
  failed_checks: string;
  results: CheckResult[];
}

export interface TxProgressStep {
  key: string;
  label: string;
  state: "idle" | "active" | "done" | "error";
}
