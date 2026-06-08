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

void interrupt_init(void) {
    outb(0x20, 0x11); outb(0xA0, 0x11); outb(0x21, 0x20); outb(0xA1, 0x28);
    outb(0x21, 0x04); outb(0xA1, 0x02); outb(0x21, 0x01); outb(0xA1, 0x01);
    outb(0x21, 0xFF); outb(0xA1, 0xFF);
    serial_write("[interrupt] PIC remapped\n");
}

void interrupt_start_timer(uint32_t hz) { (void)hz; }
uint64_t interrupt_get_ticks(void) { return ticks; }

static void interrupt_handle_syscall(struct interrupt_frame *frame) {
    switch (frame->rax) {
        case SYSCALL_TEST_PING: frame->rax = SYSCALL_TEST_RETURN_VALUE; return;
        case SYSCALL_DEBUG_WRITE: {
            const char *buf = (const char *)frame->rdi;
            uint64_t len = frame->rsi;
            if (buf && len <= 512) { for (uint64_t i=0;i<len;i++) serial_write_char(buf[i]); frame->rax = len; }
            else frame->rax = SYSCALL_ERROR_INVALID_RANGE;
            return;
        }
        case SYSCALL_GET_TICKS: frame->rax = ticks; return;
        case SYSCALL_TASK_SNAPSHOT:
            frame->rax = SYSCALL_ERROR_UNKNOWN; return;
        case SYSCALL_SCHED_SNAPSHOT:
            frame->rax = SYSCALL_ERROR_UNKNOWN; return;
        case SYSCALL_TASK_YIELD:
            task_handle_syscall_yield(frame); return;
        case SYSCALL_TASK_WAIT_CHANNEL:
            task_handle_syscall_wait(frame); return;
        case SYSCALL_TASK_WAKE_CHANNEL: {
            task_wake_channel(frame->rdi);
            frame->rax = BASTION_OK; return;
        }
        case 0x12: {
            const char *buf = (const char *)frame->rdi;
            uint64_t size = frame->rsi;
            if (buf && size <= 512) { for (uint64_t i=0;i<size;i++) serial_write_char(buf[i]); frame->rax = size; }
            else frame->rax = BASTION_ERR;
            return;
        }
        case 0x13: frame->rax = BASTION_OK; return;
        default: frame->rax = SYSCALL_ERROR_UNKNOWN; return;
    }
}

void interrupt_dispatch(struct interrupt_frame *frame) {
    if (frame->vector == 0x80) {
        interrupt_handle_syscall(frame);
        return;
    }
    if (frame->vector == 0x20) { ticks++; outb(0x20, 0x20); return; }
    if (frame->vector == 3) { serial_write("[trap] #BP\n"); return; }
    serial_write("[trap] vector=0x"); serial_write_hex_u64(frame->vector);
    serial_write("\n");
    if (frame->vector < 32) { serial_write("[panic] unhandled exception\n"); cpu_halt_forever(); }
}
