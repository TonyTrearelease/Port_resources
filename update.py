"""
一键更新脚本
运行方式：python update.py

功能：
  1. 自动识别并清洗工作目录中新增的原始Excel文件
  2. 自动对比所有期数据，生成新增/减少分析报告
  3. 生成HTML可视化趋势报告
  4. 自动提交并推送代码到GitHub
"""

import sys
import subprocess
from pathlib import Path

# 添加当前目录到系统路径
sys.path.insert(0, str(Path(__file__).parent))

from data_cleaner import batch_clean
from data_tracker import auto_track, multi_period_analysis
from report_generator import generate_text_report, generate_excel_report, print_summary
from report_viz import generate_html_report


def _git_push():
    """提交并推送代码到GitHub"""
    print("【步骤4/4】提交并推送代码到GitHub...")
    print("-" * 40)

    # 检查是否是git仓库
    if not (Path(".git").exists()):
        print("  ! 未检测到git仓库，跳过提交推送。")
        print("  ! 如需使用该功能，请先执行：")
        print("      git init")
        print("      git remote add origin https://token@github.com/用户名/仓库名.git")
        return

    # 检查是否有远程仓库
    result = subprocess.run(
        ["git", "remote", "-v"],
        capture_output=True, text=True, encoding="utf-8"
    )
    if not result.stdout.strip():
        print("  ! 未配置远程仓库，跳过推送。")
        print("  ! 如需使用该功能，请先执行：")
        print("      git remote add origin https://token@github.com/用户名/仓库名.git")
        return

    # 检查是否有文件变更
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, encoding="utf-8"
    )
    if not result.stdout.strip():
        print("  没有需要提交的变更。")
        return

    # 统计变更
    lines = result.stdout.strip().split("\n")
    changed_count = len(lines)
    print(f"  检测到 {changed_count} 个文件变更")

    # 生成提交信息：根据最新的数据文件确定日期
    xlsx_files = sorted(Path(".").glob("港口可贸易资源*.xlsx"))
    if xlsx_files:
        latest = xlsx_files[-1].stem.replace("港口可贸易资源", "")
        commit_msg = f"更新数据：{latest}"
    else:
        commit_msg = "更新数据文件及分析报告"

    # git add
    print("  暂存文件...")
    result = subprocess.run(
        ["git", "add", "-A"],
        capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        print(f"  ! git add 失败：{result.stderr.strip()}")
        return

    # git commit
    print(f"  提交：{commit_msg}")
    result = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        if "nothing to commit" in result.stderr or "nothing to commit" in result.stdout:
            print("  没有需要提交的变更。")
            return
        print(f"  ! git commit 失败：{result.stderr.strip()}")
        return
    print(f"  {result.stdout.strip()}")

    # git push
    print("  推送...")
    result = subprocess.run(
        ["git", "push"],
        capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        print(f"  ! git push 失败：{result.stderr.strip()}")
        return
    # 只显示非空行
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if line:
            print(f"  {line}")

    print("  ✓ 已提交并推送到GitHub！")


def main():
    print("=" * 60)
    print("  港口可贸易资源 - 一键更新")
    print("=" * 60)
    print()

    # 1. 批量清洗原始数据
    print("【步骤1/4】清洗原始数据文件...")
    print("-" * 40)
    results = batch_clean(".", "clean_data")
    if not results:
        print("没有需要清洗的原始文件，跳过。")
    else:
        print(f"  完成：清洗了 {len(results)} 个文件")
    print()

    # 2. 数据追踪对比 + 生成报告
    print("【步骤2/4】数据对比并生成分析报告...")
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
    print("【步骤3/4】生成HTML可视化趋势报告...")
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

    # 4. 提交推送
    _git_push()
    print()

    print("=" * 60)
    print("  全部更新完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
