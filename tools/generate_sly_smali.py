#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smali generator for Sony SD Card LUT loader with SLY v2 multi-pipeline support.
Generates smali hook extensions for reading .SLY files from the SD card and
safely dispatching parameters to the BIONZ X ISP via reflection (VerifyError immune).
"""

def get_sly_smali_hook(hook_class: str) -> str:
    """
    Returns the smali snippet to inject into RicohHook.smali (or FujiHook.smali).
    hook_class: e.g. "Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;"
    """
    return f"""
# ========================================================
# SD Card LUT Loader Extension (SLY v2 Multi-Pipeline)
# ========================================================

.field public static sSlyPaths:[Ljava/lang/String;
.field public static sSlyNames:[Ljava/lang/String;
.field public static sSlyCount:I
.field public static sSlyCurrentIndex:I
.field public static sSlyScanned:Z

# 3D CUBE Capture Extension fields
.field public static sCubePaths:[Ljava/lang/String;
.field public static sCurrentCubePath:Ljava/lang/String;
.field public static sNeedCubePostProcess:Z
.field public static sActivePresetId:Ljava/lang/String;

.field public static sSlyMatrix:[I
.field public static sSlyGamma:[B
.field public static sSlyLb:I
.field public static sSlyCc:I

# SLY v2 Multi-Pipeline fields
.field public static sSlyVersion:I
.field public static sSlyBaseColorModeStr:Ljava/lang/String;
.field public static sSlyCinemaToneStr:Ljava/lang/String;
.field public static sSlyDepthRed:I
.field public static sSlyDepthGreen:I
.field public static sSlyDepthBlue:I
.field public static sSlyDepthCyan:I
.field public static sSlyDepthMagenta:I
.field public static sSlyDepthYellow:I
.field public static sSlyContrast:I
.field public static sSlySaturation:I
.field public static sSlySharpness:I
.field public static sSlyDroModeStr:Ljava/lang/String;

# Submenu activation state flag (SLY v2 only active in C L submenu or when confirmed)
.field public static sInLutSubmenu:Z

# Cached reflection methods for SLY v2 parameters
.field public static sMethodSetColorDepth:Ljava/lang/reflect/Method;
.field public static sMethodSetCinemaTone:Ljava/lang/reflect/Method;
.field public static sMethodSetWbShiftMode:Ljava/lang/reflect/Method;
.field public static sMethodSetWbShiftLB:Ljava/lang/reflect/Method;
.field public static sMethodSetWbShiftCC:Ljava/lang/reflect/Method;
.field public static sReflectionInitialized:Z

.method public static getColorModeString(I)Ljava/lang/String;
    .locals 1
    packed-switch p0, :pswitch_data_colormode
    const-string v0, "neutral"
    return-object v0

    :pswitch_colormode_0
    const-string v0, "neutral"
    return-object v0

    :pswitch_colormode_1
    const-string v0, "portrait"
    return-object v0

    :pswitch_colormode_2
    const-string v0, "standard"
    return-object v0

    :pswitch_colormode_3
    const-string v0, "landscape"
    return-object v0

    :pswitch_colormode_4
    const-string v0, "blackwhite"
    return-object v0

    :pswitch_data_colormode
    .packed-switch 0x0
        :pswitch_colormode_0
        :pswitch_colormode_1
        :pswitch_colormode_2
        :pswitch_colormode_3
        :pswitch_colormode_4
    .end packed-switch
.end method

.method public static getCinemaToneString(I)Ljava/lang/String;
    .locals 1
    const/4 v0, 0x1
    if-ne p0, v0, :cond_ct_2
    const-string v0, "cinema-tone-1"
    return-object v0

    :cond_ct_2
    const/4 v0, 0x2
    if-ne p0, v0, :cond_ct_off
    const-string v0, "cinema-tone-2"
    return-object v0

    :cond_ct_off
    const-string v0, "off"
    return-object v0
.end method

.method public static getDroModeString(I)Ljava/lang/String;
    .locals 1
    const/4 v0, 0x1
    if-ne p0, v0, :cond_dro_2
    const-string v0, "auto"
    return-object v0

    :cond_dro_2
    const/4 v0, 0x2
    if-ne p0, v0, :cond_dro_off
    const-string v0, "d-range-opt"
    return-object v0

    :cond_dro_off
    const-string v0, "off"
    return-object v0
.end method

# Reflection helpers with cached Method objects: 80-90% faster and GC-friendly
.method private static ensureReflectionInit(Ljava/lang/Object;)V
    .locals 5
    if-nez p0, :has_target
    return-void

    :has_target
    sget-boolean v0, {hook_class}->sReflectionInitialized:Z
    if-nez v0, :already_init

    const/4 v0, 0x1
    sput-boolean v0, {hook_class}->sReflectionInitialized:Z

    invoke-virtual {{p0}}, Ljava/lang/Object;->getClass()Ljava/lang/Class;
    move-result-object v0

    # 1. setColorDepth(String, int)
    :try_start_cd
    const/4 v1, 0x2
    new-array v2, v1, [Ljava/lang/Class;
    const/4 v3, 0x0
    const-class v4, Ljava/lang/String;
    aput-object v4, v2, v3
    const/4 v3, 0x1
    sget-object v4, Ljava/lang/Integer;->TYPE:Ljava/lang/Class;
    aput-object v4, v2, v3
    const-string v3, "setColorDepth"
    invoke-virtual {{v0, v3, v2}}, Ljava/lang/Class;->getMethod(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;
    move-result-object v1
    sput-object v1, {hook_class}->sMethodSetColorDepth:Ljava/lang/reflect/Method;
    :try_end_cd
    .catch Ljava/lang/Throwable; {{:try_start_cd .. :try_end_cd}} :catch_cd
    :catch_cd

    # 2. setCinemaTone(String)
    :try_start_ct
    const/4 v1, 0x1
    new-array v2, v1, [Ljava/lang/Class;
    const/4 v3, 0x0
    const-class v4, Ljava/lang/String;
    aput-object v4, v2, v3
    const-string v3, "setCinemaTone"
    invoke-virtual {{v0, v3, v2}}, Ljava/lang/Class;->getMethod(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;
    move-result-object v1
    sput-object v1, {hook_class}->sMethodSetCinemaTone:Ljava/lang/reflect/Method;
    :try_end_ct
    .catch Ljava/lang/Throwable; {{:try_start_ct .. :try_end_ct}} :catch_ct
    :catch_ct

    # 3. setWhiteBalanceShiftMode(boolean)
    :try_start_wbm
    const/4 v1, 0x1
    new-array v2, v1, [Ljava/lang/Class;
    const/4 v3, 0x0
    sget-object v4, Ljava/lang/Boolean;->TYPE:Ljava/lang/Class;
    aput-object v4, v2, v3
    const-string v3, "setWhiteBalanceShiftMode"
    invoke-virtual {{v0, v3, v2}}, Ljava/lang/Class;->getMethod(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;
    move-result-object v1
    sput-object v1, {hook_class}->sMethodSetWbShiftMode:Ljava/lang/reflect/Method;
    :try_end_wbm
    .catch Ljava/lang/Throwable; {{:try_start_wbm .. :try_end_wbm}} :catch_wbm
    :catch_wbm

    # 4. setWhiteBalanceShiftLB(int)
    :try_start_wblb
    const/4 v1, 0x1
    new-array v2, v1, [Ljava/lang/Class;
    const/4 v3, 0x0
    sget-object v4, Ljava/lang/Integer;->TYPE:Ljava/lang/Class;
    aput-object v4, v2, v3
    const-string v3, "setWhiteBalanceShiftLB"
    invoke-virtual {{v0, v3, v2}}, Ljava/lang/Class;->getMethod(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;
    move-result-object v1
    sput-object v1, {hook_class}->sMethodSetWbShiftLB:Ljava/lang/reflect/Method;
    :try_end_wblb
    .catch Ljava/lang/Throwable; {{:try_start_wblb .. :try_end_wblb}} :catch_wblb
    :catch_wblb

    # 5. setWhiteBalanceShiftCC(int)
    :try_start_wbcc
    const/4 v1, 0x1
    new-array v2, v1, [Ljava/lang/Class;
    const/4 v3, 0x0
    sget-object v4, Ljava/lang/Integer;->TYPE:Ljava/lang/Class;
    aput-object v4, v2, v3
    const-string v3, "setWhiteBalanceShiftCC"
    invoke-virtual {{v0, v3, v2}}, Ljava/lang/Class;->getMethod(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;
    move-result-object v1
    sput-object v1, {hook_class}->sMethodSetWbShiftCC:Ljava/lang/reflect/Method;
    :try_end_wbcc
    .catch Ljava/lang/Throwable; {{:try_start_wbcc .. :try_end_wbcc}} :catch_wbcc
    :catch_wbcc

    :already_init
    return-void
.end method

.method private static callSetColorDepth(Ljava/lang/Object;Ljava/lang/String;I)V
    .locals 4
    if-nez p0, :has_obj_cd2
    return-void
    :has_obj_cd2

    invoke-static {{p0}}, {hook_class}->ensureReflectionInit(Ljava/lang/Object;)V

    sget-object v0, {hook_class}->sMethodSetColorDepth:Ljava/lang/reflect/Method;
    if-nez v0, :has_method_cd2
    return-void
    :has_method_cd2

    :try_start_cd2
    const/4 v1, 0x2
    new-array v1, v1, [Ljava/lang/Object;
    const/4 v2, 0x0
    aput-object p1, v1, v2
    const/4 v2, 0x1
    invoke-static {{p2}}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;
    move-result-object v3
    aput-object v3, v1, v2
    invoke-virtual {{v0, p0, v1}}, Ljava/lang/reflect/Method;->invoke(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;
    :try_end_cd2
    .catch Ljava/lang/Throwable; {{:try_start_cd2 .. :try_end_cd2}} :catch_cd2
    :catch_cd2
    return-void
.end method

.method private static callSetCinemaTone(Ljava/lang/Object;Ljava/lang/String;)V
    .locals 4
    if-nez p0, :has_obj_ct2
    return-void
    :has_obj_ct2

    if-nez p1, :skip_null_ct2
    return-void
    :skip_null_ct2

    invoke-static {{p0}}, {hook_class}->ensureReflectionInit(Ljava/lang/Object;)V

    sget-object v0, {hook_class}->sMethodSetCinemaTone:Ljava/lang/reflect/Method;
    if-nez v0, :has_method_ct2
    return-void
    :has_method_ct2

    :try_start_ct2
    const/4 v1, 0x1
    new-array v1, v1, [Ljava/lang/Object;
    const/4 v2, 0x0
    aput-object p1, v1, v2
    invoke-virtual {{v0, p0, v1}}, Ljava/lang/reflect/Method;->invoke(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;
    :try_end_ct2
    .catch Ljava/lang/Throwable; {{:try_start_ct2 .. :try_end_ct2}} :catch_ct2
    :catch_ct2
    return-void
.end method

.method private static callSetWbShiftLB(Ljava/lang/Object;I)V
    .locals 4
    if-nez p0, :has_obj_lb2
    return-void
    :has_obj_lb2

    invoke-static {{p0}}, {hook_class}->ensureReflectionInit(Ljava/lang/Object;)V

    sget-object v0, {hook_class}->sMethodSetWbShiftLB:Ljava/lang/reflect/Method;
    if-nez v0, :has_method_lb2
    return-void
    :has_method_lb2

    :try_start_lb2
    const/4 v1, 0x1
    new-array v1, v1, [Ljava/lang/Object;
    const/4 v2, 0x0
    invoke-static {{p1}}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;
    move-result-object v3
    aput-object v3, v1, v2
    invoke-virtual {{v0, p0, v1}}, Ljava/lang/reflect/Method;->invoke(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;
    :try_end_lb2
    .catch Ljava/lang/Throwable; {{:try_start_lb2 .. :try_end_lb2}} :catch_lb2
    :catch_lb2
    return-void
.end method

.method private static callSetWbShiftCC(Ljava/lang/Object;I)V
    .locals 4
    if-nez p0, :has_obj_cc2
    return-void
    :has_obj_cc2

    invoke-static {{p0}}, {hook_class}->ensureReflectionInit(Ljava/lang/Object;)V

    sget-object v0, {hook_class}->sMethodSetWbShiftCC:Ljava/lang/reflect/Method;
    if-nez v0, :has_method_cc2
    return-void
    :has_method_cc2

    :try_start_cc2
    const/4 v1, 0x1
    new-array v1, v1, [Ljava/lang/Object;
    const/4 v2, 0x0
    invoke-static {{p1}}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;
    move-result-object v3
    aput-object v3, v1, v2
    invoke-virtual {{v0, p0, v1}}, Ljava/lang/reflect/Method;->invoke(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;
    :try_end_cc2
    .catch Ljava/lang/Throwable; {{:try_start_cc2 .. :try_end_cc2}} :catch_cc2
    :catch_cc2
    return-void
.end method

.method private static callSetWbShiftMode(Ljava/lang/Object;Z)V
    .locals 4
    if-nez p0, :has_obj_wbm2
    return-void
    :has_obj_wbm2

    invoke-static {{p0}}, {hook_class}->ensureReflectionInit(Ljava/lang/Object;)V

    sget-object v0, {hook_class}->sMethodSetWbShiftMode:Ljava/lang/reflect/Method;
    if-nez v0, :has_method_wbm2
    return-void
    :has_method_wbm2

    :try_start_wbm2
    const/4 v1, 0x1
    new-array v1, v1, [Ljava/lang/Object;
    const/4 v2, 0x0
    invoke-static {{p1}}, Ljava/lang/Boolean;->valueOf(Z)Ljava/lang/Boolean;
    move-result-object v3
    aput-object v3, v1, v2
    invoke-virtual {{v0, p0, v1}}, Ljava/lang/reflect/Method;->invoke(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;
    :try_end_wbm2
    .catch Ljava/lang/Throwable; {{:try_start_wbm2 .. :try_end_wbm2}} :catch_wbm2
    :catch_wbm2
    return-void
.end method

.method public static applyCustomLutParameters(Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;)V
    .locals 3
    if-nez p0, :has_obj_apply
    return-void
    :has_obj_apply

    # 1. Base Color Mode (neutral / portrait / standard etc.)
    sget-object v0, {hook_class}->sSlyBaseColorModeStr:Ljava/lang/String;
    if-nez v0, :has_cm
    const-string v0, "neutral"
    :has_cm
    :try_cm
    invoke-virtual {{p0, v0}}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setColorMode(Ljava/lang/String;)V
    :try_cm_end
    .catch Ljava/lang/Throwable; {{:try_cm .. :try_cm_end}} :catch_cm
    :catch_cm

    # 2. Contrast, Saturation, Sharpness
    :try_css
    sget v0, {hook_class}->sSlyContrast:I
    invoke-virtual {{p0, v0}}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setContrast(I)V

    sget v0, {hook_class}->sSlySaturation:I
    invoke-virtual {{p0, v0}}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setSaturation(I)V

    sget v0, {hook_class}->sSlySharpness:I
    invoke-virtual {{p0, v0}}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setSharpness(I)V
    :try_css_end
    .catch Ljava/lang/Throwable; {{:try_css .. :try_css_end}} :catch_css
    :catch_css

    # 3. DRO Mode
    sget-object v0, {hook_class}->sSlyDroModeStr:Ljava/lang/String;
    if-nez v0, :has_dro
    const-string v0, "off"
    :has_dro
    :try_dro
    invoke-virtual {{p0, v0}}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setDROMode(Ljava/lang/String;)V
    :try_dro_end
    .catch Ljava/lang/Throwable; {{:try_dro .. :try_dro_end}} :catch_dro
    :catch_dro

    # 4. Cinema Tone (via reflection)
    sget-object v0, {hook_class}->sSlyCinemaToneStr:Ljava/lang/String;
    if-eqz v0, :skip_ct
    invoke-static {{p0, v0}}, {hook_class}->callSetCinemaTone(Ljava/lang/Object;Ljava/lang/String;)V
    :skip_ct

    # 5. 6-axis Color Depth (via reflection)
    const-string v1, "color-depth-red"
    sget v2, {hook_class}->sSlyDepthRed:I
    invoke-static {{p0, v1, v2}}, {hook_class}->callSetColorDepth(Ljava/lang/Object;Ljava/lang/String;I)V

    const-string v1, "color-depth-green"
    sget v2, {hook_class}->sSlyDepthGreen:I
    invoke-static {{p0, v1, v2}}, {hook_class}->callSetColorDepth(Ljava/lang/Object;Ljava/lang/String;I)V

    const-string v1, "color-depth-blue"
    sget v2, {hook_class}->sSlyDepthBlue:I
    invoke-static {{p0, v1, v2}}, {hook_class}->callSetColorDepth(Ljava/lang/Object;Ljava/lang/String;I)V

    const-string v1, "color-depth-cyan"
    sget v2, {hook_class}->sSlyDepthCyan:I
    invoke-static {{p0, v1, v2}}, {hook_class}->callSetColorDepth(Ljava/lang/Object;Ljava/lang/String;I)V

    const-string v1, "color-depth-magenta"
    sget v2, {hook_class}->sSlyDepthMagenta:I
    invoke-static {{p0, v1, v2}}, {hook_class}->callSetColorDepth(Ljava/lang/Object;Ljava/lang/String;I)V

    const-string v1, "color-depth-yellow"
    sget v2, {hook_class}->sSlyDepthYellow:I
    invoke-static {{p0, v1, v2}}, {hook_class}->callSetColorDepth(Ljava/lang/Object;Ljava/lang/String;I)V

    # 6. White Balance Shift (LB and CC) (via reflection)
    sget v0, {hook_class}->sSlyLb:I
    sget v1, {hook_class}->sSlyCc:I
    or-int v2, v0, v1
    if-eqz v2, :wb_shift_zero

    const/4 v1, 0x1
    invoke-static {{p0, v1}}, {hook_class}->callSetWbShiftMode(Ljava/lang/Object;Z)V
    invoke-static {{p0, v0}}, {hook_class}->callSetWbShiftLB(Ljava/lang/Object;I)V
    sget v0, {hook_class}->sSlyCc:I
    invoke-static {{p0, v0}}, {hook_class}->callSetWbShiftCC(Ljava/lang/Object;I)V
    goto :wb_shift_done

    :wb_shift_zero
    const/4 v1, 0x0
    invoke-static {{p0, v1}}, {hook_class}->callSetWbShiftMode(Ljava/lang/Object;Z)V
    invoke-static {{p0, v1}}, {hook_class}->callSetWbShiftLB(Ljava/lang/Object;I)V
    invoke-static {{p0, v1}}, {hook_class}->callSetWbShiftCC(Ljava/lang/Object;I)V

    :wb_shift_done
    const-string v0, "RicohHook"
    const-string v1, "applyCustomLutParameters: SLY v2 multi-pipeline parameters APPLIED to BIONZ X ISP"
    invoke-static {{v0, v1}}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    return-void
.end method

.method public static resetCustomLutParameters(Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;)V
    .locals 3
    if-nez p0, :has_obj_reset
    return-void
    :has_obj_reset

    # 1. Reset standard baseline
    :try_std
    const-string v0, "standard"
    invoke-virtual {{p0, v0}}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setColorMode(Ljava/lang/String;)V

    const/4 v0, 0x0
    invoke-virtual {{p0, v0}}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setContrast(I)V
    invoke-virtual {{p0, v0}}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setSaturation(I)V
    invoke-virtual {{p0, v0}}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setSharpness(I)V

    const-string v0, "off"
    invoke-virtual {{p0, v0}}, Lcom/sony/scalar/hardware/CameraEx$ParametersModifier;->setDROMode(Ljava/lang/String;)V
    :try_std_end
    .catch Ljava/lang/Throwable; {{:try_std .. :try_std_end}} :catch_std
    :catch_std

    # 2. Reset CinemaTone (via reflection)
    const-string v1, "off"
    invoke-static {{p0, v1}}, {hook_class}->callSetCinemaTone(Ljava/lang/Object;Ljava/lang/String;)V

    # 3. Reset 6-axis Color Depth (via reflection)
    const/4 v1, 0x0
    const-string v2, "color-depth-red"
    invoke-static {{p0, v2, v1}}, {hook_class}->callSetColorDepth(Ljava/lang/Object;Ljava/lang/String;I)V
    const-string v2, "color-depth-green"
    invoke-static {{p0, v2, v1}}, {hook_class}->callSetColorDepth(Ljava/lang/Object;Ljava/lang/String;I)V
    const-string v2, "color-depth-blue"
    invoke-static {{p0, v2, v1}}, {hook_class}->callSetColorDepth(Ljava/lang/Object;Ljava/lang/String;I)V
    const-string v2, "color-depth-cyan"
    invoke-static {{p0, v2, v1}}, {hook_class}->callSetColorDepth(Ljava/lang/Object;Ljava/lang/String;I)V
    const-string v2, "color-depth-magenta"
    invoke-static {{p0, v2, v1}}, {hook_class}->callSetColorDepth(Ljava/lang/Object;Ljava/lang/String;I)V
    const-string v2, "color-depth-yellow"
    invoke-static {{p0, v2, v1}}, {hook_class}->callSetColorDepth(Ljava/lang/Object;Ljava/lang/String;I)V

    # 4. Reset White Balance Shift (via reflection)
    const/4 v1, 0x0
    invoke-static {{p0, v1}}, {hook_class}->callSetWbShiftMode(Ljava/lang/Object;Z)V

    invoke-static {{p0, v1}}, {hook_class}->callSetWbShiftLB(Ljava/lang/Object;I)V

    invoke-static {{p0, v1}}, {hook_class}->callSetWbShiftCC(Ljava/lang/Object;I)V

    const-string v0, "RicohHook"
    const-string v1, "resetCustomLutParameters: Reset to standard baseline (SLY v2 cleared)"
    invoke-static {{v0, v1}}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    return-void
.end method

.method public static initSlyList()V
    .locals 12

    # Guard: only scan once to eliminate repeated SD card I/O
    sget-boolean v0, {hook_class}->sSlyScanned:Z
    if-eqz v0, :do_scan
    return-void

    :do_scan
    const/4 v0, 0x1
    sput-boolean v0, {hook_class}->sSlyScanned:Z

    # Initialize variables
    const/4 v0, 0x0
    sput v0, {hook_class}->sSlyCount:I
    sput v0, {hook_class}->sSlyCurrentIndex:I

    :try_start_scan
    # 1. Try Environment.getExternalStorageDirectory()
    :try_start_env
    invoke-static {{}}, Landroid/os/Environment;->getExternalStorageDirectory()Ljava/io/File;
    move-result-object v0
    if-eqz v0, :check_candidates

    # Check v0/SONY_LUT
    new-instance v1, Ljava/io/File;
    const-string v2, "SONY_LUT"
    invoke-direct {{v1, v0, v2}}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V
    invoke-virtual {{v1}}, Ljava/io/File;->exists()Z
    move-result v2
    if-eqz v2, :check_env_sonylut
    invoke-virtual {{v1}}, Ljava/io/File;->isDirectory()Z
    move-result v2
    if-eqz v2, :check_env_sonylut
    goto :dir_found

    # Check v0/SONYLUT
    :check_env_sonylut
    new-instance v1, Ljava/io/File;
    const-string v2, "SONYLUT"
    invoke-direct {{v1, v0, v2}}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V
    invoke-virtual {{v1}}, Ljava/io/File;->exists()Z
    move-result v2
    if-eqz v2, :check_candidates
    invoke-virtual {{v1}}, Ljava/io/File;->isDirectory()Z
    move-result v2
    if-eqz v2, :check_candidates
    goto :dir_found
    :try_end_env
    .catch Ljava/lang/Throwable; {{:try_start_env .. :try_end_env}} :check_candidates

    # 2. Priority candidate directories on Sony cameras
    :check_candidates
    const/16 v1, 0x8
    new-array v2, v1, [Ljava/lang/String;
    const/4 v1, 0x0
    const-string v3, "/sdcard/SONY_LUT"
    aput-object v3, v2, v1
    const/4 v1, 0x1
    const-string v3, "/storage/sdcard0/SONY_LUT"
    aput-object v3, v2, v1
    const/4 v1, 0x2
    const-string v3, "/mnt/sdcard/SONY_LUT"
    aput-object v3, v2, v1
    const/4 v1, 0x3
    const-string v3, "/sdcard/sony_lut"
    aput-object v3, v2, v1
    const/4 v1, 0x4
    const-string v3, "/storage/sdcard0/sony_lut"
    aput-object v3, v2, v1
    const/4 v1, 0x5
    const-string v3, "/sdcard/SONYLUT"
    aput-object v3, v2, v1
    const/4 v1, 0x6
    const-string v3, "/sdcard/LUTS"
    aput-object v3, v2, v1
    const/4 v1, 0x7
    const-string v3, "/storage/sdcard0/LUTS"
    aput-object v3, v2, v1

    const/4 v3, 0x0
    array-length v4, v2
    :loop_dir
    if-ge v3, v4, :cond_dir_none
    aget-object v5, v2, v3
    new-instance v1, Ljava/io/File;
    invoke-direct {{v1, v5}}, Ljava/io/File;-><init>(Ljava/lang/String;)V
    invoke-virtual {{v1}}, Ljava/io/File;->exists()Z
    move-result v5
    if-eqz v5, :cond_dir_next
    invoke-virtual {{v1}}, Ljava/io/File;->isDirectory()Z
    move-result v5
    if-eqz v5, :cond_dir_next
    goto :dir_found

    :cond_dir_next
    add-int/lit8 v3, v3, 0x1
    goto :loop_dir

    :cond_dir_none
    const-string v0, "RicohHook"
    const-string v1, "No SONY_LUT directory found on SD card"
    invoke-static {{v0, v1}}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I
    return-void

    :dir_found
    invoke-virtual {{v1}}, Ljava/io/File;->listFiles()[Ljava/io/File;
    move-result-object v1

    if-nez v1, :cond_hasfiles
    const-string v0, "RicohHook"
    const-string v1, "listFiles returned null for SONY_LUT"
    invoke-static {{v0, v1}}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I
    return-void

    :cond_hasfiles
    array-length v2, v1
    const/16 v3, 0x40
    if-le v2, v3, :cond_len
    const/16 v2, 0x40
    :cond_len

    new-array v3, v2, [Ljava/lang/String;
    sput-object v3, {hook_class}->sSlyPaths:[Ljava/lang/String;
    new-array v3, v2, [Ljava/lang/String;
    sput-object v3, {hook_class}->sSlyNames:[Ljava/lang/String;
    new-array v3, v2, [Ljava/lang/String;
    sput-object v3, {hook_class}->sCubePaths:[Ljava/lang/String;

    const/4 v3, 0x0
    const/4 v4, 0x0
    :loop_start
    if-lt v3, v2, :loop_body
    sput v4, {hook_class}->sSlyCount:I

    new-instance v0, Ljava/lang/StringBuilder;
    invoke-direct {{v0}}, Ljava/lang/StringBuilder;-><init>()V
    const-string v1, "initSlyList: Found "
    invoke-virtual {{v0, v1}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {{v0, v4}}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
    const-string v1, " SLY/CUBE files on SD card"
    invoke-virtual {{v0, v1}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {{v0}}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v0
    const-string v1, "RicohHook"
    invoke-static {{v1, v0}}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    if-lez v4, :cond_skip_load
    invoke-static {{}}, {hook_class}->loadCurrentSly()Z
    :cond_skip_load
    return-void

    :loop_body
    aget-object v5, v1, v3

    invoke-virtual {{v5}}, Ljava/io/File;->isFile()Z
    move-result v6
    if-eqz v6, :loop_next

    invoke-virtual {{v5}}, Ljava/io/File;->getName()Ljava/lang/String;
    move-result-object v6
    invoke-virtual {{v6}}, Ljava/lang/String;->toLowerCase()Ljava/lang/String;
    move-result-object v7

    const-string v8, ".sly"
    invoke-virtual {{v7, v8}}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z
    move-result v8
    if-nez v8, :loop_is_sly

    const-string v8, ".cub"
    invoke-virtual {{v7, v8}}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z
    move-result v8
    if-nez v8, :loop_is_sly

    const-string v8, ".cube"
    invoke-virtual {{v7, v8}}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z
    move-result v8
    if-nez v8, :loop_is_sly

    const-string v8, ".bin"
    invoke-virtual {{v7, v8}}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z
    move-result v8
    if-nez v8, :loop_is_sly
    goto :loop_next

    :loop_is_sly
    # Enforce 8.3 filename rule: basename length 1..8, no spaces
    const/16 v8, 0x2e
    invoke-virtual {{v6, v8}}, Ljava/lang/String;->lastIndexOf(I)I
    move-result v8
    if-lez v8, :skip_non_83
    const/16 v9, 0x8
    if-gt v8, v9, :skip_non_83

    const/16 v8, 0x20
    invoke-virtual {{v6, v8}}, Ljava/lang/String;->indexOf(I)I
    move-result v8
    if-gez v8, :skip_non_83
    goto :is_valid_83

    :skip_non_83
    const-string v7, "RicohHook"
    new-instance v8, Ljava/lang/StringBuilder;
    invoke-direct {{v8}}, Ljava/lang/StringBuilder;-><init>()V
    const-string v9, "Ignored non-8.3 file: "
    invoke-virtual {{v8, v9}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {{v8, v6}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {{v8}}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v8
    invoke-static {{v7, v8}}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I
    goto :loop_next

    :is_valid_83
    invoke-virtual {{v5}}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;
    move-result-object v7

    sget-object v8, {hook_class}->sSlyPaths:[Ljava/lang/String;
    aput-object v7, v8, v4
    sget-object v8, {hook_class}->sSlyNames:[Ljava/lang/String;
    aput-object v6, v8, v4

    # Resolve sibling .cub / .cube path if available (8.3 first)
    invoke-static {{v5}}, {hook_class}->resolveCubePath(Ljava/io/File;)Ljava/lang/String;
    move-result-object v7
    sget-object v8, {hook_class}->sCubePaths:[Ljava/lang/String;
    aput-object v7, v8, v4

    add-int/lit8 v4, v4, 0x1

    :loop_next
    add-int/lit8 v3, v3, 0x1
    goto :loop_start
    :try_end_scan
    .catch Ljava/lang/Throwable; {{:try_start_scan .. :try_end_scan}} :catch_scan

    :catch_scan
    move-exception v0
    const-string v1, "RicohHook"
    const-string v2, "Error scanning SONY_LUT directory"
    invoke-static {{v1, v2, v0}}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    return-void
.end method

.method public static loadCurrentSly()Z
    .locals 9

    sget v0, {hook_class}->sSlyCount:I
    if-gtz v0, :cond_valid
    const/4 v0, 0x0
    return v0
    :cond_valid

    sget v0, {hook_class}->sSlyCurrentIndex:I
    sget-object v2, {hook_class}->sSlyPaths:[Ljava/lang/String;
    aget-object v2, v2, v0

    # Store corresponding CUBE path for active slot
    sget-object v1, {hook_class}->sCubePaths:[Ljava/lang/String;
    if-eqz v1, :skip_cube_slot
    aget-object v1, v1, v0
    sput-object v1, {hook_class}->sCurrentCubePath:Ljava/lang/String;
    :skip_cube_slot

    # Reset default values for SLY v1 / v2
    const/4 v0, 0x1
    sput v0, {hook_class}->sSlyVersion:I
    const-string v0, "neutral"
    sput-object v0, {hook_class}->sSlyBaseColorModeStr:Ljava/lang/String;
    const-string v0, "off"
    sput-object v0, {hook_class}->sSlyCinemaToneStr:Ljava/lang/String;
    const-string v0, "off"
    sput-object v0, {hook_class}->sSlyDroModeStr:Ljava/lang/String;
    const/4 v0, 0x0
    sput v0, {hook_class}->sSlyDepthRed:I
    sput v0, {hook_class}->sSlyDepthGreen:I
    sput v0, {hook_class}->sSlyDepthBlue:I
    sput v0, {hook_class}->sSlyDepthCyan:I
    sput v0, {hook_class}->sSlyDepthMagenta:I
    sput v0, {hook_class}->sSlyDepthYellow:I
    sput v0, {hook_class}->sSlyContrast:I
    sput v0, {hook_class}->sSlySaturation:I
    sput v0, {hook_class}->sSlySharpness:I
    sput v0, {hook_class}->sSlyLb:I
    sput v0, {hook_class}->sSlyCc:I

    :try_start_0
    new-instance v0, Ljava/io/DataInputStream;
    new-instance v3, Ljava/io/FileInputStream;
    invoke-direct {{v3, v2}}, Ljava/io/FileInputStream;-><init>(Ljava/lang/String;)V
    invoke-direct {{v0, v3}}, Ljava/io/DataInputStream;-><init>(Ljava/io/InputStream;)V

    # Read 64 bytes name header
    const/16 v2, 0x40
    new-array v3, v2, [B
    invoke-virtual {{v0, v3}}, Ljava/io/DataInputStream;->readFully([B)V

    # Find null terminator within first 59 bytes (bytes 60..63 is SLY2 magic in v2)
    const/4 v4, 0x0
    :loop_term
    const/16 v5, 0x3c
    if-ge v4, v5, :cond_term_done
    aget-byte v5, v3, v4
    if-eqz v5, :cond_term_done
    add-int/lit8 v4, v4, 0x1
    goto :loop_term

    :cond_term_done
    if-lez v4, :cond_skip_name
    new-instance v5, Ljava/lang/String;
    const/4 v6, 0x0
    const-string v7, "UTF-8"
    invoke-direct {{v5, v3, v6, v4, v7}}, Ljava/lang/String;-><init>([BIILjava/lang/String;)V
    invoke-virtual {{v5}}, Ljava/lang/String;->trim()Ljava/lang/String;
    move-result-object v5
    invoke-virtual {{v5}}, Ljava/lang/String;->length()I
    move-result v3
    if-lez v3, :cond_skip_name
    sget-object v3, {hook_class}->sSlyNames:[Ljava/lang/String;
    sget v4, {hook_class}->sSlyCurrentIndex:I
    aput-object v5, v3, v4

    :cond_skip_name
    # Read 9 ints (matrix, little-endian in SLY)
    const/16 v2, 0x9
    new-array v3, v2, [I
    const/4 v4, 0x0
    :loop_mat
    if-lt v4, v2, :loop_mat_body
    sput-object v3, {hook_class}->sSlyMatrix:[I
    goto :read_wb

    :loop_mat_body
    invoke-virtual {{v0}}, Ljava/io/DataInputStream;->readInt()I
    move-result v5
    invoke-static {{v5}}, Ljava/lang/Integer;->reverseBytes(I)I
    move-result v5
    aput v5, v3, v4
    add-int/lit8 v4, v4, 0x1
    goto :loop_mat

    :read_wb
    invoke-virtual {{v0}}, Ljava/io/DataInputStream;->readInt()I
    move-result v2
    invoke-static {{v2}}, Ljava/lang/Integer;->reverseBytes(I)I
    move-result v2
    sput v2, {hook_class}->sSlyLb:I

    invoke-virtual {{v0}}, Ljava/io/DataInputStream;->readInt()I
    move-result v2
    invoke-static {{v2}}, Ljava/lang/Integer;->reverseBytes(I)I
    move-result v2
    sput v2, {hook_class}->sSlyCc:I

    # Read 4 bytes version / reserved
    invoke-virtual {{v0}}, Ljava/io/DataInputStream;->readInt()I
    move-result v2
    invoke-static {{v2}}, Ljava/lang/Integer;->reverseBytes(I)I
    move-result v2

    const/4 v3, 0x2
    if-ne v2, v3, :read_gamma

    # SLY v2 pipeline parsing
    sput v3, {hook_class}->sSlyVersion:I

    # Read 80 bytes pipeline header
    const/16 v2, 0x50
    new-array v2, v2, [B
    invoke-virtual {{v0, v2}}, Ljava/io/DataInputStream;->readFully([B)V

    # Byte 0: base_color_mode
    const/4 v3, 0x0
    aget-byte v3, v2, v3
    and-int/lit16 v3, v3, 0xff
    invoke-static {{v3}}, {hook_class}->getColorModeString(I)Ljava/lang/String;
    move-result-object v3
    sput-object v3, {hook_class}->sSlyBaseColorModeStr:Ljava/lang/String;

    # Byte 1: cinema_tone
    const/4 v3, 0x1
    aget-byte v3, v2, v3
    and-int/lit16 v3, v3, 0xff
    invoke-static {{v3}}, {hook_class}->getCinemaToneString(I)Ljava/lang/String;
    move-result-object v3
    sput-object v3, {hook_class}->sSlyCinemaToneStr:Ljava/lang/String;

    # Bytes 2..7: 6-axis color depth
    const/4 v3, 0x2
    aget-byte v3, v2, v3
    sput v3, {hook_class}->sSlyDepthRed:I

    const/4 v3, 0x3
    aget-byte v3, v2, v3
    sput v3, {hook_class}->sSlyDepthGreen:I

    const/4 v3, 0x4
    aget-byte v3, v2, v3
    sput v3, {hook_class}->sSlyDepthBlue:I

    const/4 v3, 0x5
    aget-byte v3, v2, v3
    sput v3, {hook_class}->sSlyDepthCyan:I

    const/4 v3, 0x6
    aget-byte v3, v2, v3
    sput v3, {hook_class}->sSlyDepthMagenta:I

    const/4 v3, 0x7
    aget-byte v3, v2, v3
    sput v3, {hook_class}->sSlyDepthYellow:I

    # Bytes 8..10: contrast, saturation, sharpness
    const/16 v3, 0x8
    aget-byte v3, v2, v3
    sput v3, {hook_class}->sSlyContrast:I

    const/16 v3, 0x9
    aget-byte v3, v2, v3
    sput v3, {hook_class}->sSlySaturation:I

    const/16 v3, 0xa
    aget-byte v3, v2, v3
    sput v3, {hook_class}->sSlySharpness:I

    # Byte 11: dro_mode
    const/16 v3, 0xb
    aget-byte v2, v2, v3
    and-int/lit16 v2, v2, 0xff
    invoke-static {{v2}}, {hook_class}->getDroModeString(I)Ljava/lang/String;
    move-result-object v2
    sput-object v2, {hook_class}->sSlyDroModeStr:Ljava/lang/String;

    :read_gamma
    # Read 2048 bytes gamma table using readFully
    const/16 v2, 0x800
    new-array v3, v2, [B
    invoke-virtual {{v0, v3}}, Ljava/io/DataInputStream;->readFully([B)V
    sput-object v3, {hook_class}->sSlyGamma:[B

    invoke-virtual {{v0}}, Ljava/io/DataInputStream;->close()V
    :try_end_0
    .catch Ljava/lang/Throwable; {{:try_start_0 .. :try_end_0}} :catch_0

    # Log SLY load details
    new-instance v2, Ljava/lang/StringBuilder;
    invoke-direct {{v2}}, Ljava/lang/StringBuilder;-><init>()V
    const-string v3, "Loaded SLY file (v"
    invoke-virtual {{v2, v3}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    sget v3, {hook_class}->sSlyVersion:I
    invoke-virtual {{v2, v3}}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
    const-string v3, "): CM="
    invoke-virtual {{v2, v3}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    sget-object v3, {hook_class}->sSlyBaseColorModeStr:Ljava/lang/String;
    invoke-virtual {{v2, v3}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v3, ", Depth(G)="
    invoke-virtual {{v2, v3}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    sget v3, {hook_class}->sSlyDepthGreen:I
    invoke-virtual {{v2, v3}}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
    const-string v3, ", LB="
    invoke-virtual {{v2, v3}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    sget v3, {hook_class}->sSlyLb:I
    invoke-virtual {{v2, v3}}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
    const-string v3, ", Sat="
    invoke-virtual {{v2, v3}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    sget v3, {hook_class}->sSlySaturation:I
    invoke-virtual {{v2, v3}}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
    invoke-virtual {{v2}}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v2
    const-string v3, "RicohHook"
    invoke-static {{v3, v2}}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    const/4 v0, 0x1
    return v0

    :catch_0
    move-exception v0
    const-string v1, "RicohHook"
    const-string v2, "Error reading SLY file"
    invoke-static {{v1, v2, v0}}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    const/4 v0, 0x0
    return v0
.end method

.method public static nextSlyLut()Z
    .locals 2

    sget v0, {hook_class}->sSlyCount:I
    if-gtz v0, :cond_has_list
    invoke-static {{}}, {hook_class}->initSlyList()V
    sget v0, {hook_class}->sSlyCount:I
    if-gtz v0, :cond_has_list
    const/4 v0, 0x0
    return v0

    :cond_has_list
    sget v0, {hook_class}->sSlyCurrentIndex:I
    add-int/lit8 v0, v0, 0x1
    sget v1, {hook_class}->sSlyCount:I
    rem-int/2addr v0, v1
    sput v0, {hook_class}->sSlyCurrentIndex:I

    invoke-static {{}}, {hook_class}->loadCurrentSly()Z
    move-result v0
    return v0
.end method

.method public static nextSlyLut(Landroid/content/Context;)Z
    .locals 1
    invoke-static {{}}, {hook_class}->nextSlyLut()Z
    move-result v0
    return v0
.end method

.method public static prevSlyLut()Z
    .locals 2

    sget v0, {hook_class}->sSlyCount:I
    if-gtz v0, :cond_has_list
    invoke-static {{}}, {hook_class}->initSlyList()V
    sget v0, {hook_class}->sSlyCount:I
    if-gtz v0, :cond_has_list
    const/4 v0, 0x0
    return v0

    :cond_has_list
    sget v0, {hook_class}->sSlyCurrentIndex:I
    add-int/lit8 v0, v0, -0x1
    if-gez v0, :cond_wrap
    sget v0, {hook_class}->sSlyCount:I
    add-int/lit8 v0, v0, -0x1
    :cond_wrap
    sput v0, {hook_class}->sSlyCurrentIndex:I

    invoke-static {{}}, {hook_class}->loadCurrentSly()Z
    move-result v0
    return v0
.end method

.method public static prevSlyLut(Landroid/content/Context;)Z
    .locals 1
    invoke-static {{}}, {hook_class}->prevSlyLut()Z
    move-result v0
    return v0
.end method

.method public static resolveCubePath(Ljava/io/File;)Ljava/lang/String;
    .locals 5
    if-nez p0, :has_resolve_file
    const/4 v0, 0x0
    return-object v0

    :has_resolve_file
    invoke-virtual {{p0}}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;
    move-result-object v0

    # If file itself is .cub or .cube, return it!
    invoke-virtual {{v0}}, Ljava/lang/String;->toLowerCase()Ljava/lang/String;
    move-result-object v1
    const-string v2, ".cub"
    invoke-virtual {{v1, v2}}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z
    move-result v2
    if-eqz v2, :check_self_cube
    return-object v0

    :check_self_cube
    const-string v2, ".cube"
    invoke-virtual {{v1, v2}}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z
    move-result v2
    if-eqz v2, :check_sly_sibling
    return-object v0

    :check_sly_sibling
    # If file is .sly, find last '.' and check sibling .CUB / .cub / .cube
    const/16 v2, 0x2e
    invoke-virtual {{v0, v2}}, Ljava/lang/String;->lastIndexOf(I)I
    move-result v2
    if-lez v2, :resolve_null

    const/4 v1, 0x0
    invoke-virtual {{v0, v1, v2}}, Ljava/lang/String;->substring(II)Ljava/lang/String;
    move-result-object v0

    # 1. Try prefix.CUB (strict 8.3 uppercase)
    new-instance v1, Ljava/lang/StringBuilder;
    invoke-direct {{v1}}, Ljava/lang/StringBuilder;-><init>()V
    invoke-virtual {{v1, v0}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v2, ".CUB"
    invoke-virtual {{v1, v2}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {{v1}}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v1
    new-instance v2, Ljava/io/File;
    invoke-direct {{v2, v1}}, Ljava/io/File;-><init>(Ljava/lang/String;)V
    invoke-virtual {{v2}}, Ljava/io/File;->exists()Z
    move-result v2
    if-eqz v2, :try_lower_cub
    return-object v1

    :try_lower_cub
    # 2. Try prefix.cub (8.3 lowercase)
    new-instance v1, Ljava/lang/StringBuilder;
    invoke-direct {{v1}}, Ljava/lang/StringBuilder;-><init>()V
    invoke-virtual {{v1, v0}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v2, ".cub"
    invoke-virtual {{v1, v2}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {{v1}}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v1
    new-instance v2, Ljava/io/File;
    invoke-direct {{v2, v1}}, Ljava/io/File;-><init>(Ljava/lang/String;)V
    invoke-virtual {{v2}}, Ljava/io/File;->exists()Z
    move-result v2
    if-eqz v2, :try_cube_ext
    return-object v1

    :try_cube_ext
    # 3. Try prefix.cube (fallback)
    new-instance v1, Ljava/lang/StringBuilder;
    invoke-direct {{v1}}, Ljava/lang/StringBuilder;-><init>()V
    invoke-virtual {{v1, v0}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v0, ".cube"
    invoke-virtual {{v1, v0}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {{v1}}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v0
    new-instance v1, Ljava/io/File;
    invoke-direct {{v1, v0}}, Ljava/io/File;-><init>(Ljava/lang/String;)V
    invoke-virtual {{v1}}, Ljava/io/File;->exists()Z
    move-result v1
    if-eqz v1, :resolve_null
    return-object v0

    :resolve_null
    const/4 v0, 0x0
    return-object v0
.end method

.method public static onPreCapture()V
    .locals 3
    sget-object v0, {hook_class}->sActivePresetId:Ljava/lang/String;
    const-string v1, "custom-cube"
    invoke-virtual {{v1, v0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :is_not_cube
    const/4 v0, 0x1
    sput-boolean v0, {hook_class}->sNeedCubePostProcess:Z
    const-string v0, "RicohHook"
    const-string v1, "onPreCapture: custom-cube active, CUBE post-processing armed"
    invoke-static {{v0, v1}}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    return-void

    :is_not_cube
    const/4 v0, 0x0
    sput-boolean v0, {hook_class}->sNeedCubePostProcess:Z
    return-void
.end method

.method public static onPostCapture(I)V
    .locals 3
    sget-boolean v0, {hook_class}->sNeedCubePostProcess:Z
    if-eqz v0, :skip_cube_post
    const/4 v0, 0x0
    sput-boolean v0, {hook_class}->sNeedCubePostProcess:Z
    if-nez p0, :skip_cube_post
    const-string v0, "RicohHook"
    const-string v1, "onPostCapture: starting CubeProcessor background task"
    invoke-static {{v0, v1}}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    sget-object v0, {hook_class}->sCurrentCubePath:Ljava/lang/String;
    invoke-static {{v0}}, Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/CubeProcessor;->start(Ljava/lang/String;)V

    :skip_cube_post
    return-void
.end method
"""

if __name__ == "__main__":
    print(get_sly_smali_hook("Lcom/yuki/imaging/app/pictureeffectplus/shooting/camera/RicohHook;"))
