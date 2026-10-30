# Controlador de Webots en C++ que aloja el firmware compartido (ADR 0002).
# Se compila con el botón Build del editor de Webots o con make desde una
# terminal (docs/UCI_WEBOTS.md). Necesita WEBOTS_HOME.
FIRMWARE = ../../../firmware
CXX_SOURCES = scara_uci.cpp $(FIRMWARE)/firmware.cpp
INCLUDE = -I$(FIRMWARE)
CXXFLAGS = -std=c++11 -Wextra
ifeq ($(OS),Windows_NT)
LIBRARIES = -lws2_32
endif

null :=
space := $(null) $(null)
WEBOTS_HOME_PATH ?= $(subst $(space),\ ,$(strip $(subst \,/,$(WEBOTS_HOME))))
include $(WEBOTS_HOME_PATH)/resources/Makefile.include
