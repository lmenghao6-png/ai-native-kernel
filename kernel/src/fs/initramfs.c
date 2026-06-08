#include "kernel/initramfs.h"
#include "kernel/vfs.h"
#include "kernel/serial.h"
void initramfs_load(void *start, size_t sz) {
    (void)start;
    serial_write("[initramfs] loaded "); serial_write_u64(sz); serial_write(" bytes\n");
}
void initramfs_dump(void) { vfs_dump(vfs_lookup("/"),0); }
