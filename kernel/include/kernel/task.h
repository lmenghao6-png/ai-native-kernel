#pragma once
#include <stdint.h>
#include <stdbool.h>
#include "kernel/interrupt.h"
enum task_state { TASK_EMPTY, TASK_READY, TASK_RUNNING, TASK_PREEMPTED, TASK_BLOCKED, TASK_EXITED, TASK_FAILED };
struct task_context { uint64_t r15,r14,r13,r12,r11,r10,r9,r8,rbp,rdi,rsi,rdx,rcx,rbx,rax,rip,cs,rflags,rsp,ss,cr3; };
struct task { uint64_t id; enum task_state state; uint32_t priority; char name[32]; struct task_context ctx; };
const char *task_state_name(enum task_state s);
void task_init(uint64_t rsp0);
bool task_prepare_ring3_demo(uint64_t entry);
bool task_prepare_yield_demo(void);
bool task_prepare_preempt_demo(void);
bool task_prepare_switch_demo(void);
bool task_prepare_wait_demo(void);
void task_enter_prepared(void);
bool task_can_resume(void);
void task_resume_preempted(void);
struct task *task_get_primary(void);
struct task *task_get_secondary(void);
bool task_handle_user_trap(struct interrupt_frame *frame);
void task_handle_syscall_yield(struct interrupt_frame *frame);
void task_handle_syscall_wait(struct interrupt_frame *frame);
void task_handle_syscall_exit(struct interrupt_frame *frame) __attribute__((noreturn));
void task_handle_timer_preempt(void);
void task_wake_channel(uint64_t channel);
