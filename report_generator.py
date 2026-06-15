"""
变化分析报告模块 - 生成供应商-货类维度的详细增减统计分析报告
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Optional


def _format_number(val) -> str:
    """格式化数字，添加千位分隔符"""
    if pd.isna(val) or val == 0:
        return "0"
    return f"{int(val):,}"


def _safe_int(val) -> int:
    """安全转换为整数"""
    if pd.isna(val):
        return 0
    return int(val)


def generate_text_report(comparison_result: Dict, output_path: Optional[str] = None) -> str:
    """
    生成文本格式的变化分析报告

    Args:
        comparison_result: compare_data() 返回的结果字典
        output_path: 输出文件路径，如果提供则同时写入文件

    Returns:
        str: 报告文本
    """
    summary = comparison_result['summary']
    additions = comparison_result['additions']
    removals = comparison_result['removals']
    quantity_changes = comparison_result['quantity_changes']

    lines = []
    lines.append("=" * 70)
    lines.append("          港口可贸易资源 - 数据变化分析报告")
    lines.append("=" * 70)
    lines.append("")

    # ---- 总体概览 ----
    lines.append("【一、总体变化概览】")
    lines.append("-" * 50)

    total_old = _safe_int(summary['原数据总量'].sum()) if '原数据总量' in summary.columns else 0
    total_new = _safe_int(summary['新数据总量'].sum()) if '新数据总量' in summary.columns else 0
    total_add_qty = _safe_int(summary['新增数量'].sum()) if '新增数量' in summary.columns else 0
    total_rem_qty = _safe_int(summary['减少数量'].sum()) if '减少数量' in summary.columns else 0
    total_net = total_new - total_old

    lines.append(f"  原数据总量: {_format_number(total_old)} 吨")
    lines.append(f"  新数据总量: {_format_number(total_new)} 吨")
    lines.append(f"  总量变化:   {_format_number(total_net)} 吨")
    lines.append(f"  新增数量:   {_format_number(total_add_qty)} 吨 ({len(additions)} 笔)")
    lines.append(f"  减少数量:   {_format_number(total_rem_qty)} 吨 ({len(removals)} 笔)")
    lines.append(f"  数量变更:   {len(quantity_changes)} 笔")
    lines.append("")

    # ---- 供应商-货类维度详细汇总 ----
    lines.append("【二、供应商-货类维度增减统计】")
    lines.append("-" * 50)

    if summary.empty:
        lines.append("  （无数据）")
    else:
        # 按总量变化排序
        display_cols = ['供应商', '货类', '原数据总量', '新数据总量', '总量变化',
                        '新增数量', '新增笔数', '减少数量', '减少笔数',
                        '调增数量', '调减数量']

        available_cols = [c for c in display_cols if c in summary.columns]
        report_df = summary[available_cols].copy()

        # 排序
        if '总量变化' in report_df.columns:
            report_df = report_df.sort_values('总量变化', ascending=False)

        # 格式化
        for col in report_df.columns:
            if col not in ['供应商', '货类']:
                report_df[col] = report_df[col].apply(_safe_int)

        # 打印表头
        header = f"  {'供应商':<12} {'货类':<8} {'原总量':>10} {'新总量':>10} {'变化':>10} {'新增量':>8} {'新增笔':>6} {'减少量':>8} {'减少笔':>6}"
        lines.append(header)
        lines.append("  " + "-" * (len(header) - 2))

        for _, row in report_df.iterrows():
            supplier = str(row.get('供应商', ''))[:12]
            cargo = str(row.get('货类', ''))[:8]
            old_qty = _safe_int(row.get('原数据总量', 0))
            new_qty = _safe_int(row.get('新数据总量', 0))
            change = _safe_int(row.get('总量变化', 0))
            add_qty = _safe_int(row.get('新增数量', 0))
            add_cnt = _safe_int(row.get('新增笔数', 0))
            rem_qty = _safe_int(row.get('减少数量', 0))
            rem_cnt = _safe_int(row.get('减少笔数', 0))

            change_str = f"+{_format_number(change)}" if change > 0 else _format_number(change)
            lines.append(
                f"  {supplier:<12} {cargo:<8} "
                f"{_format_number(old_qty):>10} {_format_number(new_qty):>10} "
                f"{change_str:>10} {_format_number(add_qty):>8} {add_cnt:>6} "
                f"{_format_number(rem_qty):>8} {rem_cnt:>6}"
            )

    lines.append("")

    # ---- 按供应商汇总统计 ----
    lines.append("【三、按供应商汇总统计】")
    lines.append("-" * 50)
    if summary.empty:
        lines.append("  （无数据）")
    else:
        # 按供应商分组汇总
        agg_cols = {
            '原数据总量': 'sum',
            '新数据总量': 'sum',
            '新增数量': 'sum',
            '新增笔数': 'sum',
            '减少数量': 'sum',
            '减少笔数': 'sum',
        }
        avail_agg = {k: v for k, v in agg_cols.items() if k in summary.columns}
        supplier_summary = summary.groupby('供应商')[list(avail_agg.keys())].sum().reset_index()
        supplier_summary['总量变化'] = supplier_summary['新数据总量'] - supplier_summary['原数据总量']
        supplier_summary = supplier_summary.sort_values('总量变化', ascending=False)

        header = f"  {'供应商':<12} {'原总量':>10} {'新总量':>10} {'变化':>10} {'新增量':>8} {'新增笔':>6} {'减少量':>8} {'减少笔':>6}"
        lines.append(header)
        lines.append("  " + "-" * (len(header) - 2))

        for _, row in supplier_summary.iterrows():
            supplier = str(row.get('供应商', ''))[:12]
            old_qty = _safe_int(row.get('原数据总量', 0))
            new_qty = _safe_int(row.get('新数据总量', 0))
            change = _safe_int(row.get('总量变化', 0))
            add_qty = _safe_int(row.get('新增数量', 0))
            add_cnt = _safe_int(row.get('新增笔数', 0))
            rem_qty = _safe_int(row.get('减少数量', 0))
            rem_cnt = _safe_int(row.get('减少笔数', 0))

            change_str = f"+{_format_number(change)}" if change > 0 else _format_number(change)
            lines.append(
                f"  {supplier:<12} "
                f"{_format_number(old_qty):>10} {_format_number(new_qty):>10} "
                f"{change_str:>10} {_format_number(add_qty):>8} {add_cnt:>6} "
                f"{_format_number(rem_qty):>8} {rem_cnt:>6}"
            )
    lines.append("")

    # ---- 按货类汇总统计 ----
    lines.append("【四、按货类汇总统计】")
    lines.append("-" * 50)
    if summary.empty:
        lines.append("  （无数据）")
    else:
        agg_cols = {
            '原数据总量': 'sum',
            '新数据总量': 'sum',
            '新增数量': 'sum',
            '新增笔数': 'sum',
            '减少数量': 'sum',
            '减少笔数': 'sum',
        }
        avail_agg = {k: v for k, v in agg_cols.items() if k in summary.columns}
        cargo_summary = summary.groupby('货类')[list(avail_agg.keys())].sum().reset_index()
        cargo_summary['总量变化'] = cargo_summary['新数据总量'] - cargo_summary['原数据总量']
        cargo_summary = cargo_summary.sort_values('总量变化', ascending=False)

        header = f"  {'货类':<10} {'原总量':>10} {'新总量':>10} {'变化':>10} {'新增量':>8} {'新增笔':>6} {'减少量':>8} {'减少笔':>6}"
        lines.append(header)
        lines.append("  " + "-" * (len(header) - 2))

        for _, row in cargo_summary.iterrows():
            cargo = str(row.get('货类', ''))[:10]
            old_qty = _safe_int(row.get('原数据总量', 0))
            new_qty = _safe_int(row.get('新数据总量', 0))
            change = _safe_int(row.get('总量变化', 0))
            add_qty = _safe_int(row.get('新增数量', 0))
            add_cnt = _safe_int(row.get('新增笔数', 0))
            rem_qty = _safe_int(row.get('减少数量', 0))
            rem_cnt = _safe_int(row.get('减少笔数', 0))

            change_str = f"+{_format_number(change)}" if change > 0 else _format_number(change)
            lines.append(
                f"  {cargo:<10} "
                f"{_format_number(old_qty):>10} {_format_number(new_qty):>10} "
                f"{change_str:>10} {_format_number(add_qty):>8} {add_cnt:>6} "
                f"{_format_number(rem_qty):>8} {rem_cnt:>6}"
            )
    lines.append("")

    # ---- 新增记录明细 ----
    lines.append("【五、新增记录明细】")
    lines.append("-" * 50)
    if additions.empty:
        lines.append("  （无新增记录）")
    else:
        detail_cols = ['货类', '供应商', '数量', '港口', '船名']
        avail = [c for c in detail_cols if c in additions.columns]
        for i, (_, row) in enumerate(additions[avail].iterrows(), 1):
            qty = _safe_int(row.get('数量', 0))
            lines.append(
                f"  {i:>3}. [{row.get('货类', '')}] "
                f"{row.get('供应商', '')} | "
                f"数量: {_format_number(qty)} 吨 | "
                f"港口: {row.get('港口', '')} | "
                f"船名: {row.get('船名', '')}"
            )
    lines.append("")

    # ---- 减少记录明细 ----
    lines.append("【六、减少记录明细】")
    lines.append("-" * 50)
    if removals.empty:
        lines.append("  （无减少记录）")
    else:
        detail_cols = ['货类', '供应商', '数量', '港口', '船名']
        avail = [c for c in detail_cols if c in removals.columns]
        for i, (_, row) in enumerate(removals[avail].iterrows(), 1):
            qty = _safe_int(row.get('数量', 0))
            lines.append(
                f"  {i:>3}. [{row.get('货类', '')}] "
                f"{row.get('供应商', '')} | "
                f"数量: {_format_number(qty)} 吨 | "
                f"港口: {row.get('港口', '')} | "
                f"船名: {row.get('船名', '')}"
            )
    lines.append("")

    # ---- 数量变更明细 ----
    if not quantity_changes.empty:
        lines.append("【七、数量变更明细】")
        lines.append("-" * 50)
        for i, (_, row) in enumerate(quantity_changes.iterrows(), 1):
            old_qty = _safe_int(row.get('原数量', 0))
            new_qty = _safe_int(row.get('新数量', 0))
            delta = _safe_int(row.get('变化量', 0))
            change_type = row.get('变化类型', '')
            lines.append(
                f"  {i:>3}. [{row.get('货类', '')}] "
                f"{row.get('供应商', '')} | "
                f"{row.get('船名', '')} | "
                f"{_format_number(old_qty)} → {_format_number(new_qty)} "
                f"({change_type} {_format_number(abs(delta))} 吨)"
            )
        lines.append("")

    lines.append("=" * 70)
    lines.append("报告生成时间: " + pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("=" * 70)

    report_text = "\n".join(lines)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f"报告已保存至: {output_path}")

    return report_text


def generate_excel_report(comparison_result: Dict, output_path: str):
    """
    生成Excel格式的完整分析报告，包含多个Sheet

    Args:
        comparison_result: compare_data() 返回的结果字典
        output_path: 输出Excel文件路径
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    summary = comparison_result['summary']
    additions = comparison_result['additions']
    removals = comparison_result['removals']
    quantity_changes = comparison_result['quantity_changes']

    # 生成按供应商汇总
    agg_cols = {
        '原数据总量': 'sum', '新数据总量': 'sum',
        '新增数量': 'sum', '新增笔数': 'sum',
        '减少数量': 'sum', '减少笔数': 'sum',
    }
    avail_agg = {k: v for k, v in agg_cols.items() if k in summary.columns}
    supplier_summary = summary.groupby('供应商')[list(avail_agg.keys())].sum().reset_index()
    supplier_summary['总量变化'] = supplier_summary['新数据总量'] - supplier_summary['原数据总量']
    supplier_summary = supplier_summary.sort_values('总量变化', ascending=False)

    # 按货类汇总
    cargo_summary = summary.groupby('货类')[list(avail_agg.keys())].sum().reset_index()
    cargo_summary['总量变化'] = cargo_summary['新数据总量'] - cargo_summary['原数据总量']
    cargo_summary = cargo_summary.sort_values('总量变化', ascending=False)

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # Sheet1: 按供应商汇总
        supplier_summary.to_excel(writer, sheet_name='按供应商汇总', index=False)

        # Sheet2: 按货类汇总
        cargo_summary.to_excel(writer, sheet_name='按货类汇总', index=False)

        # Sheet3: 供应商-货类明细
        summary.to_excel(writer, sheet_name='供应商-货类明细', index=False)

        # Sheet4: 新增记录
        if not additions.empty:
            additions.to_excel(writer, sheet_name='新增记录明细', index=False)

        # Sheet5: 减少记录
        if not removals.empty:
            removals.to_excel(writer, sheet_name='减少记录明细', index=False)

        # Sheet6: 数量变更
        if not quantity_changes.empty:
            quantity_changes.to_excel(writer, sheet_name='数量变更明细', index=False)

    print(f"Excel报告已保存至: {output_path}")


def print_summary(comparison_result: Dict):
    """打印简要摘要到控制台"""
    summary = comparison_result['summary']

    total_add = _safe_int(summary['新增数量'].sum()) if '新增数量' in summary.columns else 0
    total_rem = _safe_int(summary['减少数量'].sum()) if '减少数量' in summary.columns else 0
    total_add_cnt = _safe_int(summary['新增笔数'].sum()) if '新增笔数' in summary.columns else 0
    total_rem_cnt = _safe_int(summary['减少笔数'].sum()) if '减少笔数' in summary.columns else 0
    total_net = _safe_int(summary['总量变化'].sum()) if '总量变化' in summary.columns else 0

    affected_suppliers = summary['供应商'].nunique() if '供应商' in summary.columns else 0
    affected_cargos = summary['货类'].nunique() if '货类' in summary.columns else 0

    print(f"\n{'='*50}")
    print(f"对比结果摘要:")
    print(f"  - 涉及供应商: {affected_suppliers} 家")
    print(f"  - 涉及货类: {affected_cargos} 种")
    print(f"  - 新增: {total_add_cnt} 笔, {_format_number(total_add)} 吨")
    print(f"  - 减少: {total_rem_cnt} 笔, {_format_number(total_rem)} 吨")
    print(f"  - 净变化: {_format_number(total_net)} 吨")
    print(f"{'='*50}")