"""
一键更新脚本
运行方式：python update.py

功能：
  1. 自动识别并清洗工作目录中新增的原始Excel文件
  2. 自动对比所有期数据，生成新增/减少分析报告
  3. 生成HTML可视化趋势报告

不需要任何参数，直接运行即可。
"""

import sys
from pathlib import Path

# 添加当前目录到系统路径
sys.path.insert(0, str(Path(__file__).parent))

from data_cleaner import batch_clean
from data_tracker import auto_track
from report_generator import generate_text_report, generate_excel_report, print_summary
from report_viz import generate_html_report
from data_tracker import multi_period_analysis


def main():
    print("=" * 60)
    print("  港口可贸易资源 - 一键更新")
    print("=" * 60)
    print()

    # 1. 批量清洗原始数据
    print("【步骤1/3】清洗原始数据文件...")
    print("-" * 40)
    results = batch_clean(".", "clean_data")
    if not results:
        print("没有需要清洗的原始文件，跳过。")
    else:
        print(f"  完成：清洗了 {len(results)} 个文件")
    print()

    # 2. 数据追踪对比 + 生成报告
    print("【步骤2/3】数据对比并生成分析报告...")
    print("-" * 40)
    track_result = auto_track("clean_data")
    if track_result is None:
        print("  没有可对比的数据（至少需要2期数据）")
    else:
        for comp_name, comp_result in track_result.items():
            print(f"  [{comp_name}]")
            # 文本报告
            txt_path = f"report_{comp_name.replace('→', '_vs_')}.txt"
            generate_text_report(comp_result, output_path=txt_path)
            # Excel报告
            xlsx_path = f"report_{comp_name.replace('→', '_vs_')}.xlsx"
            generate_excel_report(comp_result, xlsx_path)
            print_summary(comp_result)
        print("  报告已保存")
    print()

    # 3. 生成HTML可视化趋势报告
    print("【步骤3/3】生成HTML可视化趋势报告...")
    print("-" * 40)
    analysis_data = multi_period_analysis("clean_data")
    if analysis_data is None or len(analysis_data['dates']) < 2:
        print("  至少需要2期数据才能生成趋势报告，跳过。")
    else:
        generate_html_report(analysis_data, "analysis_trend.html")
        print(f"  HTML趋势报告已保存至: analysis_trend.html")
        print(f"  - 共 {len(analysis_data['dates'])} 期数据")
        print(f"  - {len(analysis_data['supplier_data'])} 个供应商, {len(analysis_data['cargo_data'])} 种货类")
    print()

    print("=" * 60)
    print("  全部更新完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
