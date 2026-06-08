#pragma once
#include <stdint.h>
void io_wait(void);
void cpu_halt(void);
void cpu_halt_forever(void) __attribute__((noreturn));
void cpu_sti(void);
void cpu_cli(void);
void cpu_enter_user_mode(uint64_t entry, uint64_t stack_top) __attribute__((noreturn));
