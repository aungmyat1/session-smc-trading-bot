from __future__ import annotations

from pathlib import Path

from ..ai.improvement_engine import SpecificationImprovementEngine
from ..models import (
    AuditIssueBuckets,
    AuditLogEntry,
    AuditSummaryCounts,
    StrategyDocument,
    ValidationReport,
    utc_now,
)
from ..reports.report_generator import ReportGenerator
from ..scoring.scoring_engine import ScoringEngine
from ..validators import (
    AmbiguityValidator,
    InputValidator,
    InstitutionalRuleValidator,
    LogicalConsistencyValidator,
    MeasurabilityValidator,
    RiskValidationValidator,
    RuleCompletenessValidator,
    TestabilityValidator,
)


class StrategyValidationPipeline:
    AMBIGUOUS_FINDING_CODES = {"ambiguous_phrase", "reviewers_may_disagree"}
    MISSING_PARAMETER_FINDING_CODES = {"missing_field", "incomplete_rule_dimension", "missing_risk_control"}
    CONTRADICTION_FINDING_CODES = {
        "conflicting_sessions",
        "conflicting_trade_limits",
        "conflicting_exit_model",
        "spec_implementation_mismatch",
    }
    UNDEFINED_FILTER_FINDING_CODES = {"undefined_institutional_concept", "missing_institutional_context"}
    EXECUTION_CONFLICT_FINDING_CODES = {
        "non_measurable_rule",
        "entry_not_identifiable",
        "exit_not_identifiable",
        "coding_requires_assumptions",
    }

    def __init__(
        self,
        validators: list | None = None,
        scoring_engine: ScoringEngine | None = None,
        improvement_engine: SpecificationImprovementEngine | None = None,
        report_generator: ReportGenerator | None = None,
    ) -> None:
        self.validators = validators or [
            InputValidator(),
            RuleCompletenessValidator(),
            AmbiguityValidator(),
            LogicalConsistencyValidator(),
            MeasurabilityValidator(),
            InstitutionalRuleValidator(),
            RiskValidationValidator(),
            TestabilityValidator(),
        ]
        self.scoring_engine = scoring_engine or ScoringEngine()
        self.improvement_engine = improvement_engine or SpecificationImprovementEngine()
        self.report_generator = report_generator or ReportGenerator()

    def run_document(self, document: StrategyDocument) -> ValidationReport:
        results = [validator.validate(document) for validator in self.validators]
        overall_score = self.scoring_engine.aggregate_score(results)
        overall_status = self.scoring_engine.overall_status(results)
        readiness_decision = self.scoring_engine.readiness_decision(results, overall_score)
        recommendations = self.improvement_engine.build_recommendations(results)
        all_findings = [finding for result in results for finding in result.findings]
        critical_issues = [finding.message for finding in all_findings if finding.severity == "ERROR"]
        warnings = [finding.message for finding in all_findings if finding.severity == "WARN"]
        summary_counts = AuditSummaryCounts(
            ambiguous_rule_count=sum(1 for finding in all_findings if finding.code in self.AMBIGUOUS_FINDING_CODES),
            missing_parameter_count=sum(1 for finding in all_findings if finding.code in self.MISSING_PARAMETER_FINDING_CODES),
            contradiction_count=sum(1 for finding in all_findings if finding.code in self.CONTRADICTION_FINDING_CODES),
            undefined_filter_count=sum(1 for finding in all_findings if finding.code in self.UNDEFINED_FILTER_FINDING_CODES),
            execution_conflict_count=sum(1 for finding in all_findings if finding.code in self.EXECUTION_CONFLICT_FINDING_CODES),
        )
        issue_buckets = AuditIssueBuckets(
            fatal_blockers=critical_issues,
            revision_required_issues=warnings,
            improvement_only_recommendations=[item.message for item in recommendations if item.message],
        )
        audit_log = [
            AuditLogEntry(
                validator_name=validator.name,
                version=validator.version,
                document_hash=document.document_hash,
                created_at=utc_now(),
                result_status=result.status,
                result_score=result.score,
            )
            for validator, result in zip(self.validators, results)
        ]
        summary = (
            f"Specification scored {overall_score:.1f}% across {len(results)} validators. "
            f"Decision: {readiness_decision}. "
            f"Counts: ambiguous={summary_counts.ambiguous_rule_count}, "
            f"missing={summary_counts.missing_parameter_count}, "
            f"contradictions={summary_counts.contradiction_count}, "
            f"undefined_filters={summary_counts.undefined_filter_count}, "
            f"execution_conflicts={summary_counts.execution_conflict_count}."
        )
        return ValidationReport(
            strategy_name=document.strategy_name,
            overall_score=overall_score,
            overall_status=overall_status,
            readiness_decision=readiness_decision,
            validator_results=results,
            critical_issues=critical_issues,
            warnings=warnings,
            recommendations=recommendations,
            audit_log=audit_log,
            summary_counts=summary_counts,
            issue_buckets=issue_buckets,
            summary=summary,
            source_path=document.source_path,
            document_hash=document.document_hash,
        )

    def run_text(self, text: str, source_path: str = "") -> ValidationReport:
        return self.run_document(StrategyDocument.from_text(text, source_path=source_path))

    def run_file(self, path: str | Path) -> ValidationReport:
        return self.run_document(StrategyDocument.from_file(path))

    def write_report(self, report: ValidationReport, output_dir: str | Path) -> dict[str, Path]:
        return self.report_generator.write(report, Path(output_dir))
