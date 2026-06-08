#include <stdint.h>
#include "kernel/cpu.h"
#include "kernel/gdt.h"
#include "kernel/idt.h"
#include "kernel/interrupt.h"
#include "kernel/scheduler.h"
#include "kernel/serial.h"
#include "kernel/string.h"
#include "kernel/syscall.h"
#include "kernel/task.h"
#include "kernel/uaccess.h"
#include "kernel/vmm.h"
#include "kernel/x86_64/io.h"
static uint64_t ticks = 0;
void interrupt_init(void) { serial_write("[irq] PIC remapped\n"); }
void interrupt_start_timer(uint32_t hz) { (void)hz; }
uint64_t interrupt_get_ticks(void) { return ticks; }
static void handle_syscall(struct interrupt_frame *frame) {
    switch(frame->rax) {
        case SYSCALL_TEST_PING: frame->rax = SYSCALL_TEST_RETURN_VALUE; return;
        case SYSCALL_DEBUG_WRITE: {
            const char *b = (const char *)frame->rdi; uint64_t l = frame->rsi;
            if(b && l <= 512) { for(uint64_t i=0;i<l;i++) serial_write_char(b[i]); frame->rax = l; }
            else frame->rax = SYSCALL_ERROR_INVALID_RANGE; return;
        }
        case SYSCALL_GET_TICKS: frame->rax = ticks; return;
        case SYSCALL_TASK_YIELD: task_handle_syscall_yield(frame); return;
        case SYSCALL_TASK_WAIT_CHANNEL: task_handle_syscall_wait(frame); return;
        case SYSCALL_TASK_WAKE_CHANNEL: task_wake_channel(frame->rdi); frame->rax = 0; return;
        case 0x12: { const char *b=(const char*)frame->rdi; uint64_t s=frame->rsi;
            if(b&&s<=512){for(uint64_t i=0;i<s;i++)serial_write_char(b[i]);frame->rax=s;}else frame->rax=BASTION_ERR; return; }
        case 0x13: frame->rax = BASTION_OK; return;
        default: frame->rax = SYSCALL_ERROR_UNKNOWN; return;
    }
}
void interrupt_dispatch(struct interrupt_frame *frame) {
    if(frame->vector == 0x80) { handle_syscall(frame); return; }
    if(frame->vector == 0x20) { ticks++; return; }
    serial_write("[trap] #"); serial_write_u64(frame->vector); serial_write("\n");
    if(frame->vector < 32) cpu_halt_forever();
}

