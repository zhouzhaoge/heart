#
_XDCBUILDCOUNT = 
ifneq (,$(findstring path,$(_USEXDCENV_)))
override XDCPATH = D:/AppGallery/subject/MMWAVE-SDK/bios_6_73_01_01/packages
override XDCROOT = D:/AppGallery/subject/MMWAVE-SDK/xdctools_3_50_08_24_core
override XDCBUILDCFG = ./config.bld
endif
ifneq (,$(findstring args,$(_USEXDCENV_)))
override XDCARGS = 
override XDCTARGETS = 
endif
#
ifeq (0,1)
PKGPATH = D:/AppGallery/subject/MMWAVE-SDK/bios_6_73_01_01/packages;D:/AppGallery/subject/MMWAVE-SDK/xdctools_3_50_08_24_core/packages;..
HOSTOS = Windows
endif
