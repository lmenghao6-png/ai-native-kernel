#pragma once
#include <stdint.h>
struct interrupt_frame {
    uint64_t rax, rbx, rcx, rdx, rsi, rdi, rbp, r8, r9, r10, r11, r12, r13, r14, r15;
    uint64_t vector, error_code, rip, cs, rflags, rsp, ss;
};
void interrupt_init(void);
void interrupt_start_timer(uint32_t hz);
uint64_t interrupt_get_ticks(void);
