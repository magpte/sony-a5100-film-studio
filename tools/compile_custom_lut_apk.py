#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compile FilmStudio APK with external SD card LUT support ("C L")."""

import os
import sys
import shutil
import subprocess
import re
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from filter_icons import patch_icons, BADGES
from generate_sly_smali import get_sly_smali_hook
from sign_apk import sign_apk, ensure_pem

HOOK = 'Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;'
CTRL = 'Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/PictureEffectPlusController;'
LAYOUT = 'Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;'

def replace_method(text, signature, replacement):
    pattern = r'^\.method [^\n]*' + re.escape(signature) + r'\n[\s\S]*?^\.end method'
    text, n = re.subn(pattern, lambda _: replacement, text, count=1, flags=re.M)
    if n != 1:
        raise ValueError('Expected exactly one method: ' + signature)
    return text

def main():
    print("=== [1/6] Preparing Decompiled Base ===")
    work_dir = ROOT / 'build-local/custom-lut-build'
    if work_dir.exists():
        shutil.rmtree(work_dir)
    
    release_apk = ROOT / 'inputs/FilmStudio-0.3.0-alpha-movie.apk'
    apktool_jar = ROOT / 'inputs/apktool.jar'
    
    if not release_apk.exists():
        raise FileNotFoundError(f"Missing release APK: {release_apk}")
    if not apktool_jar.exists():
        raise FileNotFoundError(f"Missing apktool: {apktool_jar}")

    # Decompile
    cmd = ['java', '-jar', str(apktool_jar), 'd', '-r', '-f', str(release_apk), '-o', str(work_dir)]
    print("Running apktool d...")
    subprocess.run(cmd, check=True)

    print("=== [2/6] Patching MenuData.xml ===")
    menu_path = work_dir / 'assets/MenuData.xml'
    tree = ET.parse(menu_path)
    parent = next(x for x in tree.iter() if x.get('ItemId') == 'ApplicationTop')
    
    # Check if custom-lut is already in ApplicationTop
    if not any(x.get('ItemId') == 'custom-lut' for x in parent):
        template = parent[0]
        custom_item = ET.Element(template.tag, template.attrib)
        custom_item.attrib.update(
            ItemId='custom-lut',
            Value='custom-lut',
            Title='C L',
            DisplayName='C L',
            ExecType='SET_VALUE',
            NextMenuID='',
            IconRes='drawable/p_16_dd_parts_specialscreen_icon_pictureeffect_illust_mid_normal',
            SelectedIconRes='drawable/p_16_dd_parts_specialscreen_icon_pictureeffect_illust_mid_normal'
        )
        parent.append(custom_item)
        tree.write(menu_path, encoding='utf-8', xml_declaration=True)
        print("Appended 'custom-lut' (C L) to ApplicationTop in MenuData.xml")

    print("=== [3/6] Patching Badges and Icons ===")
    profiles_16 = [
        {'id': pid, 'name': BADGES[pid][0], 'family': BADGES[pid][1], 'reference_name': BADGES[pid][2]}
        for pid in BADGES
    ]
    patch_icons(work_dir, profiles_16)
    print("Applied 16 filter badges (including 'CL')")

    print("=== [4/6] Patching RicohHook.smali ===")
    hook_path = work_dir / 'smali/com/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook.smali'
    hook_text = hook_path.read_text(encoding='utf-8')

    # 1. Inject SLY fields and methods
    sly_smali = get_sly_smali_hook(HOOK)
    hook_text += '\n' + sly_smali + '\n'

    # 2. Patch getPresetIds: add "custom-lut"
    target_preset = 'const-string v1, "ricoh-cross"\n\n    invoke-virtual {v0, v1}, Ljava/util/ArrayList;->add(Ljava/lang/Object;)Z'
    repl_preset = target_preset + '\n\n    const-string v1, "custom-lut"\n\n    invoke-virtual {v0, v1}, Ljava/util/ArrayList;->add(Ljava/lang/Object;)Z'
    assert target_preset in hook_text, "getPresetIds target not found"
    hook_text = hook_text.replace(target_preset, repl_preset, 1)

    # 3. Patch isRicohPreset: return true for "custom-lut"
    target_is_ricoh = '.method public static isRicohPreset(Ljava/lang/String;)Z\n    .locals 1\n'
    repl_is_ricoh = target_is_ricoh + '''
    const-string v0, "custom-lut"
    invoke-virtual {v0, p0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :is_custom_lut
    const/4 v0, 0x1
    return v0
    :is_custom_lut
'''
    assert target_is_ricoh in hook_text, "isRicohPreset target not found"
    hook_text = hook_text.replace(target_is_ricoh, repl_is_ricoh, 1)

    # 4. Patch getFilterName
    p_name = r'(\.method public static getFilterName\(Ljava/lang/String;\)Ljava/lang/String;\s+\.locals )\d+(\s+if-eqz p0, :cond_\w+\s+)'
    m_name = re.search(p_name, hook_text)
    assert m_name, "getFilterName target not found"
    name_check = '''
    const-string v0, "custom-lut"
    invoke-virtual {v0, p0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :not_custom_name

    invoke-static {}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->initSlyList()V
    sget v0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sSlyCount:I
    if-lez v0, :custom_empty_name

    sget-object v0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sSlyNames:[Ljava/lang/String;
    if-eqz v0, :custom_empty_name

    sget v1, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sSlyCurrentIndex:I
    aget-object v0, v0, v1
    if-eqz v0, :custom_empty_name

    new-instance v0, Ljava/lang/StringBuilder;
    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V
    const-string v1, "C L "
    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    move-result-object v0
    sget-object v1, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sSlyNames:[Ljava/lang/String;
    sget v2, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sSlyCurrentIndex:I
    aget-object v1, v1, v2
    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    move-result-object v0
    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v0
    return-object v0

    :custom_empty_name
    const-string v0, "C L (无SD卡LUT)"
    return-object v0

    :not_custom_name
'''
    hook_text = re.sub(p_name, r'\g<1>3\g<2>' + name_check, hook_text, count=1)

    # 5. Patch getFilterGuide
    p_guide = r'(\.method public static getFilterGuide\(Ljava/lang/String;\)Ljava/lang/String;\s+\.locals )\d+(\s+if-eqz p0, :cond_\w+\s+)'
    m_guide = re.search(p_guide, hook_text)
    assert m_guide, "getFilterGuide target not found"
    guide_check = '''
    const-string v0, "custom-lut"
    invoke-virtual {v0, p0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :not_custom_guide

    invoke-static {}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->initSlyList()V
    sget v0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sSlyCount:I
    if-gtz v0, :has_sly_guide

    const-string v0, "未检测到SD卡LUT (放入 /sdcard/SONY_LUT/*.sly)"
    return-object v0

    :has_sly_guide
    new-instance v0, Ljava/lang/StringBuilder;
    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V
    const-string v1, "按中心键/右键进入LUT列表 (共 "
    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    move-result-object v0
    sget v1, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sSlyCount:I
    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
    move-result-object v0
    const-string v1, " 个) · MENU返回"
    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    move-result-object v0
    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v0
    return-object v0

    :not_custom_guide
'''
    hook_text = re.sub(p_guide, r'\g<1>2\g<2>' + guide_check, hook_text, count=1)

    # 6. Patch getRGBMatrix
    p_mat = r'(\.method public static getRGBMatrix\(Ljava/lang/String;\)\[I\s+\.locals )\d+(\s+if-eqz p0, :cond_\w+\s+)'
    m_mat = re.search(p_mat, hook_text)
    assert m_mat, "getRGBMatrix target not found"
    mat_check = '''
    const-string v0, "custom-lut"
    invoke-virtual {v0, p0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :not_custom_matrix

    invoke-static {}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->initSlyList()V
    sget-object v0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sSlyMatrix:[I
    if-eqz v0, :custom_mat_default
    return-object v0

    :custom_mat_default
    const/16 v0, 0x9
    new-array v0, v0, [I
    const/4 v1, 0x0
    const/16 v2, 0x400
    aput v2, v0, v1
    const/4 v1, 0x4
    aput v2, v0, v1
    const/16 v1, 0x8
    aput v2, v0, v1
    return-object v0

    :not_custom_matrix
'''
    hook_text = re.sub(p_mat, r'\g<1>4\g<2>' + mat_check, hook_text, count=1)

    # 7. Patch getGammaBytes
    p_gamma = r'(\.method public static getGammaBytes\(Ljava/lang/String;\)\[B\s+\.locals )\d+(\s+if-eqz p0, :cond_\w+\s+)'
    m_gamma = re.search(p_gamma, hook_text)
    assert m_gamma, "getGammaBytes target not found"
    gamma_check = '''
    const-string v0, "custom-lut"
    invoke-virtual {v0, p0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :not_custom_gamma

    invoke-static {}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->initSlyList()V
    sget-object v0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sSlyGamma:[B
    if-eqz v0, :custom_gamma_default
    return-object v0

    :custom_gamma_default
    const/16 v0, 0x800
    new-array v0, v0, [B
    const/4 v1, 0x0
    :init_lin_gamma
    const/16 v2, 0x400
    if-ge v1, v2, :done_lin_gamma
    mul-int/lit8 v2, v1, 0x2
    and-int/lit16 v3, v1, 0xff
    int-to-byte v3, v3
    aput-byte v3, v0, v2
    add-int/lit8 v2, v2, 0x1
    shr-int/lit8 v3, v1, 0x8
    int-to-byte v3, v3
    aput-byte v3, v0, v2
    add-int/lit8 v1, v1, 0x1
    goto :init_lin_gamma
    :done_lin_gamma
    return-object v0

    :not_custom_gamma
'''
    hook_text = re.sub(p_gamma, r'\g<1>4\g<2>' + gamma_check, hook_text, count=1)

    # 8. Patch applyHook to call applyCustomLutParameters ONLY when custom-lut is active AND in submenu
    target_apply = '''    const-string v4, "standard"

    invoke-virtual {v2, v4}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setColorMode(Ljava/lang/String;)V

    const/4 v4, 0x0

    invoke-virtual {v2, v4}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setContrast(I)V

    invoke-virtual {v2, v4}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setSaturation(I)V

    invoke-virtual {v2, v4}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setSharpness(I)V

    const-string v4, "off"

    invoke-virtual {v2, v4}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setDROMode(Ljava/lang/String;)V'''

    repl_apply = '''    const-string v4, "custom-lut"

    invoke-virtual {v4, p2}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result v4

    # If NOT custom-lut (v4 == 0), branch to standard pipeline
    if-eqz v4, :apply_standard_pipeline

    # If custom-lut: check if in LUT submenu (or confirmed)
    sget-boolean v4, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sInLutSubmenu:Z

    # If NOT in submenu (v4 == 0), branch to standard pipeline
    if-eqz v4, :apply_standard_pipeline

    # In submenu or confirmed: apply SLY v2 multi-pipeline!
    invoke-static {v2}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->applyCustomLutParameters(Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;)V

    goto :pipeline_done

    :apply_standard_pipeline
    # Standard presets or Level 1 browse: standard pipeline
    const-string v4, "standard"

    invoke-virtual {v2, v4}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setColorMode(Ljava/lang/String;)V

    const/4 v4, 0x0

    invoke-virtual {v2, v4}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setContrast(I)V

    invoke-virtual {v2, v4}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setSaturation(I)V

    invoke-virtual {v2, v4}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setSharpness(I)V

    const-string v4, "off"

    invoke-virtual {v2, v4}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setDROMode(Ljava/lang/String;)V

    invoke-static {v2}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->resetCustomLutParameters(Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;)V

    :pipeline_done
    const-string v4, "off"'''

    assert target_apply in hook_text, "applyHook target not found in RicohHook.smali"
    hook_text = hook_text.replace(target_apply, repl_apply, 1)

    hook_path.write_text(hook_text, encoding='utf-8')
    print("Patched RicohHook.smali with all SLY methods and hooks (including SLY v2 multi-pipeline)")

    # 5. Patch Guide and Name for custom-lut (Option D Level 1)
    # guide_check in RicohHook.getFilterGuide
    # Line 153-195 in RicohHook was patched earlier in the script. Let's make sure it reflects Option D.

    print("=== [5/6] Patching PictureEffectPlusOptionMenuLayout.smali for Option D Submenu ===")
    layout_path = work_dir / 'smali/com/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout.smali'
    layout_text = layout_path.read_text(encoding='utf-8')

    # 1. Add mInLutSubmenu field
    target_field = '.field private mSelectedItemId:Ljava/lang/String;'
    repl_field = target_field + '\n\n.field private mInLutSubmenu:Z'
    assert target_field in layout_text, "mSelectedItemId field not found"
    layout_text = layout_text.replace(target_field, repl_field, 1)

    # 2. Patch initializeIconMap (add custom-lut to mItemIconMap)
    p_icon_map = r'(const-string v1, "ricoh-cross"\s+const v2, 0x7f020054\s+invoke-static \{v2\}, Ljava/lang/Integer;->valueOf\(I\)Ljava/lang/Integer;\s+move-result-object v2\s+invoke-virtual \{v0, v1, v2\}, Ljava/util/HashMap;->put\(Ljava/lang/Object;Ljava/lang/Object;\)Ljava/lang/Object;)'
    assert re.search(p_icon_map, layout_text), "initializeIconMap ricoh-cross target not found"
    custom_icon_map = r'''\1

    const-string v1, "custom-lut"

    const v2, 0x7f020054

    invoke-static {v2}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    move-result-object v2

    invoke-virtual {v0, v1, v2}, Ljava/util/HashMap;->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;'''
    layout_text = re.sub(p_icon_map, custom_icon_map, layout_text, count=1)

    # 3. Make getBackgroundDrawable crash-safe against null
    safe_bg = '''.method private getBackgroundDrawable(Ljava/lang/String;)I
    .locals 3
    .param p1, "itemID"    # Ljava/lang/String;

    .prologue
    sget-object v1, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mItemIconMap:Ljava/util/HashMap;

    if-eqz v1, :cond_null_map

    invoke-virtual {v1, p1}, Ljava/util/HashMap;->get(Ljava/lang/Object;)Ljava/lang/Object;

    move-result-object v1

    check-cast v1, Ljava/lang/Integer;

    if-eqz v1, :cond_null_map

    invoke-virtual {v1}, Ljava/lang/Integer;->intValue()I

    move-result v0

    return v0

    :cond_null_map
    const v0, 0x7f020054

    return v0
.end method'''
    layout_text = replace_method(layout_text, 'getBackgroundDrawable(Ljava/lang/String;)I', safe_bg)

    # 4. Patch onItemSelected: update both ItemName and GuideText for custom-lut
    old_item_block = '''    iget-object v1, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mService:Lcom/sony/imaging/app/base/menu/BaseMenuService;

    invoke-virtual {v1, v0}, Lcom/sony/imaging/app/base/menu/BaseMenuService;->getMenuItemText(Ljava/lang/String;)Ljava/lang/CharSequence;

    move-result-object v1

    iget-object v2, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mItemNameView:Landroid/widget/TextView;

    invoke-virtual {v2, v1}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V

    iget-object v1, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mGuideTextView:Landroid/widget/TextView;

    const-string v2, "\\u5207\\u6362\\u9884\\u89c8 \\u00b7 \\u4e2d\\u5fc3\\u786e\\u8ba4 \\u00b7 MENU \\u8fd4\\u56de"

    invoke-virtual {v1, v2}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V'''

    new_item_block = '''    # Reset sInLutSubmenu when selecting other items
    const-string v1, "custom-lut"
    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v1
    if-nez v1, :skip_reset_sub
    const/4 v1, 0x0
    sput-boolean v1, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sInLutSubmenu:Z
    :skip_reset_sub

    # Set item name: for custom-lut, use getFilterName; otherwise use getMenuItemText
    const-string v1, "custom-lut"
    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v1
    if-eqz v1, :cond_default_name

    const-string v1, "custom-lut"
    invoke-static {v1}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->getFilterName(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v1
    goto :cond_set_name

    :cond_default_name
    iget-object v1, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mService:Lcom/sony/imaging/app/base/menu/BaseMenuService;
    invoke-virtual {v1, v0}, Lcom/sony/imaging/app/base/menu/BaseMenuService;->getMenuItemText(Ljava/lang/String;)Ljava/lang/CharSequence;
    move-result-object v1

    :cond_set_name
    iget-object v2, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mItemNameView:Landroid/widget/TextView;
    if-eqz v2, :skip_name
    invoke-virtual {v2, v1}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    :skip_name

    # Set guide text: for custom-lut, use getFilterGuide; otherwise default
    const-string v1, "custom-lut"
    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v1
    if-eqz v1, :cond_default_guide

    const-string v1, "custom-lut"
    invoke-static {v1}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->getFilterGuide(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v2
    goto :cond_set_guide

    :cond_default_guide
    const-string v2, "\\u5207\\u6362\\u9884\\u89c8 \\u00b7 \\u4e2d\\u5fc3\\u786e\\u8ba4 \\u00b7 MENU \\u8fd4\\u56de"

    :cond_set_guide
    iget-object v1, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mGuideTextView:Landroid/widget/TextView;
    if-eqz v1, :skip_guide
    invoke-virtual {v1, v2}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    :skip_guide'''

    layout_text = layout_text.replace(old_item_block, new_item_block, 1)

    # 5. Replace pushedCenterKey for Option D (enters submenu on custom-lut, confirms when in submenu)
    new_pushed_center = '''.method public pushedCenterKey()I
    .locals 4

    .prologue
    # Check if currently on custom-lut
    const-string v0, "custom-lut"
    iget-object v1, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mSelectedItemId:Ljava/lang/String;
    invoke-virtual {v0, v1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    # If NOT custom-lut, do normal center
    if-eqz v0, :do_normal_center

    # On custom-lut: are we already in the submenu?
    iget-boolean v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mInLutSubmenu:Z
    if-nez v0, :already_in_submenu

    # Not yet in submenu: Enter Submenu!
    # First check if we have any LUTs loaded
    invoke-static {}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->initSlyList()V
    sget v0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sSlyCount:I
    if-lez v0, :no_sly_files

    # Enter Submenu!
    const/4 v0, 0x1
    iput-boolean v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mInLutSubmenu:Z
    sput-boolean v0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sInLutSubmenu:Z
    invoke-direct {p0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->updateLutSubmenuUI()V
    const/4 v0, 0x1
    return v0

    :no_sly_files
    # Show feedback if no files found
    iget-object v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mGuideTextView:Landroid/widget/TextView;
    if-eqz v0, :skip_no_sly_guide
    const-string v1, "\\u672a\\u68c0\\u6d4b\\u5230SD\\u5361LUT (\\u8bf7\\u653e\\u5165 SONY_LUT/*.sly)"
    invoke-virtual {v0, v1}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    :skip_no_sly_guide
    const/4 v0, 0x1
    return v0

    :already_in_submenu
    # Already in submenu: pressing Center confirms and exits to shoot!
    const/4 v0, 0x0
    iput-boolean v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mInLutSubmenu:Z
    const/4 v0, 0x1
    sput-boolean v0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sInLutSubmenu:Z
    goto :do_normal_center

    :do_normal_center
    iget-object v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mFilmHandler:Landroid/os/Handler;
    if-eqz v0, :cond_center_0
    invoke-virtual {v0, p0}, Landroid/os/Handler;->removeCallbacks(Ljava/lang/Runnable;)V
    invoke-direct {p0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->applyFilmPreview()Z
    move-result v0
    if-eqz v0, :cond_center_0
    :try_start_0
    invoke-static {}, Lcom/sony/imaging/app/util/BackUpUtil;->getInstance()Lcom/sony/imaging/app/util/BackUpUtil;
    move-result-object v0
    const-string v1, "ID_PICTUREEFFECTPLUS_CURRENT_EFFECT"
    iget-object v2, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mSelectedItemId:Ljava/lang/String;
    invoke-virtual {v0, v1, v2}, Lcom/sony/imaging/app/util/BackUpUtil;->setPreference(Ljava/lang/String;Ljava/lang/Object;)Z
    move-result v3
    :try_end_0
    .catch Ljava/lang/Throwable; {:try_start_0 .. :try_end_0} :catch_center_0
    if-eqz v3, :cond_center_1
    iput-object v2, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mFilmOriginal:Ljava/lang/String;
    iput-object v2, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mPreviousSelectedeffect:Ljava/lang/String;
    const/4 v0, 0x0
    invoke-virtual {p0, v0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->closeMenuLayout(Landroid/os/Bundle;)V
    :cond_center_0
    :goto_center_0
    const/4 v0, 0x1
    return v0
    :catch_center_0
    move-exception v0
    :cond_center_1
    invoke-direct {p0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->restoreFilmPreview()V
    invoke-direct {p0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->showFilmPreviewError()V
    goto :goto_center_0
.end method'''
    layout_text = replace_method(layout_text, 'pushedCenterKey()I', new_pushed_center)

    # 6. Replace pushedMenuKey for Option D (exits submenu to level 1, or closes layout)
    new_pushed_menu = '''.method public pushedMenuKey()I
    .locals 2

    .prologue
    # If in LUT submenu, exit submenu back to level 1!
    iget-boolean v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mInLutSubmenu:Z
    if-nez v0, :exit_lut_submenu

    # Here mInLutSubmenu == 0 (false): Normal menu behavior
    invoke-direct {p0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->endFilmPreview()V
    iget-object v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mLastItemId:Lcom/sony/imaging/app/base/menu/HistoryItem;
    if-nez v0, :cond_menu_0
    invoke-virtual {p0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->closeLayout()V
    goto :goto_menu_0
    :cond_menu_0
    invoke-virtual {p0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->openPreviousMenu()V
    :goto_menu_0
    const/4 v0, 0x1
    return v0

    :exit_lut_submenu
    # Here mInLutSubmenu == 1 (true): Exit submenu back to Level 1
    const/4 v0, 0x0
    iput-boolean v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mInLutSubmenu:Z
    sput-boolean v0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sInLutSubmenu:Z

    # Restore screen title to "胶片工坊"
    iget-object v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mScreenTitle:Landroid/widget/TextView;
    if-eqz v0, :skip_res_title
    const-string v1, "\\u80f6\\u7247\\u5de5\\u574a"
    invoke-virtual {v0, v1}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    :skip_res_title

    # Refresh item name to level 1 text
    const-string v1, "custom-lut"
    invoke-static {v1}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->getFilterName(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v1
    iget-object v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mItemNameView:Landroid/widget/TextView;
    if-eqz v0, :skip_res_name
    invoke-virtual {v0, v1}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    :skip_res_name

    # Refresh guide to level 1 text
    const-string v1, "custom-lut"
    invoke-static {v1}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->getFilterGuide(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v1
    iget-object v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mGuideTextView:Landroid/widget/TextView;
    if-eqz v0, :skip_res_guide
    invoke-virtual {v0, v1}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    :skip_res_guide

    # Update SpecialScreenArea
    iget-object v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mViewArea:Lcom/sony/imaging/app/base/menu/layout/SpecialScreenArea;
    if-eqz v0, :skip_res_area
    invoke-virtual {v0}, Lcom/sony/imaging/app/base/menu/layout/SpecialScreenArea;->update()V
    :skip_res_area

    # Re-apply standard preview since we exited back to Level 1
    invoke-direct {p0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->applyFilmPreview()Z

    const/4 v0, 0x1
    return v0
.end method'''
    layout_text = replace_method(layout_text, 'pushedMenuKey()I', new_pushed_menu)

    # 7. Replace pushedRightKey (in submenu: next LUT; in level 1 custom-lut: enters submenu)
    new_pushed_right = '''.method public pushedRightKey()I
    .locals 2

    .prologue
    iget-boolean v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mInLutSubmenu:Z
    if-nez v0, :sub_right

    # In level 1: if on custom-lut, pressing Right enters submenu
    const-string v0, "custom-lut"
    iget-object v1, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mSelectedItemId:Ljava/lang/String;
    invoke-virtual {v0, v1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :right_default

    invoke-virtual {p0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->pushedCenterKey()I
    move-result v0
    return v0

    :right_default
    invoke-virtual {p0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->pushedDownKey()I
    move-result v0
    return v0

    :sub_right
    # In submenu: switch next LUT
    const/4 v0, 0x1
    invoke-direct {p0, v0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->switchCustomLut(Z)Z
    const/4 v0, 0x1
    return v0
.end method'''
    layout_text = replace_method(layout_text, 'pushedRightKey()I', new_pushed_right)

    # 8. Replace pushedLeftKey (in submenu: prev LUT; in level 1: moves up)
    new_pushed_left = '''.method public pushedLeftKey()I
    .locals 2

    .prologue
    iget-boolean v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mInLutSubmenu:Z
    if-nez v0, :sub_left

    # In level 1:
    invoke-virtual {p0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->pushedUpKey()I
    move-result v0
    return v0

    :sub_left
    # In submenu: switch prev LUT
    const/4 v0, 0x0
    invoke-direct {p0, v0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->switchCustomLut(Z)Z
    const/4 v0, 0x1
    return v0
.end method'''
    layout_text = replace_method(layout_text, 'pushedLeftKey()I', new_pushed_left)

    # 9. Replace turnedSubDialNext (in submenu: next LUT; in level 1: pushedDownKey)
    new_sub_dial_next = '''.method public turnedSubDialNext()I
    .locals 2

    .prologue
    iget-boolean v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mInLutSubmenu:Z
    if-nez v0, :sub_dial_next

    invoke-virtual {p0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->pushedDownKey()I
    move-result v0
    return v0

    :sub_dial_next
    const/4 v0, 0x1
    invoke-direct {p0, v0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->switchCustomLut(Z)Z
    const/4 v0, 0x1
    return v0
.end method'''
    layout_text = replace_method(layout_text, 'turnedSubDialNext()I', new_sub_dial_next)

    # 10. Replace turnedSubDialPrev (in submenu: prev LUT; in level 1: pushedUpKey)
    new_sub_dial_prev = '''.method public turnedSubDialPrev()I
    .locals 2

    .prologue
    iget-boolean v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mInLutSubmenu:Z
    if-nez v0, :sub_dial_prev

    invoke-virtual {p0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->pushedUpKey()I
    move-result v0
    return v0

    :sub_dial_prev
    const/4 v0, 0x0
    invoke-direct {p0, v0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->switchCustomLut(Z)Z
    const/4 v0, 0x1
    return v0
.end method'''
    layout_text = replace_method(layout_text, 'turnedSubDialPrev()I', new_sub_dial_prev)

    # 11. Add pushedDownKey, pushedUpKey, turnedMainDialNext, turnedMainDialPrev, switchCustomLut, and updateLutSubmenuUI
    additional_methods = '''
.method public pushedDownKey()I
    .locals 2

    .prologue
    iget-boolean v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mInLutSubmenu:Z
    if-nez v0, :sub_down

    invoke-super {p0}, Lcom/sony/imaging/app/base/menu/layout/SpecialScreenMenuLayout;->pushedDownKey()I
    move-result v0
    return v0

    :sub_down
    const/4 v0, 0x1
    invoke-direct {p0, v0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->switchCustomLut(Z)Z
    const/4 v0, 0x1
    return v0
.end method

.method public pushedUpKey()I
    .locals 2

    .prologue
    iget-boolean v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mInLutSubmenu:Z
    if-nez v0, :sub_up

    invoke-super {p0}, Lcom/sony/imaging/app/base/menu/layout/SpecialScreenMenuLayout;->pushedUpKey()I
    move-result v0
    return v0

    :sub_up
    const/4 v0, 0x0
    invoke-direct {p0, v0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->switchCustomLut(Z)Z
    const/4 v0, 0x1
    return v0
.end method

.method public turnedMainDialNext()I
    .locals 2

    .prologue
    iget-boolean v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mInLutSubmenu:Z
    if-nez v0, :main_next

    invoke-virtual {p0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->pushedDownKey()I
    move-result v0
    return v0

    :main_next
    const/4 v0, 0x1
    invoke-direct {p0, v0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->switchCustomLut(Z)Z
    const/4 v0, 0x1
    return v0
.end method

.method public turnedMainDialPrev()I
    .locals 2

    .prologue
    iget-boolean v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mInLutSubmenu:Z
    if-nez v0, :main_prev

    invoke-virtual {p0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->pushedUpKey()I
    move-result v0
    return v0

    :main_prev
    const/4 v0, 0x0
    invoke-direct {p0, v0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->switchCustomLut(Z)Z
    const/4 v0, 0x1
    return v0
.end method

.method private switchCustomLut(Z)Z
    .locals 3
    .param p1, "next"    # Z

    .prologue
    :try_start_0
    if-eqz p1, :cond_prev
    invoke-static {}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->nextSlyLut()Z
    move-result v0
    goto :check_result

    :cond_prev
    invoke-static {}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->prevSlyLut()Z
    move-result v0

    :check_result
    invoke-direct {p0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->updateLutSubmenuUI()V
    :try_end_0
    .catch Ljava/lang/Throwable; {:try_start_0 .. :try_end_0} :catch_all

    const/4 v0, 0x1
    return v0

    :catch_all
    move-exception v0
    const-string v1, "switchCustomLut"
    const-string v2, "Error switching LUT"
    invoke-static {v1, v2, v0}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    const/4 v0, 0x1
    return v0
.end method

.method private updateLutSubmenuUI()V
    .locals 4

    .prologue
    # Reset mFilmApplied to force re-applying to BIONZ X ISP on next debounce run
    const/4 v0, 0x0
    iput-object v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mFilmApplied:Ljava/lang/String;

    # Queue preview via debounce handler
    invoke-direct {p0}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->queueFilmPreview()V

    # Update mScreenTitle to "SD卡 LUT 列表"
    iget-object v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mScreenTitle:Landroid/widget/TextView;
    if-eqz v0, :skip_title
    const-string v1, "SD\\u5361 LUT \\u5217\\u8868"
    invoke-virtual {v0, v1}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    :skip_title

    # Build item name: "▶ [1/5] CASABLAN"
    new-instance v1, Ljava/lang/StringBuilder;
    invoke-direct {v1}, Ljava/lang/StringBuilder;-><init>()V
    const-string v2, "\\u25b6 ["
    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    sget v2, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sSlyCurrentIndex:I
    add-int/lit8 v2, v2, 0x1
    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
    const-string v2, "/"
    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    sget v2, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sSlyCount:I
    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
    const-string v2, "] "
    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    sget-object v2, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sSlyNames:[Ljava/lang/String;
    if-eqz v2, :skip_name_str
    sget v3, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;->sSlyCurrentIndex:I
    aget-object v2, v2, v3
    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    :skip_name_str
    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v1

    iget-object v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mItemNameView:Landroid/widget/TextView;
    if-eqz v0, :skip_name
    invoke-virtual {v0, v1}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    :skip_name

    # Update guide: "波轮/上下/左右切换 · 中心键确认 · MENU返回"
    const-string v1, "\\u6ce2\\u8f6e/\\u4e0a\\u4e0b/\\u5de6\\u53f3\\u5207\\u6362 \\u00b7 \\u4e2d\\u5fc3\\u952e\\u786e\\u8ba4 \\u00b7 MENU\\u8fd4\\u56de"
    iget-object v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mGuideTextView:Landroid/widget/TextView;
    if-eqz v0, :skip_guide
    invoke-virtual {v0, v1}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    :skip_guide

    # Update SpecialScreenArea
    iget-object v0, p0, Lcom/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout;->mViewArea:Lcom/sony/imaging/app/base/menu/layout/SpecialScreenArea;
    if-eqz v0, :skip_area
    invoke-virtual {v0}, Lcom/sony/imaging/app/base/menu/layout/SpecialScreenArea;->update()V
    :skip_area
    return-void
.end method
'''
    layout_text += '\n' + additional_methods + '\n'
    layout_path.write_text(layout_text, encoding='utf-8')
    print("Patched PictureEffectPlusOptionMenuLayout.smali with Option D Submenu Mode methods")

    print("=== [6/6] Rebuilding and Signing APK ===")
    unsigned_apk = ROOT / 'output/FilmStudio-0.3.0-custom-lut-unsigned.apk'
    final_apk = ROOT / 'output/FilmStudio-0.3.0-custom-lut.apk'
    unsigned_apk.parent.mkdir(parents=True, exist_ok=True)

    build_cmd = ['java', '-jar', str(apktool_jar), 'b', str(work_dir), '-o', str(unsigned_apk)]
    print("Building APK with apktool...")
    subprocess.run(build_cmd, check=True)

    key = ROOT / '.private/signing.pem'
    key.parent.mkdir(exist_ok=True)
    if not key.exists():
        generated, _ = ensure_pem()
        shutil.move(generated, key)
        key.chmod(0o600)

    print("Signing APK...")
    sign_apk(str(unsigned_apk), str(final_apk), str(key))
    print(f"\nSUCCESS! Built and signed final APK:")
    print(f"  {final_apk} ({final_apk.stat().st_size:,} bytes)")

if __name__ == '__main__':
    main()
