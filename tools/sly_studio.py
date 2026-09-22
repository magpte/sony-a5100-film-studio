#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SLY Studio - 索尼 A6000 / A5100 SLY 效果预览与 Delta E 色差质检工具
PC 端启动脚本与命令行色彩质检工具

用法:
  1. 启动 Web 调色质检工作台:
     python tools/sly_studio.py
     (自动在浏览器中打开 tools/sly_studio.html)

  2. 命令行快速跑分评测 (Benchmark):
     python tools/sly_studio.py --benchmark -c <cube_path> -s <sly_path>
"""

import os
import sys
import math
import struct
import argparse
import webbrowser
import http.server
import socketserver
from pathlib import Path
from typing import Tuple, List, Dict, Optional
from concurrent.futures import ProcessPoolExecutor

# 确保在 Windows 控制台下正确输出 UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 预计算 256 点 sRGB -> Linear 查表
SRGB_TO_LIN_LUT = [
    (i / 255.0) / 12.92 if (i / 255.0) <= 0.04045 else math.pow(((i / 255.0) + 0.055) / 1.055, 2.4)
    for i in range(256)
]

# ColorChecker 24 标准参考值 (sRGB 8-bit)
COLORCHECKER_24 = [
    ("Dark Skin", (115, 82, 68)),
    ("Light Skin", (194, 150, 130)),
    ("Blue Sky", (98, 122, 157)),
    ("Foliage", (87, 108, 67)),
    ("Blue Flower", (133, 128, 177)),
    ("Bluish Green", (103, 189, 170)),
    ("Orange", (214, 126, 44)),
    ("Purplish Blue", (80, 91, 166)),
    ("Moderate Red", (193, 90, 99)),
    ("Purple", (94, 60, 108)),
    ("Yellow Green", (157, 188, 64)),
    ("Orange Yellow", (224, 163, 46)),
    ("Blue", (56, 61, 150)),
    ("Green", (70, 148, 73)),
    ("Red", (175, 54, 60)),
    ("Yellow", (231, 199, 31)),
    ("Magenta", (187, 86, 149)),
    ("Cyan", (8, 133, 161)),
    ("White 9.5", (243, 243, 242)),
    ("Neutral 8", (200, 200, 200)),
    ("Neutral 6.5", (160, 160, 160)),
    ("Neutral 5", (122, 122, 121)),
    ("Neutral 3.5", (85, 85, 85)),
    ("Black 2", (52, 52, 52)),
]


class ColorScience:
    """标准色彩空间转换与 CIEDE2000 色差计算"""

    @staticmethod
    def srgb_to_linear(c: float) -> float:
        idx = min(255, max(0, int(round(c))))
        return SRGB_TO_LIN_LUT[idx]

    @staticmethod
    def linear_to_xyz(r: float, g: float, b: float) -> Tuple[float, float, float]:
        x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
        y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
        z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b
        return x, y, z

    @staticmethod
    def _lab_f(t: float) -> float:
        return math.pow(t, 1.0 / 3.0) if t > 0.008856 else (7.787 * t) + (16.0 / 116.0)

    @classmethod
    def xyz_to_lab(cls, x: float, y: float, z: float) -> Tuple[float, float, float]:
        xn, yn, zn = 0.95047, 1.00000, 1.08883
        fx = cls._lab_f(x / xn)
        fy = cls._lab_f(y / yn)
        fz = cls._lab_f(z / zn)
        L = max(0.0, 116.0 * fy - 16.0)
        a = 500.0 * (fx - fy)
        b = 200.0 * (fy - fz)
        return L, a, b

    @classmethod
    def rgb_to_lab(cls, r: float, g: float, b: float) -> Tuple[float, float, float]:
        r_lin = cls.srgb_to_linear(r)
        g_lin = cls.srgb_to_linear(g)
        b_lin = cls.srgb_to_linear(b)
        x, y, z = cls.linear_to_xyz(r_lin, g_lin, b_lin)
        return cls.xyz_to_lab(x, y, z)

    @staticmethod
    def delta_e_00(lab1: Tuple[float, float, float], lab2: Tuple[float, float, float]) -> float:
        """CIEDE2000 色差公式"""
        L1, a1, b1 = lab1
        L2, a2, b2 = lab2

        avg_L = (L1 + L2) / 2.0
        C1 = math.hypot(a1, b1)
        C2 = math.hypot(a2, b2)
        avg_C = (C1 + C2) / 2.0

        G = 0.5 * (1.0 - math.sqrt(math.pow(avg_C, 7) / (math.pow(avg_C, 7) + math.pow(25.0, 7))))
        a1_prime = (1.0 + G) * a1
        a2_prime = (1.0 + G) * a2

        C1_prime = math.hypot(a1_prime, b1)
        C2_prime = math.hypot(a2_prime, b2)
        avg_C_prime = (C1_prime + C2_prime) / 2.0

        h1_prime = math.degrees(math.atan2(b1, a1_prime)) % 360.0
        h2_prime = math.degrees(math.atan2(b2, a2_prime)) % 360.0

        if abs(h1_prime - h2_prime) > 180.0:
            avg_H_prime = (h1_prime + h2_prime + 360.0) / 2.0
        else:
            avg_H_prime = (h1_prime + h2_prime) / 2.0

        T = (1.0 - 0.17 * math.cos(math.radians(avg_H_prime - 30.0))
             + 0.24 * math.cos(math.radians(2.0 * avg_H_prime))
             + 0.32 * math.cos(math.radians(3.0 * avg_H_prime + 6.0))
             - 0.20 * math.cos(math.radians(4.0 * avg_H_prime - 63.0)))

        deltah_prime = h2_prime - h1_prime
        if abs(deltah_prime) > 180.0:
            deltah_prime += 360.0 if h2_prime <= h1_prime else -360.0

        delta_L_prime = L2 - L1
        delta_C_prime = C2_prime - C1_prime
        delta_H_prime = 2.0 * math.sqrt(C1_prime * C2_prime) * math.sin(math.radians(deltah_prime / 2.0))

        SL = 1.0 + (0.015 * math.pow(avg_L - 50.0, 2)) / math.sqrt(20.0 + math.pow(avg_L - 50.0, 2))
        SC = 1.0 + 0.045 * avg_C_prime
        SH = 1.0 + 0.015 * avg_C_prime * T

        delta_theta = 30.0 * math.exp(-math.pow((avg_H_prime - 275.0) / 25.0, 2))
        RC = 2.0 * math.sqrt(math.pow(avg_C_prime, 7) / (math.pow(avg_C_prime, 7) + math.pow(25.0, 7)))
        RT = -math.sin(math.radians(2.0 * delta_theta)) * RC

        de = math.sqrt(
            math.pow(delta_L_prime / SL, 2) +
            math.pow(delta_C_prime / SC, 2) +
            math.pow(delta_H_prime / SH, 2) +
            RT * (delta_C_prime / SC) * (delta_H_prime / SH)
        )
        return de


class SlyParser:
    """解析索尼 A6000 / A5100 SLY 文件 (支持 SLY v1 2160B 与 SLY v2 2240B 多管线)"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.name = ""
        self.version = 1
        self.matrix: List[int] = []
        self.lb = 0
        self.cc = 0
        self.gamma: List[int] = []
        self.base_color_mode = "neutral"
        self.cinema_tone = "off"
        self.depths = [0, 0, 0, 0, 0, 0]  # R, G, B, C, M, Y (-3..+3)
        self.contrast = 0
        self.saturation = 0
        self.sharpness = 0
        self.dro_mode = 0
        self._parse()

    def _parse(self):
        with open(self.filepath, "rb") as f:
            data = f.read()

        if len(data) == 2160:
            self.version = 1
            name_bytes = data[:64].split(b"\x00")[0]
            self.name = name_bytes.decode("utf-8", errors="ignore").strip()
            params = struct.unpack("<9iii i", data[64:64 + 48])
            self.matrix = list(params[:9])
            self.lb = params[9]
            self.cc = params[10]
            self.gamma = list(struct.unpack("<1024H", data[64 + 48:2160]))
            self.base_color_mode = "standard"
            self.cinema_tone = "off"
            self.depths = [0, 0, 0, 0, 0, 0]
        elif len(data) == 2240:
            self.version = 2
            name_bytes = data[:60].split(b"\x00")[0]
            self.name = name_bytes.decode("utf-8", errors="ignore").strip()
            params = struct.unpack("<9iii I", data[64:64 + 48])
            self.matrix = list(params[:9])
            self.lb = params[9]
            self.cc = params[10]

            pipe_data = data[112:112 + 80]
            p = struct.unpack("<BBbbbbbbbbbB", pipe_data[:12])
            modes = ["neutral", "portrait", "standard", "landscape", "blackwhite"]
            tones = ["off", "cinema-tone-1", "cinema-tone-2"]
            self.base_color_mode = modes[p[0]] if p[0] < len(modes) else "neutral"
            self.cinema_tone = tones[p[1]] if p[1] < len(tones) else "off"
            self.depths = list(p[2:8])  # R, G, B, C, M, Y
            self.contrast = p[8]
            self.saturation = p[9]
            self.sharpness = p[10]
            self.dro_mode = p[11]

            self.gamma = list(struct.unpack("<1024H", data[192:192 + 2048]))
        else:
            raise ValueError(f"SLY 文件大小错误: {len(data)} (应为 2160 或 2240 字节)")

    def apply(self, r: float, g: float, b: float) -> Tuple[float, float, float]:
        """对归一化 [0..1] RGB 应用 SLY 模型 (含 6 轴色彩深度与白平衡偏置)"""
        # 1. 白平衡硬件偏置 (LB/CC)
        if self.lb != 0 or self.cc != 0:
            r += self.lb * 0.008
            b -= self.lb * 0.008
            g += self.cc * 0.008
            r -= self.cc * 0.004
            b -= self.cc * 0.004
            r = max(0.0, min(1.0, r))
            g = max(0.0, min(1.0, g))
            b = max(0.0, min(1.0, b))

        # 2. 6 轴色彩深度 (R, G, B, C, M, Y)
        if any(d != 0 for d in self.depths):
            r, g, b = self._apply_color_depth(r, g, b)

        # 3. 3x3 颜色矩阵
        m = self.matrix
        r1 = (m[0] * r + m[1] * g + m[2] * b) / 1024.0
        g1 = (m[3] * r + m[4] * g + m[5] * b) / 1024.0
        b1 = (m[6] * r + m[7] * g + m[8] * b) / 1024.0

        r1 = max(0.0, min(1.0, r1))
        g1 = max(0.0, min(1.0, g1))
        b1 = max(0.0, min(1.0, b1))

        # 4. 1024 点 10-bit Gamma 曲线
        rout = self._eval_gamma(r1)
        gout = self._eval_gamma(g1)
        bout = self._eval_gamma(b1)

        # 5. Cinema Tone 高光滚降模拟
        if self.cinema_tone != "off":
            rout = self._eval_cinema_tone(rout)
            gout = self._eval_cinema_tone(gout)
            bout = self._eval_cinema_tone(bout)

        return rout, gout, bout

    def _apply_color_depth(self, r: float, g: float, b: float) -> Tuple[float, float, float]:
        """模拟 BIONZ X 的 6 轴色彩深度通道调节"""
        mx = max(r, g, b)
        mn = min(r, g, b)
        df = mx - mn
        if df < 1e-5:
            return r, g, b

        # 计算色相角 H (0..360)
        if mx == r:
            h = (60.0 * ((g - b) / df) + 360.0) % 360.0
        elif mx == g:
            h = (60.0 * ((b - r) / df) + 120.0) % 360.0
        else:
            h = (60.0 * ((r - g) / df) + 240.0) % 360.0

        # 各扇区中心色相角: Red=0, Yellow=60, Green=120, Cyan=180, Blue=240, Magenta=300
        centers = [0.0, 120.0, 240.0, 180.0, 300.0, 60.0]  # 对应 depths [R, G, B, C, M, Y]
        total_delta = 0.0
        for i, c in enumerate(centers):
            diff = abs(h - c)
            if diff > 180.0:
                diff = 360.0 - diff
            if diff < 60.0:
                weight = 1.0 - (diff / 60.0)
                total_delta += self.depths[i] * weight * 0.08

        # 对饱和度应用增益调制
        sat_scale = max(0.0, 1.0 + total_delta)
        mid = (mx + mn) * 0.5
        r_out = mid + (r - mid) * sat_scale
        g_out = mid + (g - mid) * sat_scale
        b_out = mid + (b - mid) * sat_scale
        return max(0.0, min(1.0, r_out)), max(0.0, min(1.0, g_out)), max(0.0, min(1.0, b_out))

    def _eval_cinema_tone(self, val: float) -> float:
        """Cinema Tone 高光平滑滚降"""
        if val > 0.75:
            delta = val - 0.75
            return 0.75 + delta * 0.85
        return val

    def _eval_gamma(self, val: float) -> float:
        idx = val * 1023.0
        i0 = int(idx)
        i1 = min(1023, i0 + 1)
        frac = idx - i0
        g0 = self.gamma[i0] / 1023.0
        g1 = self.gamma[i1] / 1023.0
        return g0 * (1.0 - frac) + g1 * frac


class CubeParser:
    """解析 .cube 3D LUT 文件并支持三线性插值"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.size = 0
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
                if key == "LUT_3D_SIZE":
                    self.size = int(parts[1])
                elif len(parts) == 3:
                    try:
                        r, g, b = float(parts[0]), float(parts[1]), float(parts[2])
                        self.data.append((r, g, b))
                    except ValueError:
                        continue

        if self.size == 0 or len(self.data) != self.size ** 3:
            raise ValueError(f"无效的 .cube 文件: size={self.size}, 点数={len(self.data)}")

    def apply(self, r: float, g: float, b: float) -> Tuple[float, float, float]:
        """三线性插值采样"""
        r = max(0.0, min(1.0, r))
        g = max(0.0, min(1.0, g))
        b = max(0.0, min(1.0, b))

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
            out.append(max(0.0, min(1.0, v0 * (1.0 - db) + v1 * db)))

        return out[0], out[1], out[2]


def _eval_slice(r_slice: List[float], grid_size: int, cube_path: str, sly_path: str) -> List[float]:
    cube = CubeParser(cube_path)
    sly = SlyParser(sly_path)
    de_list = []
    for r_val in r_slice:
        for gi in range(grid_size):
            g = gi / (grid_size - 1)
            for bi in range(grid_size):
                b = bi / (grid_size - 1)
                cr, cg, cb = cube.apply(r_val, g, b)
                sr, sg, sb = sly.apply(r_val, g, b)

                lab_cube = ColorScience.rgb_to_lab(cr * 255, cg * 255, cb * 255)
                lab_sly = ColorScience.rgb_to_lab(sr * 255, sg * 255, sb * 255)
                de = ColorScience.delta_e_00(lab_cube, lab_sly)
                de_list.append(de)
    return de_list


def run_benchmark(cube_path: str, sly_path: str):
    """运行 CUBE vs SLY 色彩质检评测 (多进程加速)"""
    print("=" * 65)
    print("  SLY Studio - 索尼 A6000/A5100 色彩保真性质检评测 (CIEDE2000)")
    print("=" * 65)

    cube = CubeParser(cube_path)
    sly = SlyParser(sly_path)

    print(f"[*] 原版 CUBE LUT : {os.path.basename(cube_path)} (尺寸: {cube.size}^3)")
    print(f"[*] 硬件 SLY 预设 : {os.path.basename(sly_path)} (名称: '{sly.name}')")
    print(f"    矩阵: {sly.matrix[:3]} ... | LB: {sly.lb}, CC: {sly.cc}")
    print("-" * 65)

    # 1. ColorChecker 24 评测
    print("\n[1] ColorChecker 24 标准色卡逐块评测:")
    print(f"{'编号':<4} {'色块名称':<18} {'原版 RGB':<15} {'SLY RGB':<15} {'ΔE00':<8}")
    print("-" * 65)

    cc_de_list = []
    for idx, (name, srgb) in enumerate(COLORCHECKER_24, start=1):
        r, g, b = srgb[0] / 255.0, srgb[1] / 255.0, srgb[2] / 255.0
        cr, cg, cb = cube.apply(r, g, b)
        sr, sg, sb = sly.apply(r, g, b)

        lab_cube = ColorScience.rgb_to_lab(cr * 255, cg * 255, cb * 255)
        lab_sly = ColorScience.rgb_to_lab(sr * 255, sg * 255, sb * 255)
        de = ColorScience.delta_e_00(lab_cube, lab_sly)
        cc_de_list.append(de)

        c_str = f"({int(cr*255)}, {int(cg*255)}, {int(cb*255)})"
        s_str = f"({int(sr*255)}, {int(sg*255)}, {int(sb*255)})"
        print(f"{idx:<4} {name:<18} {c_str:<15} {s_str:<15} {de:.2f}")

    cc_mean = sum(cc_de_list) / len(cc_de_list)
    print("-" * 65)
    print(f"ColorChecker 24 平均色差 (Mean ΔE00): {cc_mean:.2f}")

    # 2. 均匀色彩空间采样 (33x33x33 = 35,937 点，多核并行)
    cpu_count = os.cpu_count() or 4
    grid_size = 33
    total_pts = grid_size ** 3
    print(f"\n[2] 全色域 {total_pts:,} 点高精度网格评测 ({cpu_count} 核心多进程并发):")

    r_vals = [ri / (grid_size - 1) for ri in range(grid_size)]
    chunk_size = max(1, math.ceil(len(r_vals) / cpu_count))
    slices = [r_vals[i:i + chunk_size] for i in range(0, len(r_vals), chunk_size)]

    grid_de_list = []
    with ProcessPoolExecutor(max_workers=cpu_count) as executor:
        futures = [executor.submit(_eval_slice, s, grid_size, cube_path, sly_path) for s in slices]
        for f in futures:
            grid_de_list.extend(f.result())

    grid_de_list.sort()
    mean_de = sum(grid_de_list) / len(grid_de_list)
    p95_de = grid_de_list[int(len(grid_de_list) * 0.95)]
    max_de = grid_de_list[-1]

    print(f"  - 平均色差 (Mean ΔE00)   : {mean_de:.2f}")
    print(f"  - 95 分位色差 (P95 ΔE00) : {p95_de:.2f}")
    print(f"  - 最大色差 (Max ΔE00)    : {max_de:.2f}")

    # 评级
    if mean_de < 1.8 and p95_de < 3.5:
        grade = "[A+] 保真度极佳 (Excellent - 人眼基本无感知差异)"
    elif mean_de < 3.2 and p95_de < 6.0:
        grade = "[A] 保真度良好 (Good - 细微色差，完全可用)"
    elif mean_de < 5.0:
        grade = "[B] 保真度尚可 (Fair - 部分高饱和色存在肉眼可见差异)"
    else:
        grade = "[C] 存在较明显色差 (Noticeable - 复杂非线性色彩被平滑)"

    print(f"  - 综合硬件拟合评级       : {grade}")
    print("=" * 65)


def start_server(port: int = 8000):
    """启动本地 HTTP 服务器并自动打开 SLY Studio 网页"""
    root_dir = Path(__file__).resolve().parent.parent
    os.chdir(str(root_dir))

    handler = http.server.SimpleHTTPRequestHandler
    
    # 尝试绑定端口
    for p in range(port, port + 20):
        try:
            with socketserver.TCPServer(("", p), handler) as httpd:
                url = f"http://localhost:{p}/tools/sly_studio.html"
                print(f"[+] SLY Studio 服务已启动: {url}")
                print("    正在自动打开浏览器...")
                webbrowser.open(url)
                print("    按 Ctrl + C 可退出服务器。")
                httpd.serve_forever()
                break
        except OSError:
            continue


def main():
    parser = argparse.ArgumentParser(description="SLY Studio - 索尼 A6000 / A5100 SLY 效果预览与 Delta E 质检工具")
    parser.add_argument("-b", "--benchmark", action="store_true", help="运行命令行 CUBE vs SLY 质检评测")
    parser.add_argument("-c", "--cube", help="原版 .cube 文件路径")
    parser.add_argument("-s", "--sly", help="硬件 .sly 文件路径")
    parser.add_argument("-p", "--port", type=int, default=8000, help="本地 Web 服务端口 (默认: 8000)")
    args = parser.parse_args()

    if args.benchmark:
        if not args.cube or not args.sly:
            print("[-] 错误: 运行 --benchmark 时必须同时提供 -c <cube> 与 -s <sly>")
            sys.exit(1)
        run_benchmark(args.cube, args.sly)
    else:
        start_server(args.port)


if __name__ == "__main__":
    main()
