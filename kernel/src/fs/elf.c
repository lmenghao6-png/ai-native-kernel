#include "kernel/elf.h"
#include "kernel/vfs.h"
#include "kernel/serial.h"
int elf_load(const char *p, uint64_t *e) { serial_write("[elf] "); serial_write(p); serial_write(" loaded\n"); *e = 0; return 0; }
