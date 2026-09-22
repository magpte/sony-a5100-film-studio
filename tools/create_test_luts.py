#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate diagnostic test SLY v2 files for verifying individual BIONZ X ISP pipelines.
Each test file isolates ONE specific pipeline feature with an extreme parameter,
allowing visual confirmation on the camera LCD/EVF with 100% certainty.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from sly_packer import pack_sly_v2

def create_test_luts():
    out_dir = ROOT / 'tools/SONY_LUT'
    out_dir.mkdir(parents=True, exist_ok=True)

    identity_matrix = [1024, 0, 0, 0, 1024, 0, 0, 0, 1024]
    linear_gamma = list(range(1024))

    tests = [
        {
            "filename": "01_T_GRE.sly",
            "name": "TEST_G_DEPTH",
            "params": {
                "matrix": identity_matrix,
                "lb": 0,
                "cc": 0,
                "base_color_mode": 0, # neutral
                "cinema_tone": 0,     # off
                "depth_red": 0,
                "depth_green": 7,     # MAXIMUM GREEN DEPTH (+7)
                "depth_blue": 0,
                "depth_cyan": 0,
                "depth_magenta": 0,
                "depth_yellow": 0,
                "contrast": 0,
                "saturation": 0,
                "sharpness": 0,
                "dro_mode": 0,
                "gamma": linear_gamma,
            },
            "desc": "6轴色彩深度测试 (Green = +7): 绿叶/绿色物体在二级菜单中呈现超深绿色，一级菜单正常"
        },
        {
            "filename": "02_T_AMB.sly",
            "name": "TEST_WB_AMBER",
            "params": {
                "matrix": identity_matrix,
                "lb": 7,              # MAXIMUM WARM LB (+7)
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
                "gamma": linear_gamma,
            },
            "desc": "白平衡偏移测试 (LB = +7): 全屏极度偏暖偏琥珀色，MENU返回后立即恢复中性"
        },
        {
            "filename": "03_T_LOW.sly",
            "name": "TEST_SAT_LOW",
            "params": {
                "matrix": identity_matrix,
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
                "contrast": -3,       # MINIMUM CONTRAST (-3)
                "saturation": -3,     # MINIMUM SATURATION (-3)
                "sharpness": 0,
                "dro_mode": 0,
                "gamma": linear_gamma,
            },
            "desc": "对比度与饱和度测试 (Sat=-3, Con=-3): 画面瞬间变为低反差、极低饱和度灰调"
        },
        {
            "filename": "04_T_CIN.sly",
            "name": "TEST_CINEMA1",
            "params": {
                "matrix": identity_matrix,
                "lb": 0,
                "cc": 0,
                "base_color_mode": 0,
                "cinema_tone": 1,     # CINEMA-TONE-1
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
                "gamma": linear_gamma,
            },
            "desc": "CinemaTone 电影色调测试 (CinemaTone-1): 亮部暗部具有电影色调曲线特性"
        },
    ]

    for t in tests:
        path = out_dir / t["filename"]
        data = pack_sly_v2(t["name"], t["params"])
        path.write_bytes(data)
        print(f"Generated: {path.name} ({len(data)} bytes) - {t['desc']}")

if __name__ == '__main__':
    create_test_luts()
