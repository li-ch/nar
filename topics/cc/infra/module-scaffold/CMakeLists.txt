build_lib(
  LIBNAME auto-cc
  SOURCE_FILES
    model/cc-algo.cc
  HEADER_FILES
    model/cc-algo.h
  LIBRARIES_TO_LINK
    ${libinternet}
    ${libpoint-to-point}
    ${libapplications}
    ${libtraffic-control}
)

build_lib_example(
  NAME auto-cc-scenario
  SOURCE_FILES
    examples/scenario.cc
  LIBRARIES_TO_LINK
    ${libauto-cc}
    ${libinternet}
    ${libpoint-to-point}
    ${libapplications}
    ${libtraffic-control}
    ${libflow-monitor}
)
