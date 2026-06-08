#pragma once
#include <stdint.h>
struct interrupt_frame { uint64_t r15,r14,r13,r12,r11,r10,r9,r8,rbp,rdi,rsi,rdx,rcx,rbx,rax,vector,error_code,rip,cs,rflags,rsp,ss; };
void interrupt_init(void);
void interrupt_start_timer(uint32_t hz);
uint64_t interrupt_get_ticks(void);
