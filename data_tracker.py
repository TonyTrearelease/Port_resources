"""
数据追踪对比模块 - 自动识别不同日期的数据文件，计算每个供应商在每个货类下的新增和减少数据量
"""

import re
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime


def _sort_by_date(files: List[Path]) -> List[Path]:
    """按文件名中的日期对文件进行排序"""
    def extract_date_key(f: Path):
        match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', f.name)
        if match:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return datetime.min
    return sorted(files, key=extract_date_key)


def _standardize_df(df: pd.DataFrame) -> pd.DataFrame:
    """标准化DataFrame，确保包含必要的列"""
    required_cols = ['货类', '供应商', '数量', '港口', '船名']
    for col in required_cols:
        if col not in df.columns:
            df[col] = ''
    return df


def _create_record_key(df: pd.DataFrame) -> pd.DataFrame:
    """
    为每条记录创建唯一标识键（用于逐条对比）
    使用业务字段（不含数量）组合作为键，识别同一条货源
    
    键的构成：货类|供应商|港口|船名|指标|备注
    - 不包含数量：同一货源数量变化时，仍能匹配并识别为变更
    - 包含船名等字段区分不同批次
    """
    base = (
        df['货类'].astype(str) + '|' +
        df['供应商'].astype(str) + '|' +
        df['港口'].astype(str) + '|' +
        df['船名'].astype(str)
    )
    if '指标' in df.columns:
        base = base + '|' + df['指标'].fillna('').astype(str)
    if '备注' in df.columns:
        base = base + '|' + df['备注'].fillna('').astype(str)
    # 对完全相同的key加上序号后缀（处理同供应商同船名多条记录情况）
    counts = base.groupby(base).cumcount()
    df['_key'] = base + '|#' + counts.astype(str)
    return df


def compare_data(old_df: pd.DataFrame, new_df: pd.DataFrame) -> Dict:
    """
    对比两个日期的数据，计算新增和减少

    Args:
        old_df: 旧日期清洗后的数据
        new_df: 新日期清洗后的数据

    Returns:
        dict: {
            'additions': DataFrame - 新增记录明细,
            'removals': DataFrame - 减少记录明细,
            'summary': DataFrame - 供应商-货类维度汇总
        }
    """
    old_df = _standardize_df(old_df.copy())
    new_df = _standardize_df(new_df.copy())

    # 创建唯一键
    old_df = _create_record_key(old_df)
    new_df = _create_record_key(new_df)

    old_keys = set(old_df['_key'])
    new_keys = set(new_df['_key'])

    # 新增记录：在新数据中存在，在旧数据中不存在
    added_keys = new_keys - old_keys
    additions = new_df[new_df['_key'].isin(added_keys)].copy()

    # 减少记录：在旧数据中存在，在新数据中不存在
    removed_keys = old_keys - new_keys
    removals = old_df[old_df['_key'].isin(removed_keys)].copy()

    # 共同记录：检查数量变化
    common_keys = old_keys & new_keys
    old_common = old_df[old_df['_key'].isin(common_keys)].set_index('_key')
    new_common = new_df[new_df['_key'].isin(common_keys)].set_index('_key')

    # 数量变更
    quantity_changes = []
    for key in common_keys:
        old_rows = old_common.loc[[key]] if key in old_common.index else pd.DataFrame()
        new_rows = new_common.loc[[key]] if key in new_common.index else pd.DataFrame()

        # 处理可能的多行情况
        if old_rows.empty or new_rows.empty:
            continue

        # 取第一行（正常情况下每个key唯一）
        old_row = old_rows.iloc[0] if len(old_rows) == 1 else old_rows.iloc[0]
        new_row = new_rows.iloc[0] if len(new_rows) == 1 else new_rows.iloc[0]

        old_qty = int(old_row['数量']) if pd.notna(old_row['数量']) else 0
        new_qty = int(new_row['数量']) if pd.notna(new_row['数量']) else 0
        if old_qty != new_qty:
            quantity_changes.append({
                '货类': str(old_row.get('货类', '')),
                '供应商': str(old_row.get('供应商', '')),
                '港口': str(old_row.get('港口', '')),
                '船名': str(old_row.get('船名', '')),
                '原数量': old_qty,
                '新数量': new_qty,
                '变化量': new_qty - old_qty,
                '变化类型': '增加' if new_qty > old_qty else '减少'
            })

    changes_df = pd.DataFrame(quantity_changes) if quantity_changes else pd.DataFrame()

    # 生成供应商-货类维度汇总
    summary = _generate_summary(
        additions=additions,
        removals=removals,
        changes_df=changes_df,
        old_df=old_df,
        new_df=new_df
    )

    # 清理临时列
    for df in [additions, removals]:
        if '_key' in df.columns:
            df.drop(columns=['_key'], inplace=True)

    return {
        'additions': additions,
        'removals': removals,
        'quantity_changes': changes_df,
        'summary': summary
    }


def _generate_summary(
    additions: pd.DataFrame,
    removals: pd.DataFrame,
    changes_df: pd.DataFrame,
    old_df: pd.DataFrame,
    new_df: pd.DataFrame
) -> pd.DataFrame:
    """
    生成供应商-货类维度的增减汇总统计
    """
    # 新增汇总：按供应商+货类分组
    add_summary = pd.DataFrame()
    if not additions.empty:
        add_summary = additions.groupby(['供应商', '货类']).agg(
            新增笔数=('数量', 'count'),
            新增数量=('数量', 'sum')
        ).reset_index()

    # 减少汇总
    rem_summary = pd.DataFrame()
    if not removals.empty:
        rem_summary = removals.groupby(['供应商', '货类']).agg(
            减少笔数=('数量', 'count'),
            减少数量=('数量', 'sum')
        ).reset_index()

    # 数量变更汇总
    chg_summary = pd.DataFrame()
    if not changes_df.empty:
        chg_summary = changes_df.groupby(['供应商', '货类']).agg(
            数量变更笔数=('变化量', 'count'),
            净变化量=('变化量', 'sum')
        ).reset_index()
        # 拆分增加和减少
        inc = changes_df[changes_df['变化量'] > 0].groupby(['供应商', '货类']).agg(
            调增笔数=('变化量', 'count'),
            调增数量=('变化量', 'sum')
        ).reset_index()
        dec = changes_df[changes_df['变化量'] < 0].groupby(['供应商', '货类']).agg(
            调减笔数=('变化量', 'count'),
            调减数量=('变化量', 'sum')
        ).reset_index()
        # 调减数量取绝对值
        if not dec.empty:
            dec['调减数量'] = dec['调减数量'].abs()

    # 旧数据总量
    old_summary = old_df.groupby(['供应商', '货类']).agg(
        原数据笔数=('数量', 'count'),
        原数据总量=('数量', 'sum')
    ).reset_index()

    # 新数据总量
    new_summary = new_df.groupby(['供应商', '货类']).agg(
        新数据笔数=('数量', 'count'),
        新数据总量=('数量', 'sum')
    ).reset_index()

    # 合并所有汇总
    result = old_summary.merge(new_summary, on=['供应商', '货类'], how='outer')

    if not add_summary.empty:
        result = result.merge(add_summary, on=['供应商', '货类'], how='left')
    if not rem_summary.empty:
        result = result.merge(rem_summary, on=['供应商', '货类'], how='left')
    if not chg_summary.empty:
        result = result.merge(chg_summary, on=['供应商', '货类'], how='left')

    # 填充空值
    fill_cols = ['新增笔数', '新增数量', '减少笔数', '减少数量',
                 '数量变更笔数', '净变化量', '调增笔数', '调增数量', '调减笔数', '调减数量']
    for col in fill_cols:
        if col in result.columns:
            result[col] = result[col].fillna(0).astype(int)

    # 计算净变化
    if '新数据总量' in result.columns and '原数据总量' in result.columns:
        result['总量变化'] = result['新数据总量'].fillna(0).astype(int) - result['原数据总量'].fillna(0).astype(int)

    return result


def find_data_files(directory: str) -> List[Path]:
    """查找目录中的所有Excel数据文件（排除clean_前缀的文件）"""
    dir_path = Path(directory)
    all_files = list(dir_path.glob("*.xlsx"))
    # 排除已清洗的文件
    data_files = [f for f in all_files if not f.name.startswith("clean_")]
    return _sort_by_date(data_files)


def auto_track(clean_dir: str = "clean_data") -> Optional[Dict]:
    """
    自动识别clean_data目录中的所有清洗后数据文件，按日期排序后两两对比

    Args:
        clean_dir: 清洗数据存放目录

    Returns:
        Dict: 对比结果，包含每次对比的明细
    """
    clean_path = Path(clean_dir)
    if not clean_path.exists():
        print(f"清洗数据目录不存在: {clean_dir}")
        return None

    clean_files = _sort_by_date(list(clean_path.glob("clean_*.xlsx")))
    if not clean_files:
        print(f"在 {clean_dir} 中未找到清洗后的数据文件")
        return None

    print(f"\n{'='*60}")
    print(f"开始数据追踪对比")
    print(f"找到 {len(clean_files)} 个清洗数据文件:")
    for f in clean_files:
        print(f"  - {f.name}")

    if len(clean_files) < 2:
        print("至少需要2个文件才能进行对比，当前仅1个文件")
        return None

    results = {}
    # 从文件日期最新的开始依次与上一期对比
    for i in range(len(clean_files) - 1):
        older = clean_files[i]
        newer = clean_files[i + 1]

        print(f"\n{'─'*50}")
        print(f"对比: {older.name}  →  {newer.name}")

        old_df = pd.read_excel(older, engine='openpyxl')
        new_df = pd.read_excel(newer, engine='openpyxl')

        result = compare_data(old_df, new_df)
        results[f"{older.stem}→{newer.stem}"] = result

        # 打印摘要
        summary = result['summary']
        total_add = summary['新增数量'].sum() if '新增数量' in summary.columns else 0
        total_rem = summary['减少数量'].sum() if '减少数量' in summary.columns else 0
        total_net = summary['总量变化'].sum() if '总量变化' in summary.columns else 0

        print(f"  新增记录: {len(result['additions'])} 条, 新增数量: {total_add}")
        print(f"  减少记录: {len(result['removals'])} 条, 减少数量: {total_rem}")
        print(f"  数量变更: {len(result['quantity_changes'])} 条")
        print(f"  净变化量: {total_add - total_rem} (新增-减少)")

    return results


def multi_period_analysis(clean_dir: str = "clean_data", top_n: int = 15) -> Optional[Dict]:
    """
    多期数据对比分析 - 读取所有清洗文件，构建时间序列数据

    对每个供应商-货类维度，计算其在每个日期的总量，
    以及环比变化量/变化率，用于生成可视化报告。

    Args:
        clean_dir: 清洗数据目录
        top_n: 图表中显示的Top N数量

    Returns:
        Dict: {
            'dates': ['5.29', '6.5', ...],          # 各期日期标签
            'date_labels_full': ['2026.5.29', ...],  # 完整日期
            'totals': [11408000, 11392400, ...],     # 每期总库存
            'supplier_data': [                      # 按供应商汇总
                {'name': '供应商A', 'values': [v1,v2,...], 'total': sum},
                ...
            ],
            'cargo_data': [                         # 按货类汇总
                {'name': '货类A', 'values': [v1,v2,...], 'total': sum},
                ...
            ],
            'detail': [                              # 供应商-货类明细
                {
                    'supplier': '...',
                    'cargo': '...',
                    'values': [v1, v2, ...],
                    'changes': [None, c1, c2, ...],
                    'pct_changes': [None, p1, p2, ...],
                    'latest': v_last,
                },
                ...
            ],
        }
    """
    from data_cleaner import _extract_date_from_filename

    clean_path = Path(clean_dir)
    if not clean_path.exists():
        print(f"清洗数据目录不存在: {clean_dir}")
        return None

    clean_files = _sort_by_date(list(clean_path.glob("clean_*.xlsx")))
    if len(clean_files) < 1:
        print(f"在 {clean_dir} 中未找到清洗数据文件")
        return None

    print(f"\n{'='*60}")
    print(f"多期数据分析 - 共 {len(clean_files)} 期数据")
    for f in clean_files:
        print(f"  - {f.name}")

    # 读取所有数据
    all_data = []
    date_labels = []
    date_labels_full = []

    for f in clean_files:
        df = pd.read_excel(f, engine='openpyxl')
        df = _standardize_df(df)
        all_data.append(df)

        date_str = _extract_date_from_filename(f.name) or f.stem
        # 简写标签: '5.29'
        parts = date_str.split('.')
        short_label = f"{int(parts[1])}.{int(parts[2])}" if len(parts) >= 3 else date_str
        date_labels.append(short_label)
        date_labels_full.append(date_str)

    num_periods = len(all_data)

    # 1. 每期总库存
    totals = [int(df['数量'].sum()) for df in all_data]

    # 2. 按供应商汇总（每家供应商每期的总量）
    supplier_series = {}
    for i, df in enumerate(all_data):
        grp = df.groupby('供应商')['数量'].sum()
        for supplier, qty in grp.items():
            if supplier not in supplier_series:
                supplier_series[supplier] = [0] * num_periods
            supplier_series[supplier][i] = int(qty)
        # 未出现的供应商补0
        for supplier in supplier_series:
            if len(supplier_series[supplier]) <= i:
                supplier_series[supplier].append(0)

    supplier_data = sorted(
        [{'name': k, 'values': v, 'total': sum(v)} for k, v in supplier_series.items()],
        key=lambda x: x['total'], reverse=True
    )
    # 只保留top_n
    supplier_data_top = supplier_data[:top_n]
    # 补充"其他"汇总
    if len(supplier_data) > top_n:
        other_values = [0] * num_periods
        for s in supplier_data[top_n:]:
            for i, v in enumerate(s['values']):
                other_values[i] += v
        supplier_data_top.append({'name': '其他', 'values': other_values, 'total': sum(other_values)})

    # 3. 按货类汇总
    cargo_series = {}
    for i, df in enumerate(all_data):
        grp = df.groupby('货类')['数量'].sum()
        for cargo, qty in grp.items():
            if cargo not in cargo_series:
                cargo_series[cargo] = [0] * num_periods
            cargo_series[cargo][i] = int(qty)
        for cargo in cargo_series:
            if len(cargo_series[cargo]) <= i:
                cargo_series[cargo].append(0)

    cargo_data = sorted(
        [{'name': k, 'values': v, 'total': sum(v)} for k, v in cargo_series.items()],
        key=lambda x: x['total'], reverse=True
    )
    cargo_data_top = cargo_data[:top_n]
    if len(cargo_data) > top_n:
        other_values = [0] * num_periods
        for c in cargo_data[top_n:]:
            for i, v in enumerate(c['values']):
                other_values[i] += v
        cargo_data_top.append({'name': '其他', 'values': other_values, 'total': sum(other_values)})

    # 4. 供应商-货类维度明细
    detail_map = {}
    for i, df in enumerate(all_data):
        grp = df.groupby(['供应商', '货类'])['数量'].sum()
        for (supplier, cargo), qty in grp.items():
            key = (supplier, cargo)
            if key not in detail_map:
                detail_map[key] = [0] * num_periods
            detail_map[key][i] = int(qty)
        for key in detail_map:
            if len(detail_map[key]) <= i:
                detail_map[key].append(0)

    # 按最新一期总量排序，取非零的
    detail = []
    for (supplier, cargo), values in detail_map.items():
        if sum(values) == 0:
            continue
        changes = [None] * num_periods
        pct_changes = [None] * num_periods
        for j in range(1, num_periods):
            if values[j - 1] != 0:
                changes[j] = values[j] - values[j - 1]
                pct_changes[j] = round((values[j] - values[j - 1]) / values[j - 1] * 100, 1)
            else:
                changes[j] = values[j] - values[j - 1]
                pct_changes[j] = 100.0 if values[j] > 0 else 0.0

        detail.append({
            'supplier': supplier,
            'cargo': cargo,
            'values': values,
            'changes': changes,
            'pct_changes': pct_changes,
            'latest': values[-1],
            'total': sum(values),
        })

    detail.sort(key=lambda x: x['total'], reverse=True)

    # ─── 5. 计算每期的新增和减少量（按供应商、按货类） ───
    # 对每组相邻文件进行逐条对比，提取新增记录和减少记录
    num_transitions = num_periods - 1

    # 按供应商：每期新增量、每期减少量
    supplier_add = {}   # supplier -> [add_qty_per_transition]
    supplier_rem = {}   # supplier -> [rem_qty_per_transition]
    # 按货类：每期新增量、每期减少量
    cargo_add = {}
    cargo_rem = {}

    for t in range(num_transitions):
        old_df = all_data[t]
        new_df = all_data[t + 1]

        # 使用已有的逐条对比逻辑
        result = compare_data(old_df, new_df)

        # 按供应商汇总新增
        adds = result['additions']
        if not adds.empty:
            grp = adds.groupby('供应商')['数量'].sum()
            for name, qty in grp.items():
                if name not in supplier_add:
                    supplier_add[name] = [0] * num_transitions
                supplier_add[name][t] = int(qty)
        # 补充未出现供应商标记0
        for name in supplier_add:
            if len(supplier_add[name]) <= t:
                supplier_add[name].append(0)

        # 按供应商汇总减少
        rems = result['removals']
        if not rems.empty:
            grp = rems.groupby('供应商')['数量'].sum()
            for name, qty in grp.items():
                if name not in supplier_rem:
                    supplier_rem[name] = [0] * num_transitions
                supplier_rem[name][t] = int(qty)
        for name in supplier_rem:
            if len(supplier_rem[name]) <= t:
                supplier_rem[name].append(0)

        # 按货类汇总新增
        if not adds.empty:
            grp = adds.groupby('货类')['数量'].sum()
            for name, qty in grp.items():
                if name not in cargo_add:
                    cargo_add[name] = [0] * num_transitions
                cargo_add[name][t] = int(qty)
        for name in cargo_add:
            if len(cargo_add[name]) <= t:
                cargo_add[name].append(0)

        # 按货类汇总减少
        if not rems.empty:
            grp = rems.groupby('货类')['数量'].sum()
            for name, qty in grp.items():
                if name not in cargo_rem:
                    cargo_rem[name] = [0] * num_transitions
                cargo_rem[name][t] = int(qty)
        for name in cargo_rem:
            if len(cargo_rem[name]) <= t:
                cargo_rem[name].append(0)

    # 合并供应商 add/rem 数据（与已有 supplier_data_top 对应）
    supplier_add_rem = []
    for s in supplier_data_top:
        name = s['name']
        add_vals = supplier_add.get(name, [0] * num_transitions)
        rem_vals = supplier_rem.get(name, [0] * num_transitions)
        net_vals = [add_vals[i] - rem_vals[i] for i in range(num_transitions)]
        supplier_add_rem.append({
            'name': name,
            'add_values': add_vals,
            'rem_values': rem_vals,
            'net_values': net_vals,
        })

    # 合并货类 add/rem 数据（与已有 cargo_data_top 对应）
    cargo_add_rem = []
    for c in cargo_data_top:
        name = c['name']
        add_vals = cargo_add.get(name, [0] * num_transitions)
        rem_vals = cargo_rem.get(name, [0] * num_transitions)
        net_vals = [add_vals[i] - rem_vals[i] for i in range(num_transitions)]
        cargo_add_rem.append({
            'name': name,
            'add_values': add_vals,
            'rem_values': rem_vals,
            'net_values': net_vals,
        })

    return {
        'dates': date_labels,
        'date_labels_full': date_labels_full,
        'totals': totals,
        'supplier_data': supplier_data_top,
        'cargo_data': cargo_data_top,
        'detail': detail,
        'supplier_add_rem': supplier_add_rem,
        'cargo_add_rem': cargo_add_rem,
    }


def track_with_baseline(new_clean_file: str, baseline_clean_file: str) -> Optional[Dict]:
    """
    将新数据与指定的基准数据进行对比

    Args:
        new_clean_file: 新日期的清洗数据文件路径
        baseline_clean_file: 基准（旧）清洗数据文件路径

    Returns:
        Dict: 对比结果
    """
    print(f"\n{'='*60}")
    print(f"基准对比: {baseline_clean_file}  →  {new_clean_file}")

    old_df = pd.read_excel(baseline_clean_file, engine='openpyxl')
    new_df = pd.read_excel(new_clean_file, engine='openpyxl')

    result = compare_data(old_df, new_df)

    summary = result['summary']
    total_add = summary['新增数量'].sum() if '新增数量' in summary.columns else 0
    total_rem = summary['减少数量'].sum() if '减少数量' in summary.columns else 0

    print(f"  新增记录: {len(result['additions'])} 条, 新增数量: {total_add}")
    print(f"  减少记录: {len(result['removals'])} 条, 减少数量: {total_rem}")
    print(f"  数量变更: {len(result['quantity_changes'])} 条")

    return result