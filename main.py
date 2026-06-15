"""
港口可贸易资源 - 数据处理系统主程序

功能：
1. 读取Excel原始数据，进行清洗、去重、格式统一
2. 自动识别不同日期的文件，对比数据变化
3. 生成详细的变化分析报告（文本+Excel）
"""

import sys
import argparse
from pathlib import Path

# 添加当前目录到系统路径
sys.path.insert(0, str(Path(__file__).parent))

from data_cleaner import clean_excel, save_clean_data, batch_clean
from data_tracker import auto_track, track_with_baseline, find_data_files, multi_period_analysis
from report_generator import generate_text_report, generate_excel_report, print_summary
from report_viz import generate_html_report


def cmd_clean(args):
    """执行数据清洗命令"""
    print("=" * 60)
    print("  数据清洗模块")
    print("=" * 60)

    input_path = Path(args.input)
    output_dir = args.output or "clean_data"

    if input_path.is_file():
        # 单个文件清洗
        df = clean_excel(str(input_path))
        if args.output:
            clean_name = f"clean_{input_path.name}"
            save_clean_data(df, str(Path(output_dir) / clean_name))
        print(f"\n清洗完成！共 {len(df)} 条记录")
        return df
    elif input_path.is_dir():
        # 批量清洗
        results = batch_clean(str(input_path), output_dir)
        total = sum(len(df) for df in results.values())
        print(f"\n批量清洗完成！共处理 {len(results)} 个文件，{total} 条记录")
        return results
    else:
        print(f"错误: 输入路径不存在: {args.input}")
        return None


def cmd_track(args):
    """执行数据追踪对比命令"""
    print("=" * 60)
    print("  数据追踪对比模块")
    print("=" * 60)

    if args.baseline and args.new:
        # 指定基准和新增文件
        result = track_with_baseline(args.new, args.baseline)
    else:
        # 自动识别清洗数据目录中的文件
        clean_dir = args.clean_dir or "clean_data"
        result = auto_track(clean_dir)
        if result and len(result) == 1:
            # 只有一组对比
            result = list(result.values())[0]
        elif result and len(result) > 1:
            # 多组对比 - 取最后一组（最新对比）
            last_key = list(result.keys())[-1]
            print(f"\n多组对比结果，取最新对比: {last_key}")
            result = result[last_key]

    return result


def cmd_report(args):
    """生成报告命令"""
    print("=" * 60)
    print("  报告生成模块")
    print("=" * 60)

    # 先执行追踪对比
    tracker_results = cmd_track(args)
    if tracker_results is None:
        print("无法生成报告：数据对比失败")
        return

    if isinstance(tracker_results, dict) and 'summary' in tracker_results:
        # 单个对比结果
        text_report = generate_text_report(tracker_results)

        if args.excel:
            excel_path = args.excel
        else:
            excel_path = "analysis_report.xlsx"

        generate_excel_report(tracker_results, excel_path)

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(text_report)

        print_summary(tracker_results)
    else:
        print("对比结果格式异常")


def cmd_viz(args):
    """执行HTML可视化报告生成命令"""
    print("=" * 60)
    print("  HTML可视化报告生成模块（多期趋势）")
    print("=" * 60)

    analysis_data = multi_period_analysis(args.clean_dir, top_n=args.top)
    if analysis_data is None or len(analysis_data['dates']) < 2:
        print("错误：至少需要2期数据才能生成趋势报告")
        return

    generate_html_report(analysis_data, args.output, periods_to_show=args.periods)


def main():
    parser = argparse.ArgumentParser(
        description="港口可贸易资源 - 数据处理系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 数据清洗
  python main.py clean -i 港口可贸易资源2026.6.5.xlsx -o clean_data
  
  # 批量清洗
  python main.py clean -i . -o clean_data
  
  # 自动追踪对比（自动识别clean_data目录中所有清洗文件）
  python main.py track
  
  # 指定文件对比
  python main.py track --baseline clean_data/clean_旧文件.xlsx --new clean_data/clean_新文件.xlsx
  
  # 生成完整报告（文本+Excel）
  python main.py report --excel report.xlsx -o report.txt
  
  # 一键完成：清洗→对比→报告
  python main.py pipeline -i . -o clean_data --excel report.xlsx
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='子命令')

    # clean 子命令
    clean_parser = subparsers.add_parser('clean', help='数据清洗')
    clean_parser.add_argument('-i', '--input', required=True,
                              help='输入文件或目录路径')
    clean_parser.add_argument('-o', '--output', default='clean_data',
                              help='输出目录（默认: clean_data）')

    # track 子命令
    track_parser = subparsers.add_parser('track', help='数据追踪对比')
    track_parser.add_argument('--baseline', help='基准（旧）清洗数据文件')
    track_parser.add_argument('--new', help='新增清洗数据文件')
    track_parser.add_argument('--clean-dir', default='clean_data',
                              help='清洗数据目录（默认: clean_data）')

    # report 子命令
    report_parser = subparsers.add_parser('report', help='生成变化分析报告')
    report_parser.add_argument('--baseline', help='基准（旧）清洗数据文件')
    report_parser.add_argument('--new', help='新增清洗数据文件')
    report_parser.add_argument('--clean-dir', default='clean_data',
                               help='清洗数据目录（默认: clean_data）')
    report_parser.add_argument('-o', '--output', default='analysis_report.txt',
                               help='文本报告输出路径')
    report_parser.add_argument('--excel', default='analysis_report.xlsx',
                               help='Excel报告输出路径')

    # viz 子命令（HTML可视化报告）
    viz_parser = subparsers.add_parser('viz', help='生成HTML可视化报告（多期趋势）')
    viz_parser.add_argument('--clean-dir', default='clean_data',
                            help='清洗数据目录（默认: clean_data）')
    viz_parser.add_argument('-o', '--output', default='analysis_trend.html',
                            help='HTML报告输出路径（默认: analysis_trend.html）')
    viz_parser.add_argument('--periods', type=int, default=5,
                            help='表格中显示的期数（默认: 5）')
    viz_parser.add_argument('--top', type=int, default=15,
                            help='图表中显示Top N供应商/货类（默认: 15）')

    # pipeline 子命令（一键完成）
    pipeline_parser = subparsers.add_parser('pipeline', help='一键执行：清洗→对比→报告')
    pipeline_parser.add_argument('-i', '--input', required=True,
                                 help='原始数据文件或目录')
    pipeline_parser.add_argument('-o', '--output', default='clean_data',
                                 help='清洗数据输出目录（默认: clean_data）')
    pipeline_parser.add_argument('--excel', default='analysis_report.xlsx',
                                 help='Excel报告输出路径')
    pipeline_parser.add_argument('--report-txt', default='analysis_report.txt',
                                 help='文本报告输出路径')

    args = parser.parse_args()

    if args.command == 'clean':
        cmd_clean(args)
    elif args.command == 'track':
        result = cmd_track(args)
        if result and isinstance(result, dict) and 'summary' in result:
            print_summary(result)
    elif args.command == 'report':
        cmd_report(args)
    elif args.command == 'viz':
        cmd_viz(args)
    elif args.command == 'pipeline':
        # 一键流程
        print("\n" + "█" * 60)
        print("  港口可贸易资源数据处理系统 - 一键执行")
        print("█" * 60)

        # Step 1: 清洗
        print("\n【步骤1】数据清洗")
        print("-" * 40)
        clean_results = cmd_clean(args)
        if clean_results is None:
            print("数据清洗失败，终止流程")
            return

        # Step 2: 追踪对比
        print("\n【步骤2】数据追踪对比")
        print("-" * 40)
        track_result = auto_track(args.output)
        if track_result is None:
            print("数据对比失败或无需对比，终止流程")
            return

        # Step 3: 报告生成
        print("\n【步骤3】生成变化分析报告")
        print("-" * 40)
        for comp_name, comp_result in track_result.items():
            print(f"\n--- {comp_name} ---")

            # 文本报告
            report_txt = args.report_txt
            if len(track_result) > 1:
                stem = comp_name.replace('→', '_vs_')
                report_txt = f"report_{stem}.txt"

            generate_text_report(comp_result, output_path=report_txt)

            # Excel报告
            excel_path = args.excel
            if len(track_result) > 1:
                stem = comp_name.replace('→', '_vs_')
                excel_path = f"report_{stem}.xlsx"

            generate_excel_report(comp_result, excel_path)
            print_summary(comp_result)

        print(f"\n{'█' * 60}")
        print(f"  全部流程完成！")
        print(f"{'█' * 60}")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()