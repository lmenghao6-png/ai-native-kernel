#include "kernel/task.h"
#include "kernel/scheduler.h"
#include "kernel/vmm.h"
#include "kernel/kheap.h"
#include "kernel/serial.h"
#include "kernel/cpu.h"
#include "kernel/string.h"
#include "kernel/syscall.h"

#define USER_STACK_PAGES 4

static struct task primary_task, secondary_task;
struct task *task_get_primary(void) { return &primary_task; }
struct task *task_get_secondary(void) { return &secondary_task; }
const char *task_state_name(enum task_state s) {
    switch(s) { case TASK_EMPTY:return"empty";case TASK_READY:return"ready";case TASK_RUNNING:return"running";case TASK_PREEMPTED:return"preempted";case TASK_BLOCKED:return"blocked";case TASK_EXITED:return"exited";case TASK_FAILED:return"failed";default:return"?"; }
}
void task_init(uint64_t rsp0) { (void)rsp0; primary_task.state=TASK_EMPTY; secondary_task.state=TASK_EMPTY; serial_write("[task] init\n"); }
bool task_prepare_ring3_demo(uint64_t entry) {
    uint64_t stack_base = 0;
    if (!entry ||
        !vmm_alloc_user_pages(
            USER_STACK_PAGES,
            VMM_PAGE_WRITABLE,
            &stack_base,
            0)) {
        primary_task.state = TASK_FAILED;
        serial_write("[task] failed to allocate user stack\n");
        return false;
    }

    memset(&primary_task, 0, sizeof(primary_task));
    primary_task.id = 1;
    primary_task.state = TASK_READY;
    primary_task.priority = 1;
    memcpy(primary_task.name, "init", 5);
    primary_task.ctx.rip = entry;
    primary_task.ctx.rsp = stack_base + USER_STACK_PAGES * 0x1000;
    primary_task.ctx.cs = 0x18 | 3;
    primary_task.ctx.ss = 0x20 | 3;
    primary_task.ctx.rflags = 0x202;
    return true;
}
bool task_prepare_yield_demo(void) { return false; }
bool task_prepare_preempt_demo(void) { return false; }
bool task_prepare_switch_demo(void) { return false; }
bool task_prepare_wait_demo(void) { return false; }
void task_enter_prepared(void) {
    if (primary_task.state != TASK_READY) {
        serial_write("[task] no prepared task\n");
        return;
    }
    primary_task.state = TASK_RUNNING;
    serial_write("[task] entering ring3\n");
    cpu_enter_user_mode(primary_task.ctx.rip, primary_task.ctx.rsp);
}
bool task_can_resume(void) { return false; }
void task_resume_preempted(void) {}
bool task_handle_user_trap(struct interrupt_frame *f) { (void)f; return false; }
void task_handle_syscall_yield(struct interrupt_frame *f) { (void)f; }
void task_handle_syscall_wait(struct interrupt_frame *f) { (void)f; }
void task_handle_syscall_exit(struct interrupt_frame *f) {
    primary_task.state = TASK_EXITED;
    serial_write("[task] user process exited status=");
    serial_write_u64(f->rdi);
    serial_write("\n");
    cpu_halt_forever();
}
void task_handle_timer_preempt(void) {}
void task_wake_channel(uint64_t c) { (void)c; }
