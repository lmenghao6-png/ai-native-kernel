#include <stdint.h>
#include "kernel/serial.h"
#include "kernel/gdt.h"
#include "kernel/idt.h"
#include "kernel/interrupt.h"
#include "kernel/pmm.h"
#include "kernel/vmm.h"
#include "kernel/kheap.h"
#include "kernel/uaccess.h"
#include "kernel/scheduler.h"
#include "kernel/task.h"
#include "kernel/debug_shell.h"
#include "kernel/vfs.h"
#include "kernel/initramfs.h"
#include "kernel/elf.h"

__attribute__((used, section(".limine_requests")))
static volatile struct { uint64_t id[4]; uint64_t revision; void *response; } memmap_req = {
    {0x67cf3d9d378a806f, 0xe8ac855b2a6e8e11, 0, 0}, 0, 0
};

__attribute__((used, section(".limine_requests")))
static volatile struct { uint64_t id[4]; uint64_t revision; void *response; } hhdm_req = {
    {0x48dcf1cb8ad2b852, 0x63984e959a98244b, 0, 0}, 0, 0
};

__attribute__((used, section(".limine_requests_start")))
static volatile uint64_t req_start[4] = {0,0,0,0};

__attribute__((used, section(".limine_requests_end")))
static volatile uint64_t req_end[4] = {0,0,0,0};

extern uint8_t _initramfs_start[], _initramfs_end[];

void kmain(void) {
    serial_init();
    serial_write("\n=== Bastion Kernel v0.3 ===\n\n");
    gdt_init(); idt_init(); interrupt_init();
    pmm_init(&memmap_req);
    vmm_init(0xffff800000000000ULL);
    kheap_init(); uaccess_init(); gdt_load_tss();
    scheduler_init(50); task_init(0);
    vfs_init();
    size_t isz = (size_t)(_initramfs_end - _initramfs_start);
    if (isz > 0 && isz < 33554432) { initramfs_load(_initramfs_start, isz); initramfs_dump(); }
    else { serial_write("[initramfs] no archive\n"); }
    uint64_t entry = 0;
    if (elf_load("/bin/hello", &entry) == 0) { serial_write("[kmain] ELF ready\n"); }
    serial_write("\nbastion> "); debug_shell_run_forever();
}
