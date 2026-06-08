#include "kernel/cpu.h"
#include "kernel/gdt.h"
void io_wait(void) { __asm__ volatile("outb %%al, $0x80" : : "a"(0)); }
void cpu_halt(void) { __asm__ volatile("hlt"); }
void cpu_halt_forever(void) { for(;;) __asm__ volatile("hlt"); }
void cpu_sti(void) { __asm__ volatile("sti"); }
void cpu_cli(void) { __asm__ volatile("cli"); }
void cpu_enter_user_mode(uint64_t entry, uint64_t stack_top) {
    uint64_t user_data = GDT_USER_DATA | 3;
    uint64_t user_code = GDT_USER_CODE | 3;
    __asm__ volatile(
        "cli\n"
        "movw %w0, %%ax\n"
        "movw %%ax, %%ds\n"
        "movw %%ax, %%es\n"
        "pushq %0\n"
        "pushq %1\n"
        "pushq $0x202\n"
        "pushq %2\n"
        "pushq %3\n"
        "iretq"
        :
        : "r"(user_data), "r"(stack_top), "r"(user_code), "r"(entry)
        : "rax", "memory"
    );
    __builtin_unreachable();
}
