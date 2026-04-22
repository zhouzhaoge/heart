## THIS IS A GENERATED FILE -- DO NOT EDIT
.configuro: .libraries,er4ft linker.cmd package/cfg/mmw_mss_per4ft.oer4ft

# To simplify configuro usage in makefiles:
#     o create a generic linker command file name 
#     o set modification times of compiler.opt* files to be greater than
#       or equal to the generated config header
#
linker.cmd: package/cfg/mmw_mss_per4ft.xdl
	$(SED) 's"^\"\(package/cfg/mmw_mss_per4ftcfg.cmd\)\"$""\"E:/embedded/ccs_project/work3/long_range_people_det_6843_mss/Debug/configPkg/\1\""' package/cfg/mmw_mss_per4ft.xdl > $@
	-$(SETDATE) -r:max package/cfg/mmw_mss_per4ft.h compiler.opt compiler.opt.defs
