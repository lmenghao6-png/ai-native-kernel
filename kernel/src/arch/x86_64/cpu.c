#include "kernel/cpu.h"
void io_wait(void) { __asm__ volatile("outb %%al, $0x80" : : "a"(0)); }
void cpu_halt(void) { __asm__ volatile("hlt"); }
void cpu_halt_forever(void) { for(;;) __asm__ volatile("hlt"); }
void cpu_sti(void) { __asm__ volatile("sti"); }
void cpu_cli(void) { __asm__ volatile("cli"); }
void cpu_enter_user_mode(uint64_t entry, uint64_t stack_top) {
    __asm__ volatile(
        "mov %0, %%rcx\n"
        "mov %1, %%rsp\n"
        "pushq $0x20|3\n"
        "pushq %1\n"
        "pushq $0x202\n"
        "pushq $0x18|3\n"
        "pushq %0\n"
        "iretq" : : "r"(entry), "r"(stack_top) : "rcx", "memory");
    __builtin_unreachable();
}
