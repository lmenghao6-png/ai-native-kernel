#include "kernel/debug_shell.h"
#include "kernel/serial.h"
#include "kernel/string.h"
#include "kernel/cpu.h"
void debug_shell_init(void) { serial_write("[shell] debug shell online\n"); }
void debug_shell_run_forever(void) {
    serial_write("bastion> "); cpu_halt_forever();
}
void debug_shell_poll(void) {}
