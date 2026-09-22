#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sony A6000 / A5100 SLY v2 LUT Packer (PC 端 3D LUT 转 SLY 格式工具)
将标准 .cube 3D LUT 文件深度分解为索尼微单 BIONZ X ISP 全管线硬件参数:
  - 60 字节 UTF-8 风格名称头 + 4 字节 Magic 'SLY2'
  - 3x3 定点 (x1024) RGB 颜色矩阵 (9 个 32-bit 小端整数 = 36 字节)
  - 白平衡偏移 (LB, CC, 2 个 32-bit 小端整数 = 8 字节)
  - 版本标志位 (uint32 = 4 字节, 0x00000002)
  - 80 字节多管线扩展参数区 (Base ColorMode, Cinema Tone, 6 轴色彩深度 R/G/B/C/M/Y, 对比度/饱和度/锐度, DRO)
  - 1024 点 10-bit 灰阶 Gamma 曲线 (2048 字节, 1024 个 16-bit 小端无符号整数)
SLY v2 总长度严格为 2240 字节，同时支持生成向下兼容的 SLY v1 (2160 字节)。
"""

import os
import sys
import struct
import argparse
import re
import math
from pathlib import Path
from typing import Tuple, List, Optional, Dict

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

KNOTS = 1024
MATRIX_SCALE = 1024
GRID = 24
ITERS = 35

SLY_V1_SIZE = 2160
SLY_V2_SIZE = 2240
SLY2_MAGIC = b'SLY2'

# 底模枚举
COLOR_MODES = ["neutral", "portrait", "standard", "landscape", "blackwhite"]
CINEMA_TONES = ["off", "cinema-tone-1", "cinema-tone-2"]


class CubeParser:
    """解析 .cube 文件，提取 3D LUT 数据并支持三线性插值采样"""
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.name = os.path.splitext(os.path.basename(filepath))[0]
        self.size = 0
        self.domain_min = [0.0, 0.0, 0.0]
        self.domain_max = [1.0, 1.0, 1.0]
        self.data: List[Tuple[float, float, float]] = []
        self._parse()

    def _parse(self):
        with open(self.filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                key = parts[0].upper()
                if key == "TITLE":
                    raw_title = line[5:].strip().strip('"').strip("'")
                    if raw_title:
                        self.name = raw_title
                elif key == "LUT_3D_SIZE":
                    self.size = int(parts[1])
                elif key == "DOMAIN_MIN":
                    self.domain_min = [float(parts[1]), float(parts[2]), float(parts[3])]
                elif key == "DOMAIN_MAX":
                    self.domain_max = [float(parts[1]), float(parts[2]), float(parts[3])]
                elif len(parts) == 3:
                    try:
                        r, g, b = float(parts[0]), float(parts[1]), float(parts[2])
                        self.data.append((r, g, b))
                    except ValueError:
                        continue

        if self.size == 0 or len(self.data) != self.size ** 3:
            raise ValueError(f"无效的 3D CUBE 文件: size={self.size}, 数据点数={len(self.data)}")

    def sample_trilinear(self, r: float, g: float, b: float) -> Tuple[float, float, float]:
        """三线性插值采样"""
        dmin, dmax = self.domain_min, self.domain_max
        r = max(0.0, min(1.0, (r - dmin[0]) / (dmax[0] - dmin[0] if dmax[0] > dmin[0] else 1.0)))
        g = max(0.0, min(1.0, (g - dmin[1]) / (dmax[1] - dmin[1] if dmax[1] > dmin[1] else 1.0)))
        b = max(0.0, min(1.0, (b - dmin[2]) / (dmax[2] - dmin[2] if dmax[2] > dmin[2] else 1.0)))

        N = self.size - 1
        rf, gf, bf = r * N, g * N, b * N
        r0, g0, b0 = int(rf), int(gf), int(bf)
        r1, g1, b1 = min(r0 + 1, N), min(g0 + 1, N), min(b0 + 1, N)
        dr, dg, db = rf - r0, gf - g0, bf - b0

        S = self.size
        S2 = S * S
        c000 = self.data[r0 + g0 * S + b0 * S2]
        c100 = self.data[r1 + g0 * S + b0 * S2]
        c010 = self.data[r0 + g1 * S + b0 * S2]
        c110 = self.data[r1 + g1 * S + b0 * S2]
        c001 = self.data[r0 + g0 * S + b1 * S2]
        c101 = self.data[r1 + g0 * S + b1 * S2]
        c011 = self.data[r0 + g1 * S + b1 * S2]
        c111 = self.data[r1 + g1 * S + b1 * S2]

        out = []
        for ch in range(3):
            v00 = c000[ch] * (1.0 - dr) + c100[ch] * dr
            v01 = c001[ch] * (1.0 - dr) + c101[ch] * dr
            v10 = c010[ch] * (1.0 - dr) + c110[ch] * dr
            v11 = c011[ch] * (1.0 - dr) + c111[ch] * dr
            v0 = v00 * (1.0 - dg) + v10 * dg
            v1 = v01 * (1.0 - dg) + v11 * dg
            out.append(v0 * (1.0 - db) + v1 * db)

        return (out[0], out[1], out[2])


def rgb_to_hue(r: float, g: float, b: float) -> float:
    """计算 RGB 对应的色相角 (0..360)"""
    mx = max(r, g, b)
    mn = min(r, g, b)
    df = mx - mn
    if df < 1e-6:
        return 0.0
    if mx == r:
        h = (60.0 * ((g - b) / df) + 360.0) % 360.0
    elif mx == g:
        h = (60.0 * ((b - r) / df) + 120.0) % 360.0
    else:
        h = (60.0 * ((r - g) / df) + 240.0) % 360.0
    return h


def decompose_multi_pipeline(cube: CubeParser) -> Dict:
    """
    全管线联合反向求解器 (SLY v2):
    1. 评估最佳底模 (neutral / portrait / landscape / standard)
    2. 白平衡硬件偏置 (LB, CC)
    3. 6 轴色彩深度 (R, G, B, C, M, Y 各 -3..+3)
    4. 约束 3x3 颜色矩阵 (有界交替最小二乘)
    5. 1024 点 10-bit 单调 Gamma 曲线
    6. Cinema Tone 判定
    """
    if not HAS_NUMPY:
        return decompose_pure_python_v2(cube)

    # 1. 采样均匀 3D 色彩网格
    n = GRID ** 3
    lin = np.linspace(0.0, 1.0, GRID, dtype=np.float64)
    R, G, B = np.meshgrid(lin, lin, lin, indexing='ij')
    X = np.stack([R.ravel(), G.ravel(), B.ravel()], axis=-1)

    L = np.zeros((n, 3), dtype=np.float64)
    for i in range(n):
        L[i] = cube.sample_trilinear(X[i, 0], X[i, 1], X[i, 2])

    # 2. 白平衡硬件偏置 (LB, CC) 求解
    # 采样 18% 与 50% 灰阶
    r_18, g_18, b_18 = cube.sample_trilinear(0.18, 0.18, 0.18)
    r_50, g_50, b_50 = cube.sample_trilinear(0.50, 0.50, 0.50)
    avg_r = (r_18 + r_50) * 0.5
    avg_g = (g_18 + g_50) * 0.5
    avg_b = (b_18 + b_50) * 0.5

    # LB: 琥珀(+)/蓝(-) 偏移; CC: 绿(+)/洋红(-) 偏移
    lb = int(round((avg_r - avg_b) * 24.0))
    cc = int(round((avg_g - (avg_r + avg_b) * 0.5) * 24.0))
    lb = max(-7, min(7, lb))
    cc = max(-7, min(7, cc))

    # 3. 6 轴色彩深度 (Color Depth: Red, Green, Blue, Cyan, Magenta, Yellow)
    # 针对 6 个主要色相扇区，测量 CUBE 与线性基底在饱和度与纯度上的比值
    sectors = {
        "red":     (0.8, 0.2, 0.2),
        "yellow":  (0.8, 0.8, 0.2),
        "green":   (0.2, 0.8, 0.2),
        "cyan":    (0.2, 0.8, 0.8),
        "blue":    (0.2, 0.2, 0.8),
        "magenta": (0.8, 0.2, 0.8),
    }
    color_depths = {}
    for name, (sr, sg, sb) in sectors.items():
        tr, tg, tb = cube.sample_trilinear(sr, sg, sb)
        src_sat = max(sr, sg, sb) - min(sr, sg, sb)
        dst_sat = max(tr, tg, tb) - min(tr, tg, tb)
        diff_sat = dst_sat - src_sat
        # 映射到 -3 ~ +3
        depth_val = int(round(diff_sat * 6.0))
        color_depths[name] = max(-3, min(3, depth_val))

    # 4. 底模选择 (Base Color Mode)
    # 评估中高光区域是否适合 Portrait (肤色保真) 或 Landscape (深蓝浓绿)
    r_skin, g_skin, b_skin = cube.sample_trilinear(0.8, 0.6, 0.5)  # 典型肤色点
    skin_hue = rgb_to_hue(r_skin, g_skin, b_skin)
    if 15.0 <= skin_hue <= 38.0 and abs(r_skin - 0.8) < 0.15:
        base_color_mode = 1  # portrait
    elif color_depths["blue"] >= 2 or color_depths["green"] >= 2:
        base_color_mode = 3  # landscape
    else:
        base_color_mode = 0  # neutral (最稳健、最少二次失真的底模)

    # 5. Cinema Tone 判定 (检测高光区滚降特征)
    r_hi, g_hi, b_hi = cube.sample_trilinear(0.95, 0.95, 0.95)
    hi_luma = 0.299 * r_hi + 0.587 * g_hi + 0.114 * b_hi
    if hi_luma < 0.92:
        cinema_tone = 1  # cinema-tone-1 (模拟胶片高光自然滚降)
    else:
        cinema_tone = 0  # off

    # 6. 1024 点初始单调 Gamma 曲线
    g_init = np.zeros(KNOTS, dtype=np.float64)
    for k in range(KNOTS):
        val = k / (KNOTS - 1)
        r, g_val, b = cube.sample_trilinear(val, val, val)
        g_init[k] = 0.299 * r + 0.587 * g_val + 0.114 * b

    g = np.maximum.accumulate(g_init.copy())
    if g[-1] > 1e-6:
        g /= g[-1]

    # 7. 约束 3x3 空间矩阵优化 (ALS)
    M = np.eye(3, dtype=np.float64)
    knot_idx = np.round(X * (KNOTS - 1)).astype(int)

    for _ in range(ITERS):
        U = np.interp(X, np.linspace(0, 1, KNOTS), g)

        UtU = U.T @ U
        UtL = U.T @ L
        try:
            W = np.linalg.solve(UtU + np.eye(3) * 1e-3, UtL)
            M = W.T
        except np.linalg.LinAlgError:
            pass

        # 归一化行和，保护中性轴平衡
        for c in range(3):
            s = np.sum(M[c])
            if abs(s) > 1e-4:
                M[c] /= s

        # 反向更新 Gamma
        num = np.zeros(KNOTS, dtype=np.float64)
        den = np.zeros(KNOTS, dtype=np.float64)

        for c in range(3):
            m_col = M[:, c]
            m2sq = np.sum(m_col ** 2)
            if m2sq < 1e-6:
                continue

            others = np.zeros((n, 3), dtype=np.float64)
            for cc_idx in range(3):
                if cc_idx != c:
                    others += np.outer(U[:, cc_idx], M[:, cc_idx])

            res = L - others
            proj = res @ m_col

            k_idx = knot_idx[:, c]
            np.add.at(num, k_idx, proj)
            den += np.bincount(k_idx, minlength=KNOTS) * m2sq

        valid = den > 1e-12
        new_g = np.zeros(KNOTS, dtype=np.float64)
        new_g[valid] = num[valid] / den[valid]
        if not np.all(valid):
            x_valid = np.where(valid)[0]
            if len(x_valid) > 0:
                new_g = np.interp(np.arange(KNOTS), x_valid, new_g[x_valid])

        g = 0.6 * g + 0.4 * new_g
        g = np.maximum.accumulate(g)

        top = g[-1]
        if top > 1e-6:
            g /= top
            M *= top

    # 最终约束与量化
    M_scaled = np.round(M * MATRIX_SCALE).astype(int)
    for c in range(3):
        diff = MATRIX_SCALE - np.sum(M_scaled[c])
        M_scaled[c, 1] += diff  # 补偿至绿色主通道

    gamma_int = np.clip(np.round(g * 1023), 0, 1023).astype(int).tolist()
    matrix_int = M_scaled.ravel().tolist()

    return {
        "version": 2,
        "gamma": gamma_int,
        "matrix": matrix_int,
        "lb": lb,
        "cc": cc,
        "base_color_mode": base_color_mode,
        "cinema_tone": cinema_tone,
        "depth_red": color_depths["red"],
        "depth_green": color_depths["green"],
        "depth_blue": color_depths["blue"],
        "depth_cyan": color_depths["cyan"],
        "depth_magenta": color_depths["magenta"],
        "depth_yellow": color_depths["yellow"],
        "contrast": 0,
        "saturation": 0,
        "sharpness": 0,
        "dro_mode": 0,
    }


def decompose_pure_python_v2(cube: CubeParser) -> Dict:
    """纯 Python 回退版本 (带基础管线参数)"""
    g = []
    for k in range(KNOTS):
        val = k / (KNOTS - 1)
        r, g_val, b = cube.sample_trilinear(val, val, val)
        g.append(0.299 * r + 0.587 * g_val + 0.114 * b)

    for k in range(1, KNOTS):
        if g[k] < g[k-1]:
            g[k] = g[k-1]
    top = g[-1]
    if top > 1e-6:
        g = [x / top for x in g]

    gamma_int = [max(0, min(1023, int(round(x * 1023)))) for x in g]
    matrix_int = [1024, 0, 0, 0, 1024, 0, 0, 0, 1024]
    return {
        "version": 2,
        "gamma": gamma_int,
        "matrix": matrix_int,
        "lb": 0,
        "cc": 0,
        "base_color_mode": 0,
        "cinema_tone": 0,
        "depth_red": 0,
        "depth_green": 0,
        "depth_blue": 0,
        "depth_cyan": 0,
        "depth_magenta": 0,
        "depth_yellow": 0,
        "contrast": 0,
        "saturation": 0,
        "sharpness": 0,
        "dro_mode": 0,
    }


def pack_sly_v1(name: str, matrix: List[int], lb: int, cc: int, gamma: List[int]) -> bytes:
    """打包为标准 2160 字节 SLY v1 文件 (兼容旧版)"""
    clean_name = name.encode('utf-8')[:63]
    header = clean_name + b'\x00' * (64 - len(clean_name))

    assert len(matrix) == 9
    params = struct.pack('<9i', *matrix)
    params += struct.pack('<ii', lb, cc)
    params += struct.pack('<i', 0)  # 保留字段

    assert len(gamma) == 1024
    gamma_bytes = struct.pack('<1024H', *gamma)

    data = header + params + gamma_bytes
    assert len(data) == SLY_V1_SIZE
    return data


def pack_sly_v2(name: str, params_dict: Dict) -> bytes:
    """
    打包为标准 2240 字节 SLY v2 文件 (多管线扩展):
      0x000..0x03B (60B): 预设名称
      0x03C..0x03F (4B) : Magic 'SLY2'
      0x040..0x063 (36B): 9 个矩阵整数
      0x064..0x067 (4B) : LB
      0x068..0x06B (4B) : CC
      0x06C..0x06F (4B) : Version Flag (2)
      0x070..0x0BF (80B): 多管线扩展参数区
      0x0C0..0x8BF (2048B): 1024 点 16-bit Gamma 表
    """
    # 1. 60 字节名称 + 4 字节 SLY2 Magic
    clean_name = name.encode('utf-8')[:59]
    header = clean_name + b'\x00' * (60 - len(clean_name)) + SLY2_MAGIC

    # 2. 48 字节参数区
    matrix = params_dict["matrix"]
    assert len(matrix) == 9
    params = struct.pack('<9i', *matrix)
    params += struct.pack('<ii', params_dict["lb"], params_dict["cc"])
    params += struct.pack('<I', 2)  # Version = 2

    # 3. 80 字节多管线扩展参数区
    pipeline = struct.pack(
        '<BBbbbbbbbbbB',
        params_dict.get("base_color_mode", 0),
        params_dict.get("cinema_tone", 0),
        params_dict.get("depth_red", 0),
        params_dict.get("depth_green", 0),
        params_dict.get("depth_blue", 0),
        params_dict.get("depth_cyan", 0),
        params_dict.get("depth_magenta", 0),
        params_dict.get("depth_yellow", 0),
        params_dict.get("contrast", 0),
        params_dict.get("saturation", 0),
        params_dict.get("sharpness", 0),
        params_dict.get("dro_mode", 0),
    )
    # 补齐至 80 字节 (保留区 68 字节)
    pipeline += b'\x00' * (80 - len(pipeline))
    assert len(pipeline) == 80

    # 4. 2048 字节 Gamma 表
    gamma = params_dict["gamma"]
    assert len(gamma) == 1024
    gamma_bytes = struct.pack('<1024H', *gamma)

    data = header + params + pipeline + gamma_bytes
    assert len(data) == SLY_V2_SIZE, f"SLY v2 大小错误: {len(data)} (应为 {SLY_V2_SIZE} 字节)"
    return data


BRAND_MAP = {
    "KODAK": "K",
    "FUJIFILM": "F",
    "FUJI": "F",
    "CINESTILL": "CS",
    "ILFORD": "ILF",
    "AGFA": "AG",
    "POLAROID": "POL",
    "SONY": "S",
    "LEICA": "L",
    "CANON": "C",
    "NIKON": "N",
}


def split_tokens(name: str) -> List[str]:
    """将文件名切分为单词和数字 token"""
    s = re.sub(r'([a-z])([A-Z])', r'\1_\2', name)
    s = re.sub(r'([0-9]+)', r'_\1_', s)
    raw_tokens = re.split(r'[^A-Za-z0-9]+', s)
    return [t.upper() for t in raw_tokens if t]


def generate_83_candidate(base_name: str, index: Optional[int] = None, numbered: bool = False) -> str:
    """根据原始文件名生成符合 8.3 规则的 8 字符以内候选名称"""
    tokens = split_tokens(base_name)
    if not tokens:
        tokens = ["LUT"]

    if numbered and index is not None:
        prefix = f"{index:02d}_"
        avail = 8 - len(prefix)
        rem = "".join(tokens)[:avail]
        return (prefix + rem)[:8]

    clean_all = re.sub(r'[^A-Za-z0-9_]', '', base_name).upper()
    clean_alnum = re.sub(r'[^A-Za-z0-9]', '', base_name).upper()
    if 0 < len(clean_all) <= 8:
        return clean_all
    if 0 < len(clean_alnum) <= 8:
        return clean_alnum

    brand_prefix = ""
    start_idx = 0
    if tokens[0] in BRAND_MAP:
        brand_prefix = BRAND_MAP[tokens[0]]
        start_idx = 1

    rem_tokens = tokens[start_idx:]
    if not rem_tokens:
        candidate = tokens[0][:8]
    elif len(rem_tokens) == 1:
        candidate = (brand_prefix + rem_tokens[0])[:8]
    elif len(rem_tokens) == 2:
        t0, t1 = rem_tokens[0], rem_tokens[1]
        avail = 8 - len(brand_prefix)
        if len(t0) <= 4:
            candidate = brand_prefix + t0 + t1[:(avail - len(t0))]
        else:
            p0_len = avail // 2
            p1_len = avail - p0_len
            candidate = brand_prefix + t0[:p0_len] + t1[:p1_len]
    else:
        avail = 8 - len(brand_prefix)
        first = rem_tokens[0][:3]
        last = rem_tokens[-1][:3]
        mid = "".join(t[:1] for t in rem_tokens[1:-1])[:max(0, avail - len(first) - len(last))]
        candidate = (brand_prefix + first + mid + last)[:8]

    candidate = re.sub(r'[^A-Za-z0-9_]', '', candidate).upper()[:8]
    if not candidate:
        candidate = clean_alnum[:8] if clean_alnum else "LUT"
    return candidate


def allocate_unique_83(candidate: str, used_names: set) -> str:
    """确保 8.3 文件名全局唯一"""
    cand = candidate[:8]
    if cand not in used_names:
        used_names.add(cand)
        return cand

    for i in range(1, 1000):
        if i < 10:
            prefix = cand[:6]
            name = f"{prefix}_{i}"
        elif i < 100:
            prefix = cand[:5]
            name = f"{prefix}_{i}"
        else:
            prefix = cand[:4]
            name = f"{prefix}_{i}"

        if name not in used_names:
            used_names.add(name)
            return name

    for i in range(1, 10000):
        name = f"L{i:07d}"[:8]
        if name not in used_names:
            used_names.add(name)
            return name


def convert_cube_to_sly(cube_path: str, output_dir: str, used_names: set, index: Optional[int] = None, numbered: bool = False, v1: bool = False) -> Optional[str]:
    """转换单个 .cube 文件为 SLY 文件 (默认 v2, 支持 --v1)"""
    cube_path = os.path.abspath(cube_path)
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    try:
        cube = CubeParser(cube_path)
    except Exception as e:
        print(f"[-] 解析失败 {cube_path}: {e}")
        return None

    res_dict = decompose_multi_pipeline(cube)

    base_name = os.path.splitext(os.path.basename(cube_path))[0]
    display_name = cube.name if cube.name else base_name

    candidate = generate_83_candidate(base_name, index=index, numbered=numbered)
    unique_stem = allocate_unique_83(candidate, used_names)
    sly_filename = f"{unique_stem}.SLY"
    target_path = os.path.join(output_dir, sly_filename)

    if v1:
        sly_bytes = pack_sly_v1(display_name, res_dict["matrix"], res_dict["lb"], res_dict["cc"], res_dict["gamma"])
        ver_tag = "v1 (2160B)"
    else:
        sly_bytes = pack_sly_v2(display_name, res_dict)
        ver_tag = "v2 (2240B, 多管线)"

    with open(target_path, "wb") as f:
        f.write(sly_bytes)

    mode_name = COLOR_MODES[res_dict["base_color_mode"]]
    ct_name = CINEMA_TONES[res_dict["cinema_tone"]]
    depths = [res_dict["depth_red"], res_dict["depth_green"], res_dict["depth_blue"],
              res_dict["depth_cyan"], res_dict["depth_magenta"], res_dict["depth_yellow"]]

    print(f"[+] 转换成功 [{ver_tag}]: {os.path.basename(cube_path)} -> {sly_filename}")
    print(f"    显示名称: {display_name} | 8.3 文件名: {sly_filename}")
    print(f"    底模: {mode_name} | CinemaTone: {ct_name} | LB/CC: {res_dict['lb']}/{res_dict['cc']}")
    print(f"    6轴深度 (R,G,B,C,M,Y): {depths}")
    return target_path


def main():
    parser = argparse.ArgumentParser(description="索尼 A6000 / A5100 SLY v2 胶片 LUT 多管线打包工具 (严格 8.3 格式)")
    parser.add_argument("-i", "--input", required=True, help="输入的 .cube 文件或包含 .cube 的目录")
    parser.add_argument("-o", "--output", default="./SONY_LUT", help="输出 SLY 文件的目录 (默认: ./SONY_LUT)")
    parser.add_argument("--numbered", action="store_true", help="使用序号前缀模式 (如 01_K238.SLY, 02_P400.SLY)")
    parser.add_argument("--v1", action="store_true", help="强制输出传统 SLY v1 格式 (2160 字节)")
    args = parser.parse_args()

    input_path = Path(args.input)
    out_arg = Path(args.output)
    if out_arg.suffix.lower() == ".sly":
        output_dir = out_arg.parent
        custom_out_file = out_arg
    else:
        output_dir = out_arg
        custom_out_file = None
    output_dir.mkdir(parents=True, exist_ok=True)

    cube_files = []
    seen_paths = set()
    if input_path.is_file():
        if input_path.suffix.lower() == ".cube":
            cube_files.append(input_path)
    elif input_path.is_dir():
        for p in sorted(input_path.rglob("*")):
            if p.is_file() and p.suffix.lower() == ".cube":
                resolved = str(p.resolve()).lower()
                if resolved not in seen_paths:
                    seen_paths.add(resolved)
                    cube_files.append(p)

    if not cube_files:
        print(f"[-] 在 {input_path} 中未找到任何 .cube 文件")
        sys.exit(1)

    print(f"==================================================")
    print(f"  索尼 SLY v2 多管线 LUT 转换工具 (待处理: {len(cube_files)} 个)")
    print(f"  输出目录: {output_dir}")
    print(f"  格式版本: {'SLY v1 (2160 字节)' if args.v1 else 'SLY v2 (2240 字节, 包含6轴深度/底模/色调/WB管线)'}")
    print(f"  命名规范: 严格 8.3 文件名格式 (最大8字符大写 + .SLY，防覆盖)")
    print(f"==================================================")

    used_names = set()
    for existing in output_dir.glob("*.SLY"):
        used_names.add(existing.stem.upper())
    for existing in output_dir.glob("*.sly"):
        used_names.add(existing.stem.upper())

    count = 0
    for idx, cf in enumerate(cube_files, start=1):
        res = convert_cube_to_sly(str(cf), str(output_dir), used_names, index=idx, numbered=args.numbered, v1=args.v1)
        if res:
            count += 1

    print(f"\n[OK] 转换完成！共生成 {count} 个严格 8.3 格式的 .SLY 预设（无任何覆盖）。")
    print(f"使用提示：将整个 {output_dir.name}/ 文件夹复制到相机 SD 卡根目录下即可！")


if __name__ == "__main__":
    main()
