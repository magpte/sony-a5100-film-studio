import re
from pathlib import Path

hook_file = Path('build-local/decoded-030-release/smali/com/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook.smali')
text = hook_file.read_text(encoding='utf-8')

# 1. getPresetIds
p1 = r'(\.method public static getPresetIds\(\)Ljava/util/List;[\s\S]*?const-string v1, "ricoh-cross"\s+invoke-virtual \{v0, v1\}, Ljava/util/ArrayList;->add\(Ljava/lang/Object;\)Z)'
m1 = re.search(p1, text)
print('1. getPresetIds:', bool(m1))

# 2. isRicohPreset
p2 = r'(\.method public static isRicohPreset\(Ljava/lang/String;\)Z\s+\.locals \d+\s+)'
m2 = re.search(p2, text)
print('2. isRicohPreset:', bool(m2))

# 3. getFilterName
p3 = r'(\.method public static getFilterName\(Ljava/lang/String;\)Ljava/lang/String;\s+\.locals )\d+(\s+if-eqz p0, :cond_\w+\s+)'
m3 = re.search(p3, text)
print('3. getFilterName:', bool(m3))

# 4. getFilterGuide
p4 = r'(\.method public static getFilterGuide\(Ljava/lang/String;\)Ljava/lang/String;\s+\.locals )\d+(\s+if-eqz p0, :cond_\w+\s+)'
m4 = re.search(p4, text)
print('4. getFilterGuide:', bool(m4))

# 5. getRGBMatrix
p5 = r'(\.method public static getRGBMatrix\(Ljava/lang/String;\)\[I\s+\.locals )\d+(\s+if-eqz p0, :cond_\w+\s+)'
m5 = re.search(p5, text)
print('5. getRGBMatrix:', bool(m5))

# 6. getGammaBytes
p6 = r'(\.method public static getGammaBytes\(Ljava/lang/String;\)\[B\s+\.locals )\d+(\s+if-eqz p0, :cond_\w+\s+)'
m6 = re.search(p6, text)
print('6. getGammaBytes:', bool(m6))

# 7. initializeIconMap in layout
layout_file = Path('build-local/decoded-030-release/smali/com/yuki/imaging/app/pictureeffectplus/shooting/layout/PictureEffectPlusOptionMenuLayout.smali')
l_text = layout_file.read_text(encoding='utf-8')
p7 = r'(\.method private initializeIconMap\(\)V[\s\S]*?const-string v1, "ricoh-cross"\s+const v2, 0x7f020054\s+invoke-static \{v2\}, Ljava/lang/Integer;->valueOf\(I\)Ljava/lang/Integer;\s+move-result-object v2\s+invoke-virtual \{v0, v1, v2\}, Ljava/util/HashMap;->put\(Ljava/lang/Object;Ljava/lang/Object;\)Ljava/lang/Object;)'
m7 = re.search(p7, l_text)
print('7. initializeIconMap:', bool(m7))
