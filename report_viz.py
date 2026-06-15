"""
可视化报告模块 - 生成包含数据表格和趋势图表的HTML报告
"""

import json
from pathlib import Path
from typing import Dict, Optional


def _format_number(val) -> str:
    """格式化数字，添加千位分隔符"""
    if val is None:
        return "-"
    return f"{int(val):,}"


def _fmt_change(val) -> str:
    """格式化变化量，带正负号"""
    if val is None:
        return "-"
    if val > 0:
        return f"+{int(val):,}"
    elif val < 0:
        return f"{int(val):,}"
    return "0"


def _fmt_pct(val) -> str:
    """格式化百分比变化"""
    if val is None:
        return "-"
    if val > 0:
        return f"+{val}%"
    elif val < 0:
        return f"{val}%"
    return "0%"


def _change_color(val) -> str:
    """根据变化值返回颜色样式"""
    if val is None:
        return ""
    if val > 0:
        return 'style="color:#e74c3c;"'
    elif val < 0:
        return 'style="color:#27ae60;"'
    return 'style="color:#7f8c8d;"'


def _pct_color(val) -> str:
    """根据百分比返回颜色样式"""
    if val is None:
        return ""
    if val > 0:
        return 'style="color:#e74c3c; font-weight:bold;"'
    elif val < 0:
        return 'style="color:#27ae60; font-weight:bold;"'
    return 'style="color:#7f8c8d;"'


def generate_html_report(analysis_data: Dict, output_path: str, periods_to_show: int = 5):
    """
    生成HTML可视化报告

    Args:
        analysis_data: multi_period_analysis() 返回的数据
        output_path: 输出HTML文件路径
        periods_to_show: 表格中显示的期数（默认5期）
    """
    import datetime as _dt
    dates = analysis_data['dates']
    totals = analysis_data['totals']
    supplier_data = analysis_data['supplier_data']
    cargo_data = analysis_data['cargo_data']
    detail = analysis_data['detail']
    supplier_add_rem = analysis_data.get('supplier_add_rem', [])
    cargo_add_rem = analysis_data.get('cargo_add_rem', [])

    num_periods = len(dates)
    num_transitions = num_periods - 1
    show_periods = min(periods_to_show, num_periods)

    if num_periods > show_periods:
        detail_dates = dates[-show_periods:]
    else:
        detail_dates = dates

    # JSON 序列化
    supplier_names_json = json.dumps([s['name'] for s in supplier_data])
    supplier_values_json = json.dumps([s['values'] for s in supplier_data])
    cargo_names_json = json.dumps([c['name'] for c in cargo_data])
    cargo_values_json = json.dumps([c['values'] for c in cargo_data])
    detail_json = json.dumps(detail)

    # 新增/减少数据
    supplier_add_rem_json = json.dumps(supplier_add_rem)
    cargo_add_rem_json = json.dumps(cargo_add_rem)

    # 对比期标签（用于新增/减少图表：5.29→6.5）
    trans_labels = json.dumps([f"{dates[i]}→{dates[i+1]}" for i in range(num_transitions)])

    # 总库存变化率
    total_changes = []
    for j in range(1, num_periods):
        if totals[j - 1] != 0:
            pct = round((totals[j] - totals[j - 1]) / totals[j - 1] * 100, 2)
        else:
            pct = 0
        total_changes.append(pct)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>港口可贸易资源 - 历史数据趋势分析报告</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
            background: #f0f2f5;
            color: #333;
            padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{
            background: linear-gradient(135deg, #1a5276, #2e86c1); color: #fff;
            padding: 30px 40px; border-radius: 12px; margin-bottom: 24px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.15);
        }}
        .header h1 {{ font-size: 26px; margin-bottom: 8px; }}
        .header p {{ font-size: 14px; opacity: 0.85; }}
        .header .date-range {{ margin-top: 12px; font-size: 15px; }}
        .header .date-range span {{ background: rgba(255,255,255,0.2); padding: 4px 14px; border-radius: 20px; margin-right: 8px; display: inline-block; }}

        .summary-cards {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px; margin-bottom: 24px;
        }}
        .summary-card {{
            background: #fff; border-radius: 10px; padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center;
        }}
        .summary-card .label {{ font-size: 13px; color: #888; margin-bottom: 6px; }}
        .summary-card .value {{ font-size: 24px; font-weight: bold; color: #1a5276; }}
        .summary-card .sub {{ font-size: 13px; color: #888; margin-top: 4px; }}
        .summary-card .up {{ color: #e74c3c; }} .summary-card .down {{ color: #27ae60; }}

        .section {{
            background: #fff; border-radius: 10px; padding: 24px;
            margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .section h2 {{
            font-size: 18px; color: #1a5276; margin-bottom: 16px;
            padding-bottom: 10px; border-bottom: 2px solid #eef2f7;
        }}
        .section h2 .badge {{
            font-size: 12px; background: #2e86c1; color: #fff;
            padding: 2px 10px; border-radius: 12px; margin-left: 8px;
            vertical-align: middle; font-weight: 400;
        }}
        .chart-container {{ position: relative; width: 100%; max-height: 420px; }}

        .table-wrap {{ overflow-x: auto; margin-top: 12px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; white-space: nowrap; }}
        thead th {{
            background: #1a5276; color: #fff; padding: 10px 12px;
            text-align: center; font-weight: 500; position: sticky; top: 0;
        }}
        thead th:first-child {{ border-radius: 6px 0 0 0; }}
        thead th:last-child {{ border-radius: 0 6px 0 0; }}
        tbody td {{ padding: 8px 12px; text-align: center; border-bottom: 1px solid #eef2f7; }}
        tbody tr:hover {{ background: #f7f9fc; }}
        .supplier-col {{ text-align: left; font-weight: 500; min-width: 90px; }}
        .cargo-col {{ text-align: left; min-width: 70px; }}
        .num-col {{ min-width: 90px; text-align: right; font-variant-numeric: tabular-nums; }}
        .num-add {{ color: #e74c3c; }} .num-rem {{ color: #27ae60; }}
        .change-col {{ min-width: 80px; text-align: right; }}
        .pct-col {{ min-width: 60px; text-align: right; }}

        .legend-bar {{
            display: inline-block; width: 10px; height: 10px;
            border-radius: 2px; margin-right: 4px;
        }}
        .legend-wrap {{
            display: flex; flex-wrap: wrap; gap: 6px 14px;
            margin-top: 8px; font-size: 12px; color: #555;
        }}

        .rank-badge {{
            display: inline-block; width: 22px; height: 22px; line-height: 22px;
            text-align: center; border-radius: 50%; font-size: 11px; font-weight: bold; color: #fff;
        }}
        .rank-1 {{ background: #e74c3c; }} .rank-2 {{ background: #e67e22; }} .rank-3 {{ background: #f39c12; }}

        .filter-bar {{
            display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap;
        }}
        .filter-bar input {{
            padding: 8px 14px; border: 1px solid #dce1e8; border-radius: 6px;
            font-size: 13px; flex: 1; min-width: 200px; outline: none;
        }}
        .filter-bar input:focus {{ border-color: #2e86c1; box-shadow: 0 0 0 2px rgba(46,134,193,0.15); }}
        .filter-bar select {{
            padding: 8px 14px; border: 1px solid #dce1e8; border-radius: 6px;
            font-size: 13px; outline: none; background: #fff;
        }}
        .stat-row {{
            display: flex; gap: 20px; margin-bottom: 16px; flex-wrap: wrap;
            font-size: 13px; color: #555;
        }}
        .stat-row strong {{ color: #333; }}

        .add-badge {{ display:inline-block; font-size:11px; padding:0 6px; border-radius:3px; }}
        .add-badge.add {{ background:#fde8e8; color:#e74c3c; }}
        .add-badge.rem {{ background:#e8f8f0; color:#27ae60; }}

        .period-btn {{ display:inline-block; padding:4px 14px; margin:0 4px; font-size:13px; border:1px solid #ddd; border-radius:4px; background:#fff; cursor:pointer; color:#555; }}
        .period-btn.active {{ background:#3498db; color:#fff; border-color:#3498db; }}
        .period-btn:hover {{ background:#f0f0f0; }}
        .period-btn.active:hover {{ background:#2980b9; }}

        .footer {{ text-align: center; padding: 20px; color: #999; font-size: 12px; }}

        @media (max-width: 768px) {{
            .header {{ padding: 20px; }}
            .header h1 {{ font-size: 20px; }}
            .summary-cards {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
</head>
<body>
<div class="container">

    <div class="header">
        <h1>港口可贸易资源 · 历史数据趋势分析</h1>
        <p>多期数据对比 · 新增/减少量追踪 · 供应商/货类维度</p>
        <div class="date-range">
            <span>{dates[0]}</span> → <span>{dates[-1]}</span>
            &nbsp;&nbsp;共 {num_periods} 期数据
        </div>
    </div>

    <!-- 概览卡片 -->
    <div class="summary-cards">
        <div class="summary-card">
            <div class="label">最新总库存</div>
            <div class="value">{_format_number(totals[-1])}</div>
            <div class="sub">吨</div>
        </div>
        <div class="summary-card">
            <div class="label">期初总库存</div>
            <div class="value">{_format_number(totals[0])}</div>
            <div class="sub">{dates[0]}</div>
        </div>
        <div class="summary-card">
            <div class="label">总库存变化</div>
            <div class="value {'up' if totals[-1] > totals[0] else 'down'}">{_fmt_change(totals[-1] - totals[0])}</div>
            <div class="sub">{_fmt_pct(total_changes[-1]) if total_changes else '-'}（环比）</div>
        </div>
        <div class="summary-card">
            <div class="label">涉及供应商</div>
            <div class="value">{len(supplier_data)}</div>
            <div class="sub">家</div>
        </div>
        <div class="summary-card">
            <div class="label">涉及货类</div>
            <div class="value">{len(cargo_data)}</div>
            <div class="sub">种</div>
        </div>
    </div>

    <!-- 1. 总库存趋势 -->
    <div class="section">
        <h2>一、总库存变化趋势</h2>
        <div class="stat-row">
            <span><strong>各期数据：</strong>
            {''.join(f'{dates[i]}: {_format_number(totals[i])} 吨' + (' → ' if i < num_periods - 1 else '') for i in range(num_periods))}
            </span>
        </div>
        <div class="chart-container"><canvas id="totalTrendChart"></canvas></div>
    </div>

    <!-- 2. 供应商库存趋势 -->
    <div class="section">
        <h2>二、主要供应商库存趋势 <span class="badge">点击图例切换显示</span></h2>
        <div class="chart-container"><canvas id="supplierChart"></canvas></div>
    </div>

    <!-- 3. 货类库存趋势 -->
    <div class="section">
        <h2>三、主要货类库存趋势 <span class="badge">点击图例切换显示</span></h2>
        <div class="chart-container"><canvas id="cargoChart"></canvas></div>
    </div>

    <!-- 4. 供应商每期新增 vs 减少 -->
    <div class="section">
        <h2>四、供应商每期新增 vs 减少 <span class="badge">逐期对比</span></h2>
        <div class="stat-row" style="margin-bottom:8px;">
            <span style="display:inline-flex;align-items:center;gap:8px;">
                <span class="add-badge add">■ 新增</span>
                <span class="add-badge rem">■ 减少</span>
            </span>
        </div>
        <div class="chart-container" style="max-height:380px;">
            <div style="text-align:center;margin-bottom:8px;">
                {''.join(f'<button class="period-btn{" active" if i == num_transitions - 1 else ""}" onclick="switchAddRemPeriod({i})">{dates[i]}→{dates[i+1]}</button>' for i in range(num_transitions))}
            </div>
            <canvas id="supplierAddRemChart"></canvas>
        </div>
        <div class="table-wrap" style="margin-top:16px;">
            <table>
                <thead>
                    <tr>
                        <th>供应商</th>
                        {''.join(f'<th colspan="2">{dates[i]}→{dates[i+1]}</th>' for i in range(num_transitions))}
                        <th>净变化</th>
                    </tr>
                    <tr>
                        <th></th>
                        {''.join(f'<th style="font-weight:400;font-size:12px;color:#e74c3c;">新增</th><th style="font-weight:400;font-size:12px;color:#27ae60;">减少</th>' for _ in range(num_transitions))}
                        <th style="font-weight:400;font-size:12px;"></th>
                    </tr>
                </thead>
                <tbody id="supplierAddRemBody"></tbody>
            </table>
        </div>
    </div>

    <!-- 5. 货类每期新增 vs 减少 -->
    <div class="section">
        <h2>五、货类每期新增 vs 减少 <span class="badge">逐期对比</span></h2>
        <div class="stat-row" style="margin-bottom:8px;">
            <span style="display:inline-flex;align-items:center;gap:8px;">
                <span class="add-badge add">■ 新增</span>
                <span class="add-badge rem">■ 减少</span>
            </span>
        </div>
        <div class="chart-container" style="max-height:380px;">
            <div style="text-align:center;margin-bottom:8px;">
                {''.join(f'<button class="period-btn{" active" if i == num_transitions - 1 else ""}" onclick="switchAddRemPeriod({i})">{dates[i]}→{dates[i+1]}</button>' for i in range(num_transitions))}
            </div>
            <canvas id="cargoAddRemChart"></canvas>
        </div>
        <div class="table-wrap" style="margin-top:16px;">
            <table>
                <thead>
                    <tr>
                        <th>货类</th>
                        {''.join(f'<th colspan="2">{dates[i]}→{dates[i+1]}</th>' for i in range(num_transitions))}
                        <th>净变化</th>
                    </tr>
                    <tr>
                        <th></th>
                        {''.join(f'<th style="font-weight:400;font-size:12px;color:#e74c3c;">新增</th><th style="font-weight:400;font-size:12px;color:#27ae60;">减少</th>' for _ in range(num_transitions))}
                        <th style="font-weight:400;font-size:12px;"></th>
                    </tr>
                </thead>
                <tbody id="cargoAddRemBody"></tbody>
            </table>
        </div>
    </div>

    <!-- 6. 供应商-货类明细表 -->
    <div class="section">
        <h2>六、供应商-货类明细（多期对比 + 环比变化）</h2>
        <div class="filter-bar">
            <input type="text" id="searchInput" placeholder="搜索供应商或货类..." oninput="filterTable()">
            <select id="sortSelect" onchange="sortTable()">
                <option value="total">按总量排序</option>
                <option value="latest">按最新值排序</option>
                <option value="name">按供应商名称排序</option>
            </select>
            <select id="periodSelect" onchange="updatePeriod()">
                <option value="3">显示3期</option>
                <option value="4">显示4期</option>
                <option value="5" selected>显示5期</option>
            </select>
        </div>
        <div class="stat-row">
            <span>共 <strong id="detailCount">{len(detail)}</strong> 条记录</span>
        </div>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>序号</th><th>供应商</th><th>货类</th>
                        {''.join(f'<th colspan="3">{d}</th>' for d in detail_dates)}
                    </tr>
                    <tr>
                        <th></th><th></th><th></th>
                        {''.join(f'<th style="font-weight:400;font-size:12px;">数量(吨)</th><th style="font-weight:400;font-size:12px;">环比变化</th><th style="font-weight:400;font-size:12px;">增幅</th>' for _ in detail_dates)}
                    </tr>
                </thead>
                <tbody id="detailBody"></tbody>
            </table>
        </div>
    </div>

    <div class="footer">
        报告生成时间: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>

</div>

<script>
const dates = {json.dumps(dates)};
const totals = {json.dumps(totals)};
const supplierNames = {supplier_names_json};
const supplierValues = {supplier_values_json};
const cargoNames = {cargo_names_json};
const cargoValues = {cargo_values_json};
const allDetail = {detail_json};
const supplierAddRem = {supplier_add_rem_json};
const cargoAddRem = {cargo_add_rem_json};
const transLabels = {trans_labels};
const numPeriods = {num_periods};
const numTransitions = {num_transitions};
const showPeriods = {show_periods};
const colors = [
    '#4E79A7','#F28E2B','#E15759','#76B7B2','#59A14F',
    '#EDC948','#B07AA1','#FF9DA7','#9C755F','#BAB0AC',
    '#86BCB6','#D37295','#8CD17D','#B6992D','#499894',
    '#DC851F','#A0CBE8','#F1CE63','#D4A6C8','#FABFD2'
];
// 线条样式循环：实线、虚线、点线、长短线、短长线
const dashStyles = [[], [5,5], [2,4], [10,5], [5,5,2,5]];
// 点样式循环
const pointStyles = ['circle','rect','triangle','rectRot','star','cross','dash','line'];

// ─── 1. 总库存趋势 ───
new Chart(document.getElementById('totalTrendChart'), {{
    type: 'line',
    data: {{
        labels: dates,
        datasets: [{{
            label: '总库存 (吨)',
            data: totals,
            borderColor: '#2e86c1',
            backgroundColor: 'rgba(46,134,193,0.1)',
            fill: true, tension: 0.3,
            pointRadius: 6, pointHoverRadius: 9,
            pointBackgroundColor: '#2e86c1', pointBorderColor: '#fff',
            pointBorderWidth: 2, borderWidth: 3,
        }}]
    }},
    options: {{
        responsive: true, maintainAspectRatio: true,
        plugins: {{ tooltip: {{ callbacks: {{ label: ctx => ctx.parsed.y.toLocaleString() + ' 吨' }} }} }},
        scales: {{ y: {{ beginAtZero: false, ticks: {{ callback: v => v.toLocaleString() }} }} }}
    }}
}});

// ─── 2. 供应商趋势（优化：配色+线型+点击切换） ───
const supDatasets = supplierNames.map((name, i) => ({{
    label: name, data: supplierValues[i],
    borderColor: colors[i % colors.length],
    backgroundColor: colors[i % colors.length] + '33',
    borderDash: dashStyles[i % dashStyles.length],
    borderWidth: 3,
    pointStyle: pointStyles[i % pointStyles.length],
    pointRadius: 5,
    pointHoverRadius: 8,
    pointBackgroundColor: colors[i % colors.length],
    pointBorderColor: '#fff',
    pointBorderWidth: 2,
    fill: false, tension: 0.25,
}}));
new Chart(document.getElementById('supplierChart'), {{
    type: 'line',
    data: {{ labels: dates, datasets: supDatasets }},
    options: {{
        responsive: true, maintainAspectRatio: true,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
            legend: {{
                display: true, position: 'bottom',
                labels: {{ padding: 14, usePointStyle: true, pointStyle: 'circle', font: {{ size: 12 }},
                    generateLabels: function(chart) {{
                        return chart.data.labels.length ? chart.data.datasets.map((ds, i) => ({{
                            text: ds.label,
                            fillStyle: colors[i % colors.length],
                            strokeStyle: colors[i % colors.length],
                            pointStyle: pointStyles[i % pointStyles.length],
                            hidden: !chart.isDatasetVisible(i),
                            datasetIndex: i
                        }})) : [];
                    }}
                }},
                onClick: function(e, legendItem, legend) {{
                    const index = legendItem.datasetIndex;
                    const ci = legend.chart;
                    const meta = ci.getDatasetMeta(index);
                    meta.hidden = meta.hidden === null ? !ci.data.datasets[index].hidden : null;
                    ci.update();
                }}
            }},
            tooltip: {{
                mode: 'index', intersect: false,
                callbacks: {{
                    label: ctx => ctx.dataset.label + ': ' + ctx.parsed.y.toLocaleString() + ' 吨'
                }}
            }}
        }},
        scales: {{
            y: {{ beginAtZero: false, ticks: {{ callback: v => v.toLocaleString() }}, title: {{ display: true, text: '库存量 (吨)' }} }},
            x: {{ title: {{ display: true, text: '日期' }} }}
        }}
    }}
}});
// 移除独立图例（改用 Chart.js 内置图例）

// ─── 3. 货类趋势（优化：配色+线型+点击切换） ───
const carDatasets = cargoNames.map((name, i) => ({{
    label: name, data: cargoValues[i],
    borderColor: colors[i % colors.length],
    backgroundColor: colors[i % colors.length] + '33',
    borderDash: dashStyles[i % dashStyles.length],
    borderWidth: 3,
    pointStyle: pointStyles[i % pointStyles.length],
    pointRadius: 5,
    pointHoverRadius: 8,
    pointBackgroundColor: colors[i % colors.length],
    pointBorderColor: '#fff',
    pointBorderWidth: 2,
    fill: false, tension: 0.25,
}}));
new Chart(document.getElementById('cargoChart'), {{
    type: 'line',
    data: {{ labels: dates, datasets: carDatasets }},
    options: {{
        responsive: true, maintainAspectRatio: true,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
            legend: {{
                display: true, position: 'bottom',
                labels: {{ padding: 14, usePointStyle: true, pointStyle: 'circle', font: {{ size: 12 }},
                    generateLabels: function(chart) {{
                        return chart.data.labels.length ? chart.data.datasets.map((ds, i) => ({{
                            text: ds.label,
                            fillStyle: colors[i % colors.length],
                            strokeStyle: colors[i % colors.length],
                            pointStyle: pointStyles[i % pointStyles.length],
                            hidden: !chart.isDatasetVisible(i),
                            datasetIndex: i
                        }})) : [];
                    }}
                }},
                onClick: function(e, legendItem, legend) {{
                    const index = legendItem.datasetIndex;
                    const ci = legend.chart;
                    const meta = ci.getDatasetMeta(index);
                    meta.hidden = meta.hidden === null ? !ci.data.datasets[index].hidden : null;
                    ci.update();
                }}
            }},
            tooltip: {{
                mode: 'index', intersect: false,
                callbacks: {{
                    label: ctx => ctx.dataset.label + ': ' + ctx.parsed.y.toLocaleString() + ' 吨'
                }}
            }}
        }},
        scales: {{
            y: {{ beginAtZero: false, ticks: {{ callback: v => v.toLocaleString() }}, title: {{ display: true, text: '库存量 (吨)' }} }},
            x: {{ title: {{ display: true, text: '日期' }} }}
        }}
    }}
}});
// 移除独立图例（改用 Chart.js 内置图例）

// 新增/减少图表 - 当前展示的对比期索引（默认最新一期）
let addRemPeriodIdx = transLabels.length - 1;

function renderSupplierAddRemChart(idx) {{
    const names = supplierAddRem.map(d => d.name);
    const addData = supplierAddRem.map(d => (d.add_values[idx] !== undefined ? d.add_values[idx] : 0));
    const remData = supplierAddRem.map(d => (d.rem_values[idx] !== undefined ? d.rem_values[idx] : 0));
    const ctx = document.getElementById('supplierAddRemChart');
    if (window._supChart) window._supChart.destroy();
    window._supChart = new Chart(ctx, {{
        type: 'bar',
        data: {{
            labels: names,
            datasets: [
                {{ label: '新增', data: addData, backgroundColor: 'rgba(231,76,60,0.7)', borderColor: '#e74c3c', borderWidth: 1 }},
                {{ label: '减少', data: remData, backgroundColor: 'rgba(39,174,96,0.7)', borderColor: '#27ae60', borderWidth: 1 }}
            ]
        }},
        options: {{
            responsive: true, maintainAspectRatio: true,
            plugins: {{
                tooltip: {{ callbacks: {{ label: ctx => ctx.dataset.label + ': ' + ctx.parsed.y.toLocaleString() + ' 吨' }} }},
            }},
            scales: {{
                y: {{ beginAtZero: true, ticks: {{ callback: v => v.toLocaleString() }} }}
            }}
        }}
    }});
}}

function renderCargoAddRemChart(idx) {{
    const names = cargoAddRem.map(d => d.name);
    const addData = cargoAddRem.map(d => (d.add_values[idx] !== undefined ? d.add_values[idx] : 0));
    const remData = cargoAddRem.map(d => (d.rem_values[idx] !== undefined ? d.rem_values[idx] : 0));
    const ctx = document.getElementById('cargoAddRemChart');
    if (window._carChart) window._carChart.destroy();
    window._carChart = new Chart(ctx, {{
        type: 'bar',
        data: {{
            labels: names,
            datasets: [
                {{ label: '新增', data: addData, backgroundColor: 'rgba(231,76,60,0.7)', borderColor: '#e74c3c', borderWidth: 1 }},
                {{ label: '减少', data: remData, backgroundColor: 'rgba(39,174,96,0.7)', borderColor: '#27ae60', borderWidth: 1 }}
            ]
        }},
        options: {{
            responsive: true, maintainAspectRatio: true,
            plugins: {{
                tooltip: {{ callbacks: {{ label: ctx => ctx.dataset.label + ': ' + ctx.parsed.y.toLocaleString() + ' 吨' }} }},
            }},
            scales: {{
                y: {{ beginAtZero: true, ticks: {{ callback: v => v.toLocaleString() }} }}
            }}
        }}
    }});
}}

function switchAddRemPeriod(idx) {{
    addRemPeriodIdx = idx;
    renderSupplierAddRemChart(idx);
    renderCargoAddRemChart(idx);
    // 高亮按钮
    document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
    const btns = document.querySelectorAll('.period-btn');
    if (btns[idx]) btns[idx].classList.add('active');
}}

// 初始化图表（最新一期）
renderSupplierAddRemChart(addRemPeriodIdx);
renderCargoAddRemChart(addRemPeriodIdx);

// 供应商新增/减少表格（展示所有期）
(function() {{
    const tbody = document.getElementById('supplierAddRemBody');
    if (!tbody) return;
    let html = '';
    const supData = supplierAddRem;
    supData.forEach(d => {{
        html += '<tr>';
        html += '<td class="supplier-col">' + d.name + '</td>';
        for (let i = 0; i < transLabels.length; i++) {{
            const addV = d.add_values[i] || 0;
            const remV = d.rem_values[i] || 0;
            html += '<td class="num-col num-add">' + (addV ? addV.toLocaleString() : '0') + '</td>';
            html += '<td class="num-col num-rem">' + (remV ? remV.toLocaleString() : '0') + '</td>';
        }}
        const netSum = d.net_values.reduce((a, b) => a + b, 0);
        const netStr = netSum > 0 ? '+' + netSum.toLocaleString() : netSum.toLocaleString();
        const netColor = netSum > 0 ? 'num-add' : (netSum < 0 ? 'num-rem' : '');
        html += '<td class="num-col ' + netColor + '">' + netStr + '</td>';
        html += '</tr>';
    }});
    tbody.innerHTML = html;
}})();

// 货类新增/减少表格（展示所有期）
(function() {{
    const tbody = document.getElementById('cargoAddRemBody');
    if (!tbody) return;
    let html = '';
    const carData = cargoAddRem;
    carData.forEach(d => {{
        html += '<tr>';
        html += '<td class="cargo-col">' + d.name + '</td>';
        for (let i = 0; i < transLabels.length; i++) {{
            const addV = d.add_values[i] || 0;
            const remV = d.rem_values[i] || 0;
            html += '<td class="num-col num-add">' + (addV ? addV.toLocaleString() : '0') + '</td>';
            html += '<td class="num-col num-rem">' + (remV ? remV.toLocaleString() : '0') + '</td>';
        }}
        const netSum = d.net_values.reduce((a, b) => a + b, 0);
        const netStr = netSum > 0 ? '+' + netSum.toLocaleString() : netSum.toLocaleString();
        const netColor = netSum > 0 ? 'num-add' : (netSum < 0 ? 'num-rem' : '');
        html += '<td class="num-col ' + netColor + '">' + netStr + '</td>';
        html += '</tr>';
    }});
    tbody.innerHTML = html;
}})();

// ─── 6. 明细表 ───
let currentDetail = [...allDetail];
let periodCount = showPeriods;
let searchText = '';

function fmtNum(v) {{ return (v === null || v === undefined) ? '-' : v.toLocaleString(); }}
function _changeColor(v) {{ if(v===null) return ''; if(v>0) return 'style="color:#e74c3c;"'; if(v<0) return 'style="color:#27ae60;"'; return 'style="color:#7f8c8d;"'; }}
function _pctColor(v) {{ if(v===null) return ''; if(v>0) return 'style="color:#e74c3c;font-weight:bold;"'; if(v<0) return 'style="color:#27ae60;font-weight:bold;"'; return 'style="color:#7f8c8d;"'; }}
function _fmtChange(v) {{ if(v===null) return '-'; if(v>0) return '+'+v.toLocaleString(); if(v<0) return v.toLocaleString(); return '0'; }}
function _fmtPct(v) {{ if(v===null) return '-'; if(v>0) return '+'+v+'%'; if(v<0) return v+'%'; return '0%'; }}

function getDatesSlice() {{ return dates.slice(-periodCount); }}

function renderTable() {{
    const tbody = document.getElementById('detailBody');
    const ds = getDatesSlice();
    const offset = numPeriods - ds.length;
    let filtered = currentDetail;
    if (searchText) {{
        const st = searchText.toLowerCase();
        filtered = filtered.filter(d => d.supplier.toLowerCase().includes(st) || d.cargo.toLowerCase().includes(st));
    }}
    document.getElementById('detailCount').textContent = filtered.length;
    if (filtered.length === 0) {{
        tbody.innerHTML = '<tr><td colspan="' + (3 + ds.length * 3) + '" style="text-align:center;padding:40px;color:#999;">无匹配记录</td></tr>';
        return;
    }}
    let html = '';
    filtered.forEach((d, idx) => {{
        const rank = idx + 1;
        let badge = rank <= 3 ? '<span class="rank-badge rank-' + rank + '">' + rank + '</span>' : rank;
        html += '<tr><td>' + badge + '</td><td class="supplier-col">' + d.supplier + '</td><td class="cargo-col">' + d.cargo + '</td>';
        for (let j = offset; j < numPeriods; j++) {{
            const v = d.values[j], ch = d.changes[j], pc = d.pct_changes[j];
            html += '<td class="num-col">' + fmtNum(v) + '</td>';
            if (j === offset) {{
                html += '<td class="change-col" style="color:#999;">基准</td><td class="pct-col" style="color:#999;">-</td>';
            }} else {{
                html += '<td class="change-col" ' + (ch !== null && ch !== 0 ? _changeColor(ch) : '') + '>' + _fmtChange(ch) + '</td>';
                html += '<td class="pct-col" ' + (pc !== null && pc !== 0 ? _pctColor(pc) : '') + '>' + _fmtPct(pc) + '</td>';
            }}
        }}
        html += '</tr>';
    }});
    tbody.innerHTML = html;
}}

function filterTable() {{ searchText = document.getElementById('searchInput').value; renderTable(); }}
function sortTable() {{
    const mode = document.getElementById('sortSelect').value;
    if (mode === 'total') currentDetail.sort((a,b) => b.total - a.total);
    else if (mode === 'latest') currentDetail.sort((a,b) => b.latest - a.latest);
    else if (mode === 'name') currentDetail.sort((a,b) => a.supplier.localeCompare(b.supplier));
    renderTable();
}}
function updatePeriod() {{ periodCount = parseInt(document.getElementById('periodSelect').value); renderTable(); }}

renderTable();
</script>
</body>
</html>'''

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"HTML可视化报告已保存至: {output_path}")
    print(f"  - 共 {num_periods} 期数据")
    print(f"  - {len(supplier_data)} 个供应商, {len(cargo_data)} 种货类")
    print(f"  - {len(detail)} 条供应商-货类明细记录")

    return html