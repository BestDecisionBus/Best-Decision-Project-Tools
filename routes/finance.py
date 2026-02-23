from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required

import database

finance_bp = Blueprint('finance', __name__)


@finance_bp.before_request
def _check_scheduler_access():
    """Block scheduler role from all finance routes."""
    if not current_user.is_authenticated:
        return
    if current_user.is_scheduler and not current_user.is_bdb:
        abort(403)


def _helpers():
    import app as _app
    return _app


@finance_bp.route("/admin/finance")
@login_required
def finance_dashboard():
    h = _helpers()
    tokens = h._get_tokens_for_user()
    token_str, selected_token = h._get_selected_token(tokens)

    payroll = None
    labor_stats = None
    job_financials = None
    active_jobs = []
    completed_jobs = []
    totals = {}
    kpis = {}
    estimate_stats = None
    expense_totals = None
    income_target_pct = 0
    overhead_pct = 0
    monthly_overhead = 0
    cash_on_hand = 0

    if token_str:
        payroll = database.get_weekly_payroll_estimate(token_str)
        labor_stats = database.get_overall_labor_stats(token_str)
        job_financials = database.get_job_financials(token_str)
        estimate_stats = database.get_estimate_stats(token_str)
        expense_totals = database.get_expense_totals(token_str)

        income_target_pct = selected_token.get("income_target_pct", 0) or 0
        monthly_overhead = selected_token.get("monthly_overhead", 0) or 0
        cash_on_hand = selected_token.get("cash_on_hand", 0) or 0

        for jf in job_financials:
            # Earned revenue: recognize revenue proportional to completion
            earned = jf["budget"] * jf["completion_pct"] / 100
            jf["earned_revenue"] = round(earned, 2)
            jf["unearned_liability"] = round(jf["actual_collected"] - earned, 2)
            if jf["is_active"]:
                active_jobs.append(jf)
            else:
                completed_jobs.append(jf)

        # Company totals across all jobs
        t_budget = sum(j["budget"] for j in job_financials)
        t_est_cost = sum(j["est_total_cost"] for j in job_financials)
        t_actual_cost = sum(j["actual_total_cost"] for j in job_financials)
        t_collected = sum(j["actual_collected"] for j in job_financials)
        t_earned = sum(j["earned_revenue"] for j in job_financials)
        t_unearned = round(t_collected - t_earned, 2)
        # Use earned revenue for margin calculations
        t_margin = t_earned - t_actual_cost
        t_margin_pct = round((t_margin / t_earned) * 100, 1) if t_earned else 0
        t_budget_pct = round((t_actual_cost / t_est_cost) * 100, 1) if t_est_cost else 0

        # WIP Income vs Completion: actual collected vs expected collected at current completion
        wip_expected_income = sum(
            j["budget"] * j["completion_pct"] / 100 for j in active_jobs
        )
        wip_actual_income = sum(j["actual_collected"] for j in active_jobs)
        # ratio: 1.0 = even, >1 = ahead, <1 = behind
        wip_income_ratio = round(
            wip_actual_income / wip_expected_income, 3
        ) if wip_expected_income else (1.0 if not active_jobs else 0.0)

        # WIP Expenses vs Completion: actual cost vs expected cost at current completion
        wip_expected_cost = sum(
            j["est_total_cost"] * j["completion_pct"] / 100 for j in active_jobs
        )
        wip_actual_cost = sum(j["actual_total_cost"] for j in active_jobs)
        # ratio: 1.0 = even, <1 = under budget (good), >1 = over budget (bad)
        wip_expense_ratio = round(
            wip_actual_cost / wip_expected_cost, 3
        ) if wip_expected_cost else (1.0 if not active_jobs else 0.0)

        totals = {
            "budget": round(t_budget, 2),
            "est_cost": round(t_est_cost, 2),
            "actual_cost": round(t_actual_cost, 2),
            "collected": round(t_collected, 2),
            "earned": round(t_earned, 2),
            "unearned": t_unearned,
            "margin": round(t_margin, 2),
            "margin_pct": t_margin_pct,
            "budget_pct": t_budget_pct,
            "wip_income_ratio": wip_income_ratio,
            "wip_expense_ratio": wip_expense_ratio,
            "wip_expected_income": round(wip_expected_income, 2),
            "wip_actual_income": round(wip_actual_income, 2),
            "wip_expected_cost": round(wip_expected_cost, 2),
            "wip_actual_cost": round(wip_actual_cost, 2),
        }

        # Calculate overhead % from monthly overhead dollar amount
        if monthly_overhead > 0 and t_earned > 0:
            overhead_pct = round((monthly_overhead * 12) / t_earned * 100, 1)
        else:
            overhead_pct = 0

        # Executive KPIs — use earned revenue for income calculations
        pipeline_value = estimate_stats["pending"]["total"] if estimate_stats else 0
        contracted_revenue = (
            (estimate_stats["accepted"]["total"] if estimate_stats else 0)
            + (estimate_stats["in_progress"]["total"] if estimate_stats else 0)
        )
        total_actual_costs = t_actual_cost
        overhead_amount = round(t_earned * overhead_pct / 100, 2) if overhead_pct else 0
        net_income = round(t_earned - total_actual_costs - overhead_amount, 2)
        net_income_pct = round((net_income / t_earned) * 100, 1) if t_earned else 0
        collection_rate = round((t_collected / contracted_revenue) * 100, 1) if contracted_revenue else 0

        # Required revenue to hit income target given current costs
        divisor = 1 - (overhead_pct / 100) - (income_target_pct / 100)
        if divisor > 0 and total_actual_costs > 0:
            required_revenue = round(total_actual_costs / divisor, 2)
        else:
            required_revenue = 0

        # Backlog Months = contracted revenue / monthly overhead
        backlog_months = round(contracted_revenue / monthly_overhead, 1) if monthly_overhead > 0 else 0

        # Days Cash on Hand = cash / daily overhead ("survival" number)
        daily_overhead = monthly_overhead / 30 if monthly_overhead > 0 else 0
        days_cash_on_hand = int(round(cash_on_hand / daily_overhead, 0)) if daily_overhead > 0 else 0

        # Overbilling/Underbilling: positive = overbilled, negative = underbilled
        overbilling = t_unearned

        # Margin Target = overhead % + income target %
        margin_target = round(overhead_pct + income_target_pct, 1)
        # Markup Required = margin / (1 - margin) — converts margin % to markup %
        markup_required = round(
            margin_target / (100 - margin_target) * 100, 1
        ) if margin_target < 100 else 0

        kpis = {
            "pipeline_value": round(pipeline_value, 2),
            "contracted_revenue": round(contracted_revenue, 2),
            "revenue_collected": round(t_collected, 2),
            "earned_revenue": round(t_earned, 2),
            "unearned_liability": t_unearned,
            "total_actual_costs": round(total_actual_costs, 2),
            "overhead_amount": overhead_amount,
            "net_income": net_income,
            "net_income_pct": net_income_pct,
            "income_target_pct": income_target_pct,
            "collection_rate": collection_rate,
            "required_revenue": required_revenue,
            "backlog_months": backlog_months,
            "days_cash_on_hand": days_cash_on_hand,
            "overbilling": round(overbilling, 2),
            "margin_target": margin_target,
            "markup_required": markup_required,
        }

    return render_template(
        "admin/finance_dashboard.html",
        tokens=tokens,
        selected_token=selected_token,
        payroll=payroll,
        labor_stats=labor_stats,
        active_jobs=active_jobs,
        completed_jobs=completed_jobs,
        totals=totals,
        kpis=kpis,
        estimate_stats=estimate_stats,
        expense_totals=expense_totals,
        income_target_pct=income_target_pct,
        overhead_pct=overhead_pct,
        monthly_overhead=monthly_overhead,
        cash_on_hand=cash_on_hand,
    )


@finance_bp.route("/admin/finance/update-targets", methods=["POST"])
@login_required
def finance_update_targets():
    h = _helpers()
    data = request.get_json()
    if not data:
        abort(400)
    token_str = data.get("token", "").strip()
    h._verify_token_access(token_str)
    if not current_user.is_bdb and current_user.role not in ("admin", "viewer"):
        abort(403)
    try:
        itp = float(data.get("income_target_pct", 0))
        mo = float(data.get("monthly_overhead", 0))
        coh = float(data.get("cash_on_hand", 0))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid value."}), 400
    database.update_token_finance_targets(token_str, itp, 0,
                                         monthly_overhead=mo, cash_on_hand=coh)
    return jsonify({"success": True})
