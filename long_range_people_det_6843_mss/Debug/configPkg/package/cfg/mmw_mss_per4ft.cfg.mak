# invoke SourceDir generated makefile for mmw_mss.per4ft
mmw_mss.per4ft: .libraries,mmw_mss.per4ft
.libraries,mmw_mss.per4ft: package/cfg/mmw_mss_per4ft.xdl
	$(MAKE) -f E:\embedded\ccs_project\work3\long_range_people_det_6843_mss/src/makefile.libs

clean::
	$(MAKE) -f E:\embedded\ccs_project\work3\long_range_people_det_6843_mss/src/makefile.libs clean

