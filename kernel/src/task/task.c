#include "kernel/task.h"
#include "kernel/scheduler.h"
#include "kernel/vmm.h"
#include "kernel/kheap.h"
#include "kernel/serial.h"
#include "kernel/cpu.h"
#include "kernel/string.h"
#include "kernel/syscall.h"
static struct task primary_task, secondary_task;
static struct task *tasks[2] = {&primary_task, &secondary_task};
struct task *task_get_primary(void) { return &primary_task; }
struct task *task_get_secondary(void) { return &secondary_task; }
const char *task_state_name(enum task_state s) {
    switch(s) { case TASK_EMPTY:return"empty";case TASK_READY:return"ready";case TASK_RUNNING:return"running";case TASK_PREEMPTED:return"preempted";case TASK_BLOCKED:return"blocked";case TASK_EXITED:return"exited";case TASK_FAILED:return"failed";default:return"?"; }
}
void task_init(uint64_t rsp0) { (void)rsp0; primary_task.state=TASK_EMPTY; secondary_task.state=TASK_EMPTY; serial_write("[task] init\n"); }
bool task_prepare_ring3_demo(void) { serial_write("[task] ring3 demo not implemented\n"); return false; }
bool task_prepare_yield_demo(void) { return false; }
bool task_prepare_preempt_demo(void) { return false; }
bool task_prepare_switch_demo(void) { return false; }
bool task_prepare_wait_demo(void) { return false; }
void task_enter_prepared(void) {}
bool task_can_resume(void) { return false; }
void task_resume_preempted(void) {}
bool task_handle_user_trap(struct interrupt_frame *f) { (void)f; return false; }
void task_handle_syscall_yield(struct interrupt_frame *f) { (void)f; }
void task_handle_syscall_wait(struct interrupt_frame *f) { (void)f; }
void task_handle_timer_preempt(void) {}
void task_wake_channel(uint64_t c) { (void)c; }
