################################################################################
# Automatically-generated file. Do not edit!
################################################################################

SHELL = cmd.exe

# Each subdirectory must supply rules for building sources it contributes
%.oer4f: ../%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Building file: "$<"'
	@echo 'Invoking: Arm Compiler'
	"D:/AppGallery/subject/ccs/ccs/tools/compiler/ti-cgt-arm_20.2.7.LTS/bin/armcl" -mv7R4 --code_state=16 --float_support=VFPv3D16 -me -O3 --include_path="E:/embedded/ccs_project/work3/long_range_people_det_6843_mss" --include_path="D:/AppGallery/subject/MMWAVE-SDK/mmwave_sdk_03_06_02_00-LTS/packages" --include_path="D:/AppGallery/subject/ccs/radar_toolbox_4_00_00_05/source/ti/custom_sdk_files/sdk3" --include_path="D:/AppGallery/subject/ccs/radar_toolbox_4_00_00_05" --include_path="D:/AppGallery/subject/ccs/ccs/tools/compiler/ti-cgt-arm_20.2.7.LTS/include" --define=SOC_XWR68XX --define=SUBSYS_MSS --define=USE_TRACPROC_OVERHEAD_DPU --define=MMWAVE_L3RAM_NUM_BANK=6 --define=MMWAVE_SHMEM_TCMA_NUM_BANK=0 --define=MMWAVE_SHMEM_TCMB_NUM_BANK=0 --define=MMWAVE_SHMEM_BANK_SIZE=0x20000 --define=MMWAVE_L3_CODEMEM_SIZE=0x100 --define=DOWNLOAD_FROM_CCS --define=DebugP_ASSERT_ENABLED --define=_LITTLE_ENDIAN --define=OBJDET_NO_RANGE --define=GTRACK_3D --define=APP_RESOURCE_FILE='<'mmw_res.h'>' -g --diag_warning=225 --diag_wrap=off --display_error_number --gen_func_subsections=on --enum_type=int --abi=eabi --obj_extension=.oer4f --preproc_with_compile --preproc_dependency="$(basename $(<F)).d_raw" $(GEN_OPTS__FLAG) "$<"
	@echo 'Finished building: "$<"'
	@echo ' '

build-1208409121:
	@$(MAKE) --no-print-directory -Onone -f subdir_rules.mk build-1208409121-inproc

build-1208409121-inproc: ../mmw_mss.cfg
	@echo 'Building file: "$<"'
	@echo 'Invoking: XDCtools'
	"D:/AppGallery/subject/MMWAVE-SDK/xdctools_3_50_08_24_core/xs" --xdcpath="D:/AppGallery/subject/MMWAVE-SDK/bios_6_73_01_01/packages;" xdc.tools.configuro -o configPkg -t ti.targets.arm.elf.R4Ft -p ti.platforms.cortexR:IWR68XX:false:200 -r release -c "D:/AppGallery/subject/ccs/ccs/tools/compiler/ti-cgt-arm_20.2.7.LTS" --compileOptions "--enum_type=int " "$<"
	@echo 'Finished building: "$<"'
	@echo ' '

configPkg/linker.cmd: build-1208409121 ../mmw_mss.cfg
configPkg/compiler.opt: build-1208409121
configPkg: build-1208409121


