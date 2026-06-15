"""
数据清洗模块 - 负责读取Excel原始数据，进行数据清洗、去重、格式统一处理
"""

import re
import pandas as pd
from pathlib import Path
from typing import Optional


# 标准货类名称映射（用于统一格式）
CARGO_NAME_MAPPING = {
    # 可在此扩展更多映射
}


def _extract_date_from_filename(filename: str) -> Optional[str]:
    """从文件名中提取日期信息，如 '港口可贸易资源2026.6.5.xlsx' -> '2026.6.5'"""
    match = re.search(r'(\d{4}\.\d{1,2}\.\d{1,2})', filename)
    if match:
        return match.group(1)
    return None


def _is_clean_format(raw_df: pd.DataFrame) -> bool:
    """判断是否为已清洗的简单格式（第一行即为列名）"""
    first_row = raw_df.iloc[0].astype(str).tolist()
    # 如果第一行包含'货类'且数据行较少（没有复杂的标题结构），视为干净格式
    has_cargo = any('货类' in str(v) for v in first_row)
    if not has_cargo:
        return False
    # 检查第二行是否为数字（数据行）
    if len(raw_df) > 1:
        second_row = raw_df.iloc[1].astype(str).tolist()
        # 干净格式的第二行通常包含供应商名称，原始格式的第二行通常是空行或标题
        second_row_clean = [v for v in second_row if v not in ('', 'nan', 'None')]
        first_row_clean = [v for v in first_row if v not in ('', 'nan', 'None')]
        # 如果第一行列名数量和第二行数据字段数量接近，很可能是干净格式
        return len(second_row_clean) >= 3
    return False


def _parse_sheet(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    解析原始Excel数据表，提取结构化数据
    
    支持两种格式：
    1. 原始格式：复杂表头、合并单元格
    2. 已清洗格式：简单表格，第一行为列名
    """
    # 判断是否为干净格式
    if _is_clean_format(raw_df):
        return _parse_clean_format(raw_df)
    else:
        return _parse_raw_format(raw_df)


def _parse_clean_format(raw_df: pd.DataFrame) -> pd.DataFrame:
    """解析已清洗的简单格式（第一行为列名）"""
    df = raw_df.copy()
    df.columns = df.iloc[0].astype(str).str.strip()
    df = df.iloc[1:].reset_index(drop=True)
    
    # 确保必要列存在
    required_cols = ['货类', '供应商', '数量']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"干净格式数据缺少必要列: {col}")
    
    # 转换数量为数值型
    df['数量'] = pd.to_numeric(df['数量'], errors='coerce')
    df = df.dropna(subset=['数量'])
    df['数量'] = df['数量'].astype(int)
    
    # 清理字符串列
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.strip().replace('nan', '').replace('None', '')
    
    # 指标列转为数值
    if '指标' in df.columns:
        df['指标'] = pd.to_numeric(df['指标'], errors='coerce')
    
    return df.reset_index(drop=True)


def _parse_raw_format(raw_df: pd.DataFrame) -> pd.DataFrame:
    """解析原始Excel数据表（复杂表头、合并单元格）"""
    # 查找表头行：包含"货类"的行
    header_row_idx = None
    for i in range(min(10, len(raw_df))):
        row_vals = raw_df.iloc[i].astype(str).tolist()
        if any('货类' in str(v) for v in row_vals):
            header_row_idx = i
            break
    
    if header_row_idx is None:
        raise ValueError("无法找到表头行（包含'货类'的行）")
    
    # 重新读取，以表头行为列名
    df = raw_df.iloc[header_row_idx + 1:].copy()
    df.columns = ['货类', '供应商', '数量', '港口', '指标', '船名', '备注']
    df = df.reset_index(drop=True)
    
    # 前向填充货类（处理合并单元格）
    df['货类'] = df['货类'].replace('', pd.NA).replace('nan', pd.NA)
    df['货类'] = df['货类'].ffill()
    
    # 过滤无效行：排除空供应商、总计行
    df = df[df['供应商'].notna() & (df['供应商'].astype(str).str.strip() != '')]
    df = df[~df['供应商'].astype(str).str.strip().str.contains('总计')]
    # 排除货类包含"总计"的行
    if '货类' in df.columns:
        df = df[~df['货类'].astype(str).str.strip().str.contains('总计')]
    # 排除供应商名称为"货类"的误匹配行
    df = df[df['供应商'].astype(str).str.strip() != '货类']
    
    # 转换数量为数值型
    df['数量'] = pd.to_numeric(df['数量'], errors='coerce')
    df = df.dropna(subset=['数量'])
    df['数量'] = df['数量'].astype(int)
    
    # 清理字符串列
    for col in ['供应商', '港口', '船名', '备注']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace('nan', '')
    
    # 统一货类名称
    if '货类' in df.columns:
        df['货类'] = df['货类'].astype(str).str.strip().replace('nan', '')
        df['货类'] = df['货类'].replace(CARGO_NAME_MAPPING)
    
    # 指标列转为数值
    if '指标' in df.columns:
        df['指标'] = pd.to_numeric(df['指标'], errors='coerce')
    
    return df.reset_index(drop=True)


def _deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """
    数据去重：基于关键字段（货类、供应商、数量、港口、船名）去除完全重复的行
    
    保留策略：对完全相同的记录，保留第一条
    """
    key_cols = ['货类', '供应商', '数量', '港口', '船名']
    before = len(df)
    df = df.drop_duplicates(subset=key_cols, keep='first')
    after = len(df)
    if before > after:
        print(f"  去重：移除 {before - after} 条重复记录")
    return df


def clean_excel(file_path: str) -> pd.DataFrame:
    """
    读取并清洗一个Excel文件
    
    Args:
        file_path: Excel文件路径
        
    Returns:
        清洗后的DataFrame，包含列：货类、供应商、数量、港口、指标、船名、备注
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    print(f"\n{'='*60}")
    print(f"正在处理文件: {file_path.name}")
    
    # 提取日期
    date_str = _extract_date_from_filename(file_path.name)
    if date_str:
        print(f"  识别日期: {date_str}")
    
    # 读取原始数据
    raw_df = pd.read_excel(file_path, sheet_name=0, header=None)
    print(f"  原始数据: {raw_df.shape[0]} 行 x {raw_df.shape[1]} 列")
    
    # 解析数据
    df = _parse_sheet(raw_df)
    print(f"  解析后: {len(df)} 条有效记录")
    
    # 去重
    df = _deduplicate(df)
    
    # 添加日期列
    if date_str:
        df['数据日期'] = date_str
    
    print(f"  清洗完成: {len(df)} 条记录")
    
    return df


def save_clean_data(df: pd.DataFrame, output_path: str):
    """保存清洗后的数据到Excel文件"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_excel(output_path, index=False, engine='openpyxl')
    print(f"  干净数据已保存至: {output_path}")


def batch_clean(input_dir: str, output_dir: str) -> dict:
    """
    批量清洗指定目录下的所有Excel文件
    
    Args:
        input_dir: 输入目录路径
        output_dir: 输出目录路径
        
    Returns:
        dict: {文件名: 清洗后的DataFrame}
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    all_excel = sorted(input_path.glob("*.xlsx"))
    # 排除临时文件(~$开头)、已清洗文件(clean_)、报告文件(analysis_/report_)
    excel_files = [
        f for f in all_excel
        if not f.name.startswith('~$')
        and not f.name.lower().startswith(('clean_', 'analysis_', 'report_'))
    ]

    if not excel_files:
        print(f"在 {input_dir} 中未找到原始Excel文件（已排除 clean_/analysis_/report_ 文件）")
        return {}
    
    print(f"\n找到 {len(excel_files)} 个原始Excel文件（已过滤 {len(all_excel) - len(excel_files)} 个非原始文件）:")
    for f in excel_files:
        print(f"  - {f.name}")
    
    result = {}
    for file_path in excel_files:
        df = clean_excel(str(file_path))
        result[file_path.name] = df
        
        # 保存清洗后的数据
        clean_name = f"clean_{file_path.name}"
        save_clean_data(df, str(output_path / clean_name))
    
    return result